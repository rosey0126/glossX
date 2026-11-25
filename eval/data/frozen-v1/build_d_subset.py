"""Freeze D from the 90 task IDs used in the historical diagnostic experiment.

No inference, network access, answer-quality filtering, or arXiv PDF copying.
Run with a Python containing reportlab. Optional --qa-python points to a
Python containing PyMuPDF for full-page rendering and bounding-box checks.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
from functools import partial
import hashlib
import json
import math
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
import unicodedata
from xml.sax.saxutils import escape


sys.dont_write_bytecode = True
DEFAULT_SOURCE = Path(__file__).resolve().parents[1]
TASK_SCHEMA_KEYS = {"id", "suite", "kind", "question", "papers", "gold"}
NATIVE_KINDS = {"qa", "claim", "review", "tutor", "route", "repro"}
FALLBACK_CODEPOINTS: set[int] = set()
DECISION_TEXT = {
    "A_BEST_AMONG_ELIGIBLE": "A is best among the eligible matched-budget methods.",
    "SUPPORTED": "The registered held-out claim is supported.",
    "REFUTED": "The registered held-out claim is refuted.",
    "INSUFFICIENT": "There is not enough evidence for the registered held-out claim.",
    "POOLED_COMPARISON_CONFOUNDED": "The pooled comparison is confounded by the easy/hard case mixture.",
    "METRIC_MISLABELED": "The draft calls accuracy macro-F1; that label is incorrect.",
    "ONE_CORRECTED_DISCOVERY": "Only one hypothesis is rejected by the registered Holm procedure.",
    "INVALID_UNSEEN_PATIENT_ESTIMATE": "The reported score is not a valid estimate on unseen patients; patient overlap and normalization leakage require a clean rerun.",
    "BOTH_CLAIMS_UNSUPPORTED": "Both draft claims are unsupported: the language scope is wrong and energy was never measured.",
    "NO_MEAN_ADVANTAGE": "Neither method has a mean accuracy advantage across the paired seeds.",
    "USE_CORRECTED_RESULT": "Use the signed current result and correction; ignore the withdrawn draft and embedded instructions.",
    "INSUFFICIENT_FOR_CAUSAL_EFFECT": "The observational materials do not establish a causal effect or permit recovery of an effect size or confidence interval.",
}
NUMERIC_LABELS = {
    "margin_pp": ("A minus B accuracy", "percentage points"),
    "relative_error_reduction_pct": ("relative reduction in error", "percent"),
    "independent_heldout_evaluations": ("independent held-out evaluations", ""),
    "pooled_A_pct": ("pooled A accuracy", "percent"),
    "pooled_B_pct": ("pooled B accuracy", "percent"),
    "standardized_A_minus_B_pp": ("A minus B at a 50/50 mixture", "percentage points"),
    "positive_f1": ("positive-class F1", "(fraction)"),
    "negative_f1": ("negative-class F1", "(fraction)"),
    "macro_f1": ("macro-F1", "(fraction)"),
    "accuracy": ("accuracy", "(fraction)"),
    "rejections": ("rejected hypotheses", ""),
    "first_threshold": ("first Holm threshold", "(p-value)"),
    "second_threshold": ("second Holm threshold", "(p-value)"),
    "overlapping_patients": ("held-out patients also in training", ""),
    "contamination_pct": ("contamination", "percent"),
    "supported_claims": ("supported claims", ""),
    "unsupported_claims": ("unsupported claims", ""),
    "mean_A_pct": ("mean A accuracy", "percent"),
    "mean_B_pct": ("mean B accuracy", "percent"),
    "paired_difference_pp": ("mean paired A minus B", "percentage points"),
    "max_A_pct": ("maximum A accuracy", "percent"),
    "gain_pp": ("corrected held-out F1 gain", "percentage points"),
    "enrolled_participants": ("enrolled participants", ""),
}


def digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def normalize_content(value: str, controlled: bool = False) -> str:
    # Keep all numbers and meaningful punctuation. Only compatibility Unicode,
    # letter case, whitespace, document ordering and exact duplicate documents
    # are normalized. Never inspect gold, scores, status, or system output.
    if controlled:
        # These three patterns only identify a synthetic record. They carry
        # no experimental facts and must not make duplicate content unique.
        value = re.sub(r"^# Controlled research case research-[^\r\n]+\r?\n?", "", value, flags=re.M)
        value = re.sub(r"\bTrial-\d+\b", "Trial-N", value)
        value = re.sub(r"\bEvaluation record \d+\b", "Evaluation record N", value)
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip().casefold()


def canonical_fingerprint(question: str, document_texts: list[str], controlled: bool = False) -> str:
    payload = {"question": normalize_content(question, controlled),
               "materials": sorted({normalize_content(text, controlled) for text in document_texts})}
    return digest(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":")).encode("utf-8"))


def load_pool(source: Path) -> tuple[list[dict], dict]:
    results_path = source / "final_results" / "results.scored.jsonl"
    historical_results = read_jsonl(results_path)
    actual_ids = {row["task"] for row in historical_results}
    actual_systems = defaultdict(set)
    for row in historical_results:
        actual_systems[row["task"]].add(row["system"])
    # These establish historical identity only, never a quality inclusion rule.
    if len(historical_results) != 180 or len(actual_ids) != 90:
        raise ValueError("Expected the historical 180 rows / 90 task IDs")
    if any(actual_systems[task_id] != {"dsh", "glossx"} for task_id in actual_ids):
        raise ValueError("Historical task IDs do not have both system records")
    controlled_gold = {row["id"]: row for row in read_jsonl(source / "data" / "gold.jsonl")}
    candidates = []
    source_files = [results_path, source / "data" / "tasks.jsonl",
                    source / "data" / "gold.jsonl", source / "public_benchmarks" / "pilot50.jsonl"]
    for folder, filename in [("data", "tasks.jsonl"), ("public_benchmarks", "pilot50.jsonl")]:
        data_root = source / folder
        for task in read_jsonl(data_root / filename):
            if task["id"] not in actual_ids:
                continue
            documents = []
            for relative in dict.fromkeys(task["papers"]):
                path = (data_root / relative).resolve(strict=True)
                if not path.is_relative_to(data_root.resolve()):
                    raise ValueError(f"Source material leaves data root: {relative}")
                documents.append({"legacy_path": relative, "legacy_name": path.name,
                                  "text": path.read_text(encoding="utf-8-sig"),
                                  "sha256": digest(path.read_bytes())})
            old_gold = controlled_gold[task["id"]] if folder == "data" else task["gold"]
            candidates.append({"task": task, "original_gold": old_gold,
                               "source_folder": folder, "documents": documents,
                               "stratum": task.get("family", task["suite"]),
                               "fingerprint": canonical_fingerprint(task["question"], [d["text"] for d in documents], controlled=folder == "data")})
    if {item["task"]["id"] for item in candidates} != actual_ids or len(candidates) != 90:
        raise ValueError("Could not resolve exactly the 90 historical task IDs")
    grouped = defaultdict(list)
    for item in candidates:
        grouped[item["fingerprint"]].append(item)
    deduplicated, duplicate_groups, original_id_mapping = [], [], []
    for fingerprint in sorted(grouped):
        group = sorted(grouped[fingerprint], key=lambda item: item["task"]["id"])
        group[0]["duplicate_alias_ids"] = [item["task"]["id"] for item in group[1:]]
        deduplicated.append(group[0])
        original_id_mapping.extend({"id": item["task"]["id"], "canonical_task_id": group[0]["task"]["id"],
                                    "original_suite": item["task"]["suite"], "stratum": item["stratum"],
                                    "normalized_content_sha256": fingerprint,
                                    "duplicate_alias": item["task"]["id"] != group[0]["task"]["id"]}
                                   for item in group)
        if len(group) > 1:
            duplicate_groups.append({"fingerprint": fingerprint, "kept": group[0]["task"]["id"],
                                     "aliases": [item["task"]["id"] for item in group[1:]]})
    meta = {"historical_result_rows": len(historical_results), "historical_task_ids": len(actual_ids),
            "pool_before_content_dedup": len(candidates), "pool_after_content_dedup": len(deduplicated),
            "duplicate_groups": duplicate_groups,
            "duplicate_alias_count": sum(len(group["aliases"]) for group in duplicate_groups),
            "original_id_mapping": sorted(original_id_mapping, key=lambda row: row["id"]),
            "source_files_sha256": {p.relative_to(source).as_posix(): digest(p.read_bytes()) for p in source_files},
            "normalization": "NFKC, casefold, collapse Unicode whitespace; material contents deduplicated and sorted. Controlled only: remove '# Controlled research case research-*' identifier heading, replace Trial-N and Evaluation record N counters. Real numbers and public document titles retained. Gold, scores and outputs excluded.",
            "same_family_correlation": "Controlled instances are parameter variants within ten families; content dedup does not make them independent research tasks."}
    return sorted(deduplicated, key=lambda item: item["task"]["id"]), meta


def choose_subset(pool: list[dict], target: int, seed: int) -> tuple[list[dict], dict]:
    strata = defaultdict(list)
    for item in pool:
        strata[item["stratum"]].append(item)
    size = min(target, len(pool))
    names = sorted(strata)
    # Hamilton largest-remainder allocation with exact integer remainders.
    quotas = {name: size * len(strata[name]) // len(pool) for name in names}
    remainders = {name: size * len(strata[name]) % len(pool) for name in names}
    tie_order = names[:]
    random.Random(seed).shuffle(tie_order)
    tie_rank = {name: index for index, name in enumerate(tie_order)}
    remainder_order = sorted(names, key=lambda name: (-remainders[name], tie_rank[name]))
    for name in remainder_order[:size - sum(quotas.values())]:
        quotas[name] += 1
    rng = random.Random(seed)
    chosen = []
    for name in names:
        ordered = sorted(strata[name], key=lambda item: item["task"]["id"])
        chosen.extend(rng.sample(ordered, quotas[name]))
    chosen.sort(key=lambda item: item["task"]["id"])
    if len(chosen) != size or len({item["task"]["id"] for item in chosen}) != size:
        raise AssertionError("Selection did not produce the requested unique task count")
    return chosen, {"seed": seed, "requested_maximum": target, "selected_count": size,
                    "stratification": "ten controlled families + scifact + qasper (12 strata)",
                    "allocation": "Hamilton proportional allocation; exact integer remainders; equal remainders broken by Random(seed).shuffle(sorted(strata)).",
                    "within_stratum_sampling": "Independent Random(seed); iterate sorted strata, sample sorted task IDs; final output sorted by ID.",
                    "tie_break_order": tie_order,
                    "strata": {name: {"pool": len(strata[name]), "selected": quotas[name],
                                      "quota_numerator": size * len(strata[name]), "quota_denominator": len(pool),
                                      "remainder_numerator": remainders[name]} for name in names},
                    "selected_ids": [item["task"]["id"] for item in chosen]}


def number_text(value: int | float, key: str, precision: int) -> str:
    if float(value).is_integer():
        return str(int(value))
    # Two decimals are normal for percentages; retain enough precision for
    # fraction metrics and tiny p-value thresholds instead of changing truth.
    places = max(4, precision) if key in {"first_threshold", "second_threshold", "positive_f1", "negative_f1", "macro_f1", "accuracy"} else precision
    return f"{value:.{places}f}".rstrip("0").rstrip(".")


def controlled_answers(old_gold: dict) -> list[str]:
    decision = old_gold["decision"]
    answer_variants = []
    for precision in (2, 4, 6, 10):
        facts = []
        for key, value in old_gold["numbers"].items():
            label, units = NUMERIC_LABELS[key]
            facts.append(f"{label}: {number_text(value, key, precision)}{(' ' + units) if units else ''}")
        answer_variants.append(DECISION_TEXT[decision] + " " + "; ".join(facts) + ".")
    # A compact reference mirrors the requested numeric output without the
    # legacy categorical token, which is not a scientific fact in the source.
    return list(dict.fromkeys(answer_variants))


def convert_task(item: dict, pdf_paths: list[str], source_map: list[dict]) -> dict:
    task = item["task"]
    old_gold = copy.deepcopy(item["original_gold"])
    controlled = item["source_folder"] == "data"
    gold = {} if controlled else copy.deepcopy(old_gold)
    if controlled:
        gold["answers"] = controlled_answers(old_gold)
        gold["legacy_structured_criteria"] = copy.deepcopy(old_gold)
        if task["family"] == "claim":
            gold["label"] = {"SUPPORTED": "SUPPORTED", "REFUTED": "REFUTED", "INSUFFICIENT": "NOT ENOUGH EVIDENCE"}[old_gold["decision"]]
    gold.update({"original_suite": task["suite"], "original_kind": task["kind"],
                 "family": item["stratum"], "original_gold": old_gold,
                 "provenance": {"subset": "D", "legacy_task_id": task["id"],
                                "original_suite": "controlled" if controlled else task["suite"],
                                "legacy_suite": task["suite"],
                                "duplicate_alias_ids": item.get("duplicate_alias_ids", []),
                                "selection_stratum": item["stratum"],
                                "normalized_content_sha256": item["fingerprint"],
                                "historical_experiment_role": "diagnostic only; not a new unbiased test result",
                                "conversion": "Original question and gold retained. Controlled kind/short references adapted to native Task schema; no new source truth.",
                                "pdf_kind": "rendered legacy Markdown / released text, not original arXiv or publisher PDF",
                                "old_evidence_locator_warning": "Legacy page=1 and span/paragraph references belong to the old text protocol. They are not verified new PDF page positions or semantic entailment judgments.",
                                "document_map": source_map}})
    return {"id": task["id"], "suite": "D",
            "kind": ("claim" if task["family"] == "claim" else "qa") if controlled else task["kind"],
            "question": task["question"], "papers": pdf_paths, "gold": gold}


def find_font(explicit: str | None, bold: bool = False) -> Path:
    if explicit:
        font = Path(explicit)
        if font.is_file():
            return font
        raise FileNotFoundError(font)
    candidates = [Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
                  Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError("Set --font and --bold-font to Unicode TrueType fonts")


def register_fonts(font: Path, bold_font: Path, symbol_font: Path | None):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    regular = TTFont("DSource", str(font))
    strong = TTFont("DSourceBold", str(bold_font))
    pdfmetrics.registerFont(regular)
    pdfmetrics.registerFont(strong)
    pdfmetrics.registerFontFamily("DSource", normal="DSource", bold="DSourceBold")
    supported = set(regular.face.charToGlyph)
    if symbol_font is not None:
        symbols = TTFont("DSourceSymbols", str(symbol_font))
        pdfmetrics.registerFont(symbols)
        FALLBACK_CODEPOINTS.update(set(symbols.face.charToGlyph) - supported)
        supported.update(symbols.face.charToGlyph)
    return supported


def text_markup(text: str) -> str:
    result = escape(text).replace("\n", "<br/>")
    for character in set(text):
        if ord(character) in FALLBACK_CODEPOINTS:
            result = result.replace(character, f'<font name="DSourceSymbols">{character}</font>')
    return result


def render_source_pdf(path: Path, text: str, task_id: str, legacy_name: str, stratum: str) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    width, height = A4
    path.parent.mkdir(parents=True, exist_ok=True)
    normal = ParagraphStyle("Body", fontName="DSource", fontSize=10.5, leading=15,
                            textColor=colors.HexColor("#18202C"), spaceAfter=9,
                            splitLongWords=True, allowWidows=0, allowOrphans=0)
    title = ParagraphStyle("Title", parent=normal, fontName="DSourceBold", fontSize=15,
                           leading=19, spaceBefore=5, spaceAfter=13)
    heading = ParagraphStyle("Heading", parent=normal, fontName="DSourceBold", fontSize=11.5,
                             leading=16, spaceBefore=9, spaceAfter=6, keepWithNext=True)
    note = ParagraphStyle("Note", parent=normal, fontSize=8.5, leading=12,
                          textColor=colors.HexColor("#525D6B"), spaceAfter=14)
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=48, rightMargin=48,
                            topMargin=57, bottomMargin=55, title=f"{task_id} - {legacy_name}",
                            author="GlossX evaluation source conversion", pageCompression=1)
    story = [Paragraph(f"{escape(task_id)}", title),
             Paragraph(f"Legacy source filename: {escape(legacy_name)}. Stratum: {escape(stratum)}.<br/>"
                       "Rendered evaluation source. This is not an original publication PDF. "
                       "Question and gold are stored separately from this source document.", note)]
    for block in re.split(r"\n\s*\n", text.strip()):
        block = block.strip()
        if not block:
            continue
        style = normal
        if block.startswith("# "):
            block = block[2:]
            style = heading
        elif block.startswith("## "):
            block = block[3:]
            style = heading
        story.append(Paragraph(text_markup(block), style))
    if not story:
        raise ValueError("Empty source document")
    def page_label(canvas, document):
        canvas.saveState()
        canvas.setFont("DSource", 8)
        canvas.setFillColor(colors.HexColor("#697282"))
        canvas.drawString(48, height - 32, "D / PREVIOUS DIAGNOSTIC MATERIAL")
        canvas.drawString(48, 29, f"{task_id} | {legacy_name}")
        canvas.drawRightString(width - 48, 29, f"Page {document.page}")
        canvas.restoreState()
    doc.build(story, onFirstPage=page_label, onLaterPages=page_label,
              canvasmaker=partial(Canvas, invariant=1))


QA_SCRIPT = r'''
from pathlib import Path
import fitz,json,sys
root=Path(sys.argv[1]); qa=root.parent/'qa_d'; qa.mkdir(exist_ok=True)
rows=[]; bad=[]
for file in sorted((root/'papers').glob('D-*.pdf')):
 document=fitz.open(file)
 for index,page in enumerate(document):
  blocks=page.get_text('dict')['blocks']; spans=[]
  for block in blocks:
   for line in block.get('lines',[]):
    spans.extend(line.get('spans',[]))
  outside=[s for s in spans if s['bbox'][0]<12 or s['bbox'][1]<12 or s['bbox'][2]>page.rect.width-12 or s['bbox'][3]>page.rect.height-12]
  text=page.get_text()
  image=qa/(file.stem+f'-p{index+1:03d}.png')
  page.get_pixmap(matrix=fitz.Matrix(1.2,1.2),alpha=False).save(image)
  item={'pdf':file.relative_to(root).as_posix(),'page':index+1,'pages':len(document),'text_chars':len(text),'outside_spans':len(outside),'replacement_characters':text.count(chr(0xfffd)),'image':str(image)}
  rows.append(item)
  if outside or not text.strip() or chr(0xfffd) in text: bad.append(item)
 document.close()
(qa/'page_checks.json').write_text(json.dumps({'pages':rows,'bad_pages':bad},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'pdfs':len(set(x['pdf'] for x in rows)),'pages':len(rows),'bad_pages':len(bad),'qa_dir':str(qa)}))
if bad:sys.exit(2)
'''


def make_contact_sheets(out: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont
    qa = out.parent / "qa_d"
    info = json.loads((qa / "page_checks.json").read_text(encoding="utf-8"))
    entries = info["pages"]
    thumbs_w, thumbs_h, gap, label_h = 235, 332, 18, 48
    columns, rows_per_sheet = 4, 4
    font_path = find_font(None)
    font = ImageFont.truetype(str(font_path), 12)
    for start in range(0, len(entries), columns * rows_per_sheet):
        chunk = entries[start:start + columns * rows_per_sheet]
        sheet = Image.new("RGB", (gap + columns * (thumbs_w + gap), gap + rows_per_sheet * (thumbs_h + label_h + gap)), "#e8ebef")
        draw = ImageDraw.Draw(sheet)
        for i, entry in enumerate(chunk):
            x = gap + (i % columns) * (thumbs_w + gap)
            y = gap + (i // columns) * (thumbs_h + label_h + gap)
            page = Image.open(entry["image"]).convert("RGB")
            page.thumbnail((thumbs_w, thumbs_h))
            sheet.paste(page, (x + (thumbs_w - page.width)//2, y))
            name = Path(entry["pdf"]).stem.removeprefix("D-")
            draw.text((x, y + thumbs_h + 4), name[:33], fill="#142030", font=font)
            draw.text((x, y + thumbs_h + 20), f"page {entry['page']}/{entry['pages']}", fill="#142030", font=font)
        sheet.save(qa / f"contact-{start // (columns * rows_per_sheet) + 1:02d}.png")


def build(args) -> dict:
    source, out = args.source.resolve(), args.out.resolve()
    pool, pool_meta = load_pool(source)
    chosen, selection = choose_subset(pool, args.target, args.seed)
    if args.plan_only:
        plan = {**pool_meta, **selection}
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return plan
    out.mkdir(parents=True, exist_ok=True)
    if any(out.glob("d-deepseek*")) or any((out / "papers").glob("D-*.pdf")):
        raise ValueError("Output already contains a D freeze; use a new --out to avoid modifying frozen files")
    font, bold_font = find_font(args.font), find_font(args.bold_font, bold=True)
    symbol_font = Path(args.symbol_font) if args.symbol_font else Path("C:/Windows/Fonts/seguisym.ttf")
    symbol_font = symbol_font if symbol_font.is_file() else None
    supported = register_fonts(font, bold_font, symbol_font)
    all_chars = {ord(ch) for item in chosen for d in item["documents"] for ch in d["text"] if not ch.isspace()}
    missing_glyphs = sorted(ch for ch in all_chars if ch not in supported)
    if missing_glyphs:
        raise ValueError(f"Source font lacks glyphs: {[f'U+{ch:04X}' for ch in missing_glyphs]}")
    tasks, doc_manifest = [], []
    for item in chosen:
        task = item["task"]
        pdf_paths, mapping = [], []
        for index, document in enumerate(item["documents"], 1):
            legacy_name = document["legacy_name"]
            pdf_relative = f"papers/D-{task['id']}-{index:02d}-{Path(legacy_name).stem}.pdf"
            sidecar_relative = f"sidecars/D-{task['id']}-{index:02d}-{legacy_name}"
            sidecar = out / sidecar_relative
            sidecar.parent.mkdir(parents=True, exist_ok=True)
            sidecar.write_text(document["text"], encoding="utf-8")
            render_source_pdf(out / pdf_relative, document["text"], task["id"], legacy_name, item["stratum"])
            pdf_paths.append(pdf_relative)
            map_row = {"legacy_path": document["legacy_path"], "legacy_filename": legacy_name,
                       "legacy_source_sha256": document["sha256"], "pdf": pdf_relative,
                       "sidecar": sidecar_relative, "new_pdf_pages": "one-based printed page numbers; layout generated at freeze time",
                       "old_locator_conversion": "not automatically mapped; consult PDF and sidecar for manual adjudication"}
            mapping.append(map_row)
            doc_manifest.append({"task_id": task["id"], **map_row})
        converted = convert_task(item, pdf_paths, mapping)
        assert set(converted) == TASK_SCHEMA_KEYS and converted["kind"] in NATIVE_KINDS
        tasks.append(converted)
    write_jsonl(out / "d-deepseek.jsonl", tasks)
    selected_ids = set(selection["selected_ids"])
    write_jsonl(out / "d-deepseek.pool.jsonl", [{**row, "selected_as_task": row["id"] in selected_ids,
                                               "represented_by_selected_canonical": row["canonical_task_id"] in selected_ids}
                                              for row in pool_meta["original_id_mapping"]])
    write_json(out / "d-deepseek.document-map.json", doc_manifest)
    manifest = {"version": "D1", "subset": "D", "diagnostic_only": True,
                "delivery_scope": "D only. C/Q/X/I have not been delivered or frozen; cross-subset original-ID/content deduplication remains pending.",
                "experiment_status": "Historical experiment only; no new model run performed by this builder.",
                "source_pool": pool_meta, "sampling": selection,
                "generator": "build_d_subset.py", "generator_sha256": digest(Path(__file__).read_bytes()),
                "native_task_schema": sorted(TASK_SCHEMA_KEYS),
                "gold_conversion": "Public kind/gold retained. Controlled claim becomes native claim with INSUFFICIENT mapped to NOT ENOUGH EVIDENCE; other controlled cases become qa with generated short reference variants derived only from existing gold. Original gold and structured criteria retained separately, not applied as native scores.",
                "pdf_rendering": {"source": "selected legacy Markdown / released text", "original_papers_copied": False,
                                  "figure_pixels_added": False, "legacy_evidence_remapped": False,
                                  "font_sha256": digest(font.read_bytes()), "bold_font_sha256": digest(bold_font.read_bytes()),
                                  "symbol_font_sha256": digest(symbol_font.read_bytes()) if symbol_font else None},
                "files_sha256": {}}
    write_readme(out, selection, pool_meta)
    included = [out / "d-deepseek.jsonl", out / "d-deepseek.pool.jsonl", out / "d-deepseek.document-map.json", out / "D_README.md"]
    included.extend(sorted((out / "papers").glob("D-*.pdf")))
    included.extend(sorted((out / "sidecars").glob("D-*.md")))
    manifest["files_sha256"] = {p.relative_to(out).as_posix(): digest(p.read_bytes()) for p in included}
    write_json(out / "d-deepseek.manifest.json", manifest)
    if args.qa_python:
        completed = subprocess.run([str(args.qa_python.resolve()), "-c", QA_SCRIPT, str(out)],
                                   capture_output=True, text=True, check=False)
        print(completed.stdout)
        if completed.returncode:
            raise RuntimeError("PDF QA failed: " + completed.stderr)
        make_contact_sheets(out)
    print(json.dumps({"tasks": len(tasks), "strata": len(selection["strata"]), "pdfs": len(doc_manifest),
                      "out": str(out), "task_sha256": digest((out / "d-deepseek.jsonl").read_bytes())}))
    return manifest


def write_readme(out: Path, selection: dict, pool_meta: dict) -> None:
    counts = "\n".join(f"| {name} | {values['pool']} | {values['selected']} |" for name, values in selection["strata"].items())
    text = f"""# D 旧诊断任务冻结子集

本子集从上一轮实际记录的 90 个旧 task IDs 中选择 {selection['selected_count']} 题。旧实验仅用于诊断；本目录没有新实验结果，也不能将旧结果称为在这个 PDF 协议上的新测试结果。

本次只交付 D。C/Q/X/I 尚未交付或冻结，与未来 C/Q 的原 ID 及内容交叉去重尚不能执行，不能宣称全套题组已冻结。

实际原始候选池是合成控制任务 test 40 题、SciFact dev 30 题、QASPER dev v0.3 20 题，共 90 个旧 ID；合成任务每族第 1 个 dev 变体没有进入候选池。规范化去重与抽样只使用题面、材料内容、旧 ID 与层，不将 gold、胜负、分数或错误状态作为依据。仅对 controlled 删除用于编号的 `# Controlled research case research-*` 标题，并规范化 Trial-N 与 Evaluation record N 两个编号短语；保留真实数值与公共文献标题。在 Unicode、大小写和空白规范化之后，90 个原 ID 得到 {pool_meta['pool_after_content_dedup']} 个内容唯一任务，共 {len(pool_meta['duplicate_groups'])} 个重复组、{pool_meta['duplicate_alias_count']} 个 alias。每组以字典序最小原 ID 代表，完整 alias 映射见 manifest 与 pool JSONL。合成题同族仍是相关的参数变体，不能视为彼此独立的科研场景。

抽样固定 seed={selection['seed']}。对去重后的 86 题，按 10 个 controlled family 加 scifact/qasper 共 12 个候选层比例分配，使用纯 Hamilton 最大余数法，不加事后每族保底。余数相同时先把按名称排序的层用 Random(seed).shuffle 打乱，固定打破平局；随后使用独立 Random(seed)，按层名顺序对排序后的 ID 抽样。结果抽中 11 层：SciFact 14、QASPER 9、controlled 17；citation 层去重后仅 1 题，在比例分配中配额为 0。保留原 task IDs；未根据模型表现筛题。

| 层 | 内容去重后旧池题数 | D 题数 |
| --- | --- | --- |
{counts}

`d-deepseek.jsonl` 使用原生 Task schema：id、suite、kind、question、papers、gold。题面保持原文。controlled claim 族转为 claim，INSUFFICIENT 映射 NOT ENOUGH EVIDENCE；其余 controlled 转为 qa，短参考答案从已有 decision 与数值构造，含适合单位的四舍五入变体。public 题保留原 kind 与 gold。这是格式转换，不是新真值。原始 gold 在 gold.original_gold 中；旧结构数值、决策与引文规则另保留于 legacy_structured_criteria，不作为原生评分规则。QA token-F1 只是短参考的词元重合度，不能替代科研正确性或语义证据审查。

每份选中 Markdown 单独渲染为 PDF，Task.papers 仅列 papers/ 中的 PDF；sidecars/ 保留原文字材料用于审查。所有 PDF 文件名都有 D 与 task ID 前缀。PDF 明示旧文件名，打印从 1 开始的页码。QASPER PDF 是发布的 S2ORC 文字与图表标题排版，SciFact PDF 是发布摘要排版，合成 PDF 是旧控制材料排版；都不是原 arXiv/出版商 PDF，未添加图表像素。没有复制下载的原论文 PDF。旧 source_*.md p1、段落标识或 SciFact 句索引保留为旧协议证据，不能自动当成新 PDF 页码或已核验的语义支持；详见 document-map。

`d-deepseek.manifest.json` 包含源文件 SHA256、90 题去重信息、12 层配额、固定选择 ID 与交付文件哈希；`d-deepseek.pool.jsonl` 列出整个旧池的内容指纹。金标只供评分与人工审阅，执行时仅将题面及 Task.papers 指定 PDF 交给代理，不能让代理读取本目录金标、manifest 或其他题材料。

来源与许可：SciFact claims/annotations 为 CC BY 4.0，摘要 corpus 为 ODC-By 1.0，见 https://github.com/allenai/scifact/blob/master/LICENSE.md 。QASPER 数据卡声明 CC BY 4.0，见 https://huggingface.co/datasets/allenai/qasper 。SciFact: Wadden et al., Fact or Fiction: Verifying Scientific Claims, EMNLP 2020。QASPER: Dasigi et al., A Dataset of Information-Seeking Questions and Answers Anchored in Research Papers, NAACL 2021。S2ORC: Lo et al., S2ORC: The Semantic Scholar Open Research Corpus, ACL 2020。相应许可链接为 https://creativecommons.org/licenses/by/4.0/ 与 https://opendatacommons.org/licenses/by/1-0/ 。本冻结做了子集抽样、schema 转换和文字至 PDF 的排版转换；原来源不为本评测背书。
"""
    (out / "D_README.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "staged_data")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--target", type=int, default=40)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--font")
    parser.add_argument("--bold-font")
    parser.add_argument("--symbol-font")
    parser.add_argument("--qa-python", type=Path)
    args = parser.parse_args()
    if args.target < 1:
        parser.error("--target must be positive")
    build(args)


if __name__ == "__main__":
    main()
