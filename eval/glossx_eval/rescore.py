"""Re-score saved runs with the current answer-field rule, without re-running agents.

    python -m glossx_eval.rescore runs/frozen-v1/*/results-*.jsonl --tasks data/frozen-v1/frozen-v1.jsonl

Rows whose final message had no JSON answer object are re-parsed from the saved
text (``output.raw.text``): an explicit ``Answer:`` line becomes the answer
field, the same rule for every system. Only answer-dependent scores (token F1,
exact match, fault checks) are recomputed; labels, citation checks and the
saved trace are kept. Rows are rewritten in place and the run is idempotent.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from . import faults, metrics
from .systems import output_from_text
from .tasks import load_tasks

SCORING = "answer-line-v1"


def rescore_row(row: dict, task) -> dict:
    out, scores = row.get("output") or {}, row.get("scores") or {}
    raw = out.get("raw") or {}
    if raw.get("format_ok") is not False or "text" not in raw:
        row["scoring"] = SCORING
        return row
    fresh = output_from_text(raw["text"])
    out["answer"] = fresh.answer
    out["raw"] = {**raw, **{k: v for k, v in fresh.raw.items() if k in ("answer_source", "full_answer")}}
    if "full_answer" not in fresh.raw:
        out["raw"].pop("full_answer", None)
    ok = scores.get("execution_ok", not out.get("error"))
    if task is not None and task.kind == "qa" and task.gold.get("answers"):
        scores["f1"] = metrics.best_f1(fresh.answer, task.gold["answers"]) if ok else 0.0
        scores["em"] = metrics.exact_match(fresh.answer, task.gold["answers"]) if ok else 0.0
    if task is not None and task.gold.get("fault"):
        scores.update(faults.score(task, fresh.raw.get("full_answer") or fresh.answer))
    scores["answer_source"] = fresh.raw.get("answer_source")
    row["output"], row["scores"], row["scoring"] = out, scores, SCORING
    return row


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="glossx_eval.rescore")
    ap.add_argument("results", nargs="+")
    ap.add_argument("--tasks", required=True)
    args = ap.parse_args(argv)
    tasks = {t.id: t for t in load_tasks(args.tasks)}
    summary: Counter = Counter()
    for path in map(Path, args.results):
        rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        for row in rows:
            rescore_row(row, tasks.get(row.get("task")))
            summary[(row.get("system"), (row.get("scores") or {}).get("answer_source", "json"))] += 1
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    for (system, source), n in sorted(summary.items(), key=str):
        print(f"{system}\t{source}\t{n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
