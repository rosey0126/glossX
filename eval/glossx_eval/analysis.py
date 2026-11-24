"""Secondary analyses for the report, computed from the same frozen-v1 result rows.

    python -m glossx_eval.analysis runs/frozen-v1/*/results-*.jsonl \
        --items data/frozen-v1 --route data/route100.jsonl --out ../report/latex/generated

Nothing here calls a model. Every table is written as a LaTeX snippet that the
report ``\\input``s when it exists, so re-running this script after new runs
updates the report:

* ``efficiency.tex``  per agent: success rate, quality, latency, tokens, tool calls
* ``tradeoff.tex``    pgfplots scatter of quality against latency, one point per agent
* ``breakdown.tex``   score by claim label and by research-task family (where agents fail)
* ``variance.tex``    repeated runs: mean, spread across repeats, pass^k, item agreement
* ``routing.tex``     GlossX routing confusion and accuracy by request language
* ``internals.tex``   GlossX stop reasons and claims removed by the verifier
"""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

PARTS = (("C35.jsonl", "Claim"), ("Q20.jsonl", "ShortQA"), ("x10.jsonl", "CrossPaper"),
         ("I10.jsonl", "Injection"), ("d-deepseek.jsonl", "Research"))
DISPLAY = {"glossx": "GlossX", "codex": "Codex CLI", "paperqa2": "PaperQA2", "gpt-researcher": "GPT Res.",
           "gpt_researcher": "GPT Res.", "glossx-noverify": "$-$verify", "glossx-noreflect": "$-$reflect",
           "gloss-chat": "Gloss chat", "dsh": "DSH"}
ORDER = ["glossx", "codex", "paperqa2", "gpt-researcher", "gpt_researcher", "glossx-noverify",
         "glossx-noreflect", "gloss-chat", "dsh"]
LABELS = ("SUPPORTED", "REFUTED", "NOT ENOUGH EVIDENCE")
SHORT_WF = {None: "generic", "workflow.literature-review": "review", "workflow.cross-paper-qa": "cross-QA",
            "workflow.claim-verification": "claim", "workflow.tutoring": "tutor",
            "workflow.reproduction": "repro", "workflow.team-review": "team"}


# -- loading ---------------------------------------------------------------------------
def read_jsonl(paths: Iterable[Path]) -> list[dict]:
    rows = []
    for path in paths:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("//"):
                rows.append(json.loads(line))
    return rows


def item_index(items_dir: Path) -> dict[str, dict]:
    """task id -> {part, family, gold}; family is the research-task family or source suite."""
    index = {}
    for name, part in PARTS:
        path = items_dir / name
        if not path.exists():
            continue
        for task in read_jsonl([path]):
            gold = task.get("gold") or {}
            family = gold.get("family") or (task["id"].split("-")[0] if part == "Research" else part)
            index[task["id"]] = {"part": part, "family": family, "gold": gold, "kind": task.get("kind")}
    return index


def system_key(row: dict) -> str:
    return row.get("system") or "?"


def model_of(row: dict, path_model: str | None) -> str:
    return row.get("model") or path_model or "?"


def item_score(row: dict) -> float:
    """One number in [0, 1] per run: the task's primary score; failed runs score zero."""
    s = row.get("scores") or {}
    if not s.get("execution_ok", True):
        return 0.0
    for key in ("score", "rubric", "points"):
        if isinstance(s.get(key), (int, float)):
            return float(s[key])
    if "label_correct" in s:
        return float(bool(s["label_correct"]))
    if isinstance(s.get("f1"), (int, float)):
        return float(s["f1"])
    if "route_correct" in s:
        return float(bool(s["route_correct"]))
    return 0.0


# -- small stats -----------------------------------------------------------------------
def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def fmt(x: float, pct: bool = True, nd: int = 1) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    return f"{100 * x:.{nd}f}" if pct else f"{x:.{nd}f}"


def shade(x: float) -> str:
    """Cell colour for a score in [0, 1] (white to blue), readable in print."""
    if x is None or math.isnan(x):
        return ""
    return f"\\cellcolor{{blue!{int(round(35 * x))}}}"


def systems_in(rows: list[dict]) -> list[str]:
    present = {system_key(r) for r in rows}
    return [s for s in ORDER if s in present] + sorted(present - set(ORDER))


def tex_escape(text: str) -> str:
    return re.sub(r"([_&%#])", r"\\\1", text)


# -- analyses --------------------------------------------------------------------------
def per_task_means(rows: list[dict]) -> dict[str, dict[str, float]]:
    """system -> task -> score averaged over repeats."""
    acc: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        acc[system_key(r)][r["task"]].append(item_score(r))
    return {s: {t: mean(v) for t, v in tasks.items()} for s, tasks in acc.items()}


def efficiency(rows: list[dict], index: dict[str, dict]) -> tuple[str, dict[str, tuple[float, float]]]:
    doc = [r for r in rows if r["task"] in index]
    by_sys: dict[str, list[dict]] = defaultdict(list)
    for r in doc:
        by_sys[system_key(r)].append(r)
    scores = per_task_means(doc)
    points = {}
    lines = []
    for s in systems_in(doc):
        rs = by_sys[s]
        ok = [r for r in rs if not (r.get("output") or {}).get("error")]
        # quality: mean over parts of the mean item score, so every part weighs the same
        part_scores = defaultdict(list)
        for task, v in scores[s].items():
            part_scores[index[task]["part"]].append(v)
        quality = mean([mean(v) for v in part_scores.values()])
        lat = mean([(r["output"] or {}).get("latency_s") or 0.0 for r in ok])
        toks = [((r["output"] or {}).get("tokens_in") or 0) + ((r["output"] or {}).get("tokens_out") or 0) for r in ok]
        toks = [t for t in toks if t]
        calls = [(r["output"] or {}).get("tool_calls") for r in ok if (r["output"] or {}).get("tool_calls") is not None]
        points[s] = (lat, quality)
        lines.append(" & ".join([DISPLAY.get(s, tex_escape(s)), f"{len(ok)}/{len(rs)}", fmt(quality),
                                 fmt(lat, False), f"{mean(toks) / 1000:.1f}k" if toks else "n/a",
                                 fmt(mean(calls), False) if calls else "n/a"]) + " \\\\")
    body = ("\\begin{tabular}{@{}lrrrrr@{}}\n\\toprule\n"
            "Agent & Runs completed & Quality & Latency (s) & Tokens / run & Tool calls / run \\\\\n\\midrule\n"
            + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n")
    return body, points


def tradeoff(points: dict[str, tuple[float, float]]) -> str:
    coords = "\n".join(f"  ({lat:.2f},{100 * q:.2f}) [{DISPLAY.get(s, tex_escape(s))}]"
                       for s, (lat, q) in points.items() if not (math.isnan(lat) or math.isnan(q)))
    return ("\\begin{tikzpicture}\n\\begin{axis}[width=0.62\\linewidth, height=4.2cm, xlabel={Mean latency (s)},"
            " ylabel={Quality (\\%)}, nodes near coords, point meta=explicit symbolic,"
            " every node near coord/.append style={font=\\tiny, anchor=west}, tick label style={font=\\scriptsize},"
            " label style={font=\\scriptsize}, xmin=0, enlarge x limits={upper, value=0.25}]\n"
            "\\addplot[only marks, mark=*, mark size=1.6pt, color=blue!70!black] coordinates {\n"
            + coords + "\n};\n\\end{axis}\n\\end{tikzpicture}\n")


def breakdown(rows: list[dict], index: dict[str, dict]) -> str:
    doc = [r for r in rows if r["task"] in index]
    scores = per_task_means(doc)
    systems = systems_in(doc)
    groups: list[tuple[str, list[str]]] = []
    for label in LABELS:
        tasks = [t for t, i in index.items() if i["part"] == "Claim" and i["gold"].get("label") == label]
        groups.append((f"Claim: gold {label.title().replace('Not Enough Evidence', 'NEE')}", tasks))
    def source(info: dict) -> str:
        fam = str(info["family"]).lower()
        return {"scifact": "SciFact claims", "qasper": "QASPER questions"}.get(fam, "multi-source audits")
    fams = Counter(source(i) for i in index.values() if i["part"] == "Research")
    for fam, n in sorted(fams.items(), key=lambda kv: (-kv[1], kv[0])):
        tasks = [t for t, i in index.items() if i["part"] == "Research" and source(i) == fam]
        groups.append((f"Research: {fam} ($n={n}$)", tasks))
    lines = []
    for name, tasks in groups:
        cells = []
        for s in systems:
            vals = [scores[s][t] for t in tasks if t in scores[s]]
            v = mean(vals) if vals else float("nan")
            cells.append(f"{shade(v)}{fmt(v, nd=0)}")
        lines.append(name + " & " + " & ".join(cells) + " \\\\")
    # NEE answered as REFUTED: the "absence is not contradiction" error
    conf = []
    for s in systems:
        nee = [r for r in doc if system_key(r) == s and index[r["task"]]["part"] == "Claim"
               and index[r["task"]]["gold"].get("label") == "NOT ENOUGH EVIDENCE"]
        bad = sum(1 for r in nee if (r.get("scores") or {}).get("pred_label") == "REFUTED")
        conf.append(f"{bad}/{len(nee)}" if nee else "n/a")
    lines.append("\\midrule\nNEE answered as REFUTED & " + " & ".join(conf) + " \\\\")
    head = "Item group & " + " & ".join(DISPLAY.get(s, tex_escape(s)) for s in systems) + " \\\\"
    return ("\\begin{tabular}{@{}l" + "r" * len(systems) + "@{}}\n\\toprule\n" + head + "\n\\midrule\n"
            + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n")


def variance(rows: list[dict], index: dict[str, dict], threshold: float = 0.5) -> str:
    by = defaultdict(lambda: defaultdict(dict))  # system -> task -> repeat -> score
    for r in rows:
        if r["task"] in index:
            by[system_key(r)][r["task"]][r.get("repeat", 0)] = item_score(r)
    lines = []
    for s in systems_in(rows):
        tasks = {t: reps for t, reps in by[s].items() if len(reps) >= 2}
        if not tasks:
            continue
        k = min(len(v) for v in tasks.values())
        rep_ids = sorted({rid for v in tasks.values() for rid in v})[:k]
        per_rep = [mean([tasks[t][rid] for t in tasks if rid in tasks[t]]) for rid in rep_ids]
        sd = statistics.stdev(per_rep) if len(per_rep) > 1 else 0.0
        pass1 = mean([float(tasks[t][rid] >= threshold) for t in tasks for rid in rep_ids if rid in tasks[t]])
        passk = mean([float(all(tasks[t].get(rid, 0) >= threshold for rid in rep_ids)) for t in tasks])
        agree = mean([float(len({tasks[t].get(rid, 0) >= threshold for rid in rep_ids}) == 1) for t in tasks])
        lines.append(" & ".join([DISPLAY.get(s, tex_escape(s)), str(len(tasks)), str(k), fmt(mean(per_rep)),
                                 fmt(sd), fmt(pass1), fmt(passk), fmt(agree)]) + " \\\\")
    if not lines:
        return "% no repeated runs yet\n"
    return ("\\begin{tabular}{@{}lrrrrrrr@{}}\n\\toprule\n"
            "Agent & Items & $k$ & Mean & SD across runs & pass@1 & pass\\textasciicircum$k$ & Same outcome \\\\\n"
            "\\midrule\n" + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n")


def routing(rows: list[dict], route_items: list[dict]) -> str:
    gold = {t["id"]: (t.get("gold") or {}).get("workflow") for t in route_items}
    lang = {t["id"]: "zh" if re.search("[\u4e00-\u9fff]", t["question"]) else "en" for t in route_items}
    rs = [r for r in rows if r["task"] in gold and system_key(r) == "glossx"]
    if not rs:
        return "% no routing runs yet\n"
    names = list(SHORT_WF)
    m = Counter()
    for r in rs:
        decision = ((r.get("output") or {}).get("raw") or {}).get("route") or {}
        pred = decision.get("workflow") if isinstance(decision, dict) and not decision.get("failed") else "failed"
        m[(gold[r["task"]], pred if pred in SHORT_WF or pred == "failed" else "other")] += 1
    cols = names + ["failed"]
    head = "Gold $\\downarrow$ / predicted $\\rightarrow$ & " + " & ".join(SHORT_WF.get(c, c) for c in cols) + " \\\\"
    lines = []
    for g in names:
        cells = [(f"\\textbf{{{m[(g, c)]}}}" if c == g else (str(m[(g, c)]) if m[(g, c)] else "")) for c in cols]
        lines.append(SHORT_WF[g] + " & " + " & ".join(cells) + " \\\\")
    acc = {}
    for L in ("en", "zh"):
        sub = [r for r in rs if lang[r["task"]] == L]
        acc[L] = (sum(bool((r.get("scores") or {}).get("route_correct")) for r in sub), len(sub))
    total = sum(v[0] for v in acc.values()), sum(v[1] for v in acc.values())
    foot = (f"\\multicolumn{{{len(cols) + 1}}}{{@{{}}l}}{{Accuracy: {total[0]}/{total[1]}; English "
            f"{acc['en'][0]}/{acc['en'][1]}, Chinese {acc['zh'][0]}/{acc['zh'][1]}.}} \\\\")
    return ("\\begin{tabular}{@{}l" + "r" * len(cols) + "@{}}\n\\toprule\n" + head + "\n\\midrule\n"
            + "\n".join(lines) + "\n\\midrule\n" + foot + "\n\\bottomrule\n\\end{tabular}\n")


def internals(rows: list[dict], index: dict[str, dict], run_dirs: list[Path]) -> str:
    rs = [r for r in rows if r["task"] in index and system_key(r) in ("glossx", "glossx-noverify", "glossx-noreflect")]
    if not rs:
        return "% no GlossX runs yet\n"
    stops: dict[str, Counter] = defaultdict(Counter)
    removed: dict[str, list[int]] = defaultdict(list)
    for r in rs:
        raw = (r.get("output") or {}).get("raw") or {}
        stops[system_key(r)][raw.get("stop_reason") or ("error" if (r["output"] or {}).get("error") else "n/a")] += 1
        trace = None
        for d in run_dirs:
            p = d / "work" / system_key(r) / f"{r['task']}-r{r.get('repeat', 0)}" / "glossx-run.json"
            if p.exists():
                trace = json.loads(p.read_text(encoding="utf-8"))
                break
        if trace:
            result = (trace.get("run") or trace).get("result") or {}
            removed[system_key(r)].append(len(result.get("rejected_claims") or []))
    reasons = sorted({k for c in stops.values() for k in c}, key=lambda k: -sum(c[k] for c in stops.values()))
    systems = [s for s in ORDER if s in stops]
    lines = [f"Stop: \\code{{{tex_escape(k)}}} & " + " & ".join(str(stops[s][k]) for s in systems) + " \\\\" for k in reasons]
    lines.append("\\midrule\nClaims removed by verifier / answer & " + " & ".join(
        fmt(mean(removed[s]), False, 2) if removed[s] else "n/a" for s in systems) + " \\\\")
    lines.append("Answers with $\\geq$1 claim removed & " + " & ".join(
        f"{sum(1 for x in removed[s] if x)}/{len(removed[s])}" if removed[s] else "n/a" for s in systems) + " \\\\")
    head = " & " + " & ".join(DISPLAY.get(s, s) for s in systems) + " \\\\"
    return ("\\begin{tabular}{@{}l" + "r" * len(systems) + "@{}}\n\\toprule\n" + head + "\n\\midrule\n"
            + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("results", nargs="+", help="result JSONL files from glossx_eval.run (and adapters)")
    ap.add_argument("--items", default="data/frozen-v1")
    ap.add_argument("--route", default="data/route100.jsonl")
    ap.add_argument("--out", default="../report/latex/generated")
    args = ap.parse_args(argv)
    paths = [Path(p) for p in args.results]
    rows = read_jsonl(paths)
    index = item_index(Path(args.items))
    route_items = read_jsonl([Path(args.route)]) if Path(args.route).exists() else []
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    eff, points = efficiency(rows, index)
    files = {"efficiency.tex": eff, "tradeoff.tex": tradeoff(points), "breakdown.tex": breakdown(rows, index),
             "variance.tex": variance(rows, index), "routing.tex": routing(rows, route_items),
             "internals.tex": internals(rows, index, sorted({p.parent for p in paths}))}
    header = "% generated by python -m glossx_eval.analysis; do not edit by hand\n"
    for name, text in files.items():
        (out / name).write_text(header + text, encoding="utf-8")
    print(f"wrote {', '.join(files)} to {out} from {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
