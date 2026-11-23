"""Dependency-light lexical retrieval (BM25) over a paper's text blocks.

Used to ground the chat feature without downloading any embedding model, so it
works offline on the data disk.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

_WORD = re.compile(r"[a-z0-9]+|[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af]")
_CAPTION = re.compile(r"^(?:table|figure|fig\.?)\s+\d+\s*[:.]", re.I)


def _tok(text: str) -> list[str]:
    # NFKC expands PDF ligatures ("\ufb01rst" -> "first"); CJK characters count as one token each
    return _WORD.findall(unicodedata.normalize("NFKC", text).lower())


def _union_bbox(a: list | None, b: list | None) -> list | None:
    if not a:
        return list(b) if isinstance(b, (list, tuple)) else None
    if not b:
        return list(a) if isinstance(a, (list, tuple)) else None
    return [
        round(min(a[0], b[0]), 2),
        round(min(a[1], b[1]), 2),
        round(max(a[2], b[2]), 2),
        round(max(a[3], b[3]), 2),
    ]


def _same_column(b1: list | None, b2: list | None, page_w: float) -> bool:
    if not b1 or not b2 or not page_w:
        return True
    x_overlap = min(b1[2], b2[2]) - max(b1[0], b2[0])
    min_w = max(1.0, min(b1[2] - b1[0], b2[2] - b2[0]))
    if x_overlap / min_w > 0.25:
        return True
    return (b1[2] - b1[0]) > 0.55 * page_w or (b2[2] - b2[0]) > 0.55 * page_w


def _is_page_number(text: str, bbox: list | None, page_h: float) -> bool:
    t = text.strip()
    if len(t) <= 4 and t.isdigit() and bbox and page_h:
        return bbox[1] > page_h * 0.88 or bbox[3] < page_h * 0.10
    return False


def _is_tabular_group(g: dict) -> bool:
    if g["starts_cap"]:
        return False
    if g["short_blocks"] or len(g["texts"]) >= 2:
        return True
    txt = "\n".join(g["texts"])
    lines = [ln for ln in txt.splitlines() if ln.strip()]
    return bool(lines) and (sum(len(ln) < 60 for ln in lines) / len(lines)) >= 0.6


def build_chunks(parsed: dict, max_chars: int = 900) -> list[dict]:
    """Flatten blocks into retrieval chunks with page + bbox provenance.

    Adjacent short blocks in the same column (such as PDF table column headers,
    row groups, headings, and captions) are coalesced in reading order up to
    ``max_chars`` (or ``1.5 * max_chars`` when attaching a table/figure caption)
    so tabular numbers stay paired with their headers and captions instead of
    being dropped or orphaned. For very tall multi-chunk tables, sibling body
    chunks inherit compact caption/header index tokens while keeping ``text``
    strictly verbatim.
    """
    table_cap_max = int(max_chars * 1.5)
    chunks: list[dict] = []
    for page in parsed.get("pages", []):
        pno = page["index"]
        pw = float(page.get("width") or 0)
        ph = float(page.get("height") or 0)
        blocks = [
            b for b in page.get("blocks", [])
            if b.get("text", "").strip() and not _is_page_number(b.get("text", ""), b.get("bbox"), ph)
        ]
        groups: list[dict] = []
        cur: dict | None = None
        for b in blocks:
            txt = b["text"].strip()
            bb = b.get("bbox")
            is_cap = bool(_CAPTION.match(txt))
            if cur is None:
                cur = {
                    "texts": [txt], "bbox": list(bb) if isinstance(bb, (list, tuple)) else None,
                    "block_id": b.get("id"), "last_bb": bb, "len": len(txt),
                    "short_blocks": len(txt) < 350, "cap_text": txt if is_cap else "",
                    "starts_cap": is_cap, "closed": False,
                }
                continue
            prev_bb = cur["last_bb"]
            same_col = _same_column(prev_bb, bb, pw)
            v_gap = (bb[1] - prev_bb[3]) if (bb and prev_bb) else 0.0
            short_involved = len(txt) < 300 or cur["len"] < 300
            close_v = -15.0 <= v_gap <= (45.0 if (short_involved or is_cap) else 18.0)
            limit = table_cap_max if is_cap else max_chars
            fits = cur["len"] + 1 + len(txt) <= limit
            if is_cap:
                # Attach below-table captions to the preceding tabular/short group and close it;
                # above-table captions following a long prose paragraph start a new group.
                can_merge = not cur["closed"] and same_col and close_v and fits and (
                    cur["short_blocks"] or cur["len"] < 350 or _is_tabular_group(cur)
                )
            else:
                can_merge = not cur["closed"] and same_col and close_v and fits and short_involved
            if can_merge:
                cur["texts"].append(txt)
                cur["bbox"] = _union_bbox(cur["bbox"], bb)
                cur["last_bb"] = bb
                cur["len"] += 1 + len(txt)
                cur["short_blocks"] = cur["short_blocks"] and len(txt) < 350
                if is_cap:
                    cur["cap_text"] = txt
                    cur["closed"] = True
            else:
                groups.append(cur)
                cur = {
                    "texts": [txt], "bbox": list(bb) if isinstance(bb, (list, tuple)) else None,
                    "block_id": b.get("id"), "last_bb": bb, "len": len(txt),
                    "short_blocks": len(txt) < 350, "cap_text": txt if is_cap else "",
                    "starts_cap": is_cap, "closed": False,
                }
        if cur is not None:
            groups.append(cur)

        # Propagate compact caption lead + header tokens to sibling chunks of tall multi-chunk tables
        # (for BM25 retrieval only; chunk text stays verbatim and contiguous).
        group_extra_toks: list[list[str]] = [[] for _ in groups]
        for gi, g in enumerate(groups):
            if not g["cap_text"]:
                continue
            cap_toks = _tok(g["cap_text"][:180])
            j = gi - 1
            table_idxs: list[int] = []
            next_bb = g["bbox"]
            while j >= 0 and _is_tabular_group(groups[j]) and not groups[j]["cap_text"]:
                gbb = groups[j]["bbox"]
                if gbb and next_bb and _same_column(gbb, next_bb, pw) and -15.0 <= (next_bb[1] - gbb[3]) <= 50.0:
                    table_idxs.append(j)
                    next_bb = gbb
                    j -= 1
                else:
                    break
            if table_idxs:
                header_toks = _tok(groups[table_idxs[-1]]["texts"][0][:180])
                extra = list(dict.fromkeys(cap_toks + header_toks))
                for ti in table_idxs:
                    group_extra_toks[ti].extend(extra)
                if not g["starts_cap"]:
                    group_extra_toks[gi].extend(header_toks)
            elif g["starts_cap"]:
                j = gi + 1
                table_idxs = []
                prev_bb = g["bbox"]
                while j < len(groups) and _is_tabular_group(groups[j]) and not groups[j]["cap_text"]:
                    gbb = groups[j]["bbox"]
                    if gbb and prev_bb and _same_column(prev_bb, gbb, pw) and -15.0 <= (gbb[1] - prev_bb[3]) <= 50.0:
                        table_idxs.append(j)
                        prev_bb = gbb
                        j += 1
                    else:
                        break
                if table_idxs:
                    header_src = g["texts"][1] if len(g["texts"]) > 1 else groups[table_idxs[0]]["texts"][0]
                    header_toks = _tok(header_src[:180])
                    extra = list(dict.fromkeys(cap_toks + header_toks))
                    for ti in table_idxs:
                        group_extra_toks[ti].extend(extra)

        for gi, g in enumerate(groups):
            text = "\n".join(g["texts"]).strip()
            if len(text) < 30:
                continue
            lim = table_cap_max if g["cap_text"] else max_chars
            pieces = [text] if len(text) <= lim else [
                text[i : i + max_chars] for i in range(0, len(text), max_chars)
            ]
            extra = group_extra_toks[gi]
            for pc in pieces:
                toks = _tok(pc)
                if extra:
                    seen = set(toks)
                    toks = toks + [t for t in extra if t not in seen]
                chunks.append({
                    "page": pno,
                    "bbox": g["bbox"],
                    "block_id": g["block_id"],
                    "text": pc,
                    "tokens": toks,
                })
    return chunks


def retrieve(query: str, chunks: list[dict], k: int = 6) -> list[dict]:
    """Return the top-k chunks by BM25 score."""
    q_terms = _tok(query)
    if not q_terms or not chunks:
        return chunks[:k]
    N = len(chunks)
    df: Counter = Counter()
    for c in chunks:
        for t in set(c["tokens"]):
            df[t] += 1
    avgdl = (sum(len(c["tokens"]) for c in chunks) / N) or 1.0
    k1, b = 1.5, 0.75

    scored = []
    for c in chunks:
        tf = Counter(c["tokens"])
        dl = len(c["tokens"]) or 1
        score = 0.0
        for t in q_terms:
            if t not in tf:
                continue
            idf = math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5))
            denom = tf[t] + k1 * (1 - b + b * dl / avgdl)
            score += idf * (tf[t] * (k1 + 1)) / denom
        if score > 0:
            scored.append((score, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:k]]
