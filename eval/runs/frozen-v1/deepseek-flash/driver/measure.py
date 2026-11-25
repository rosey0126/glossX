"""Local interpretation of frozen rows. No network calls."""
from collections import Counter
import json
from pathlib import Path
from itertools import combinations
from statistics import fmean, median, stdev
import sys

from glossx_eval.metrics import bootstrap_ci, label_scores, normalize, token_f1

parts = {"scifact": "C", "qasper": "Q", "cross-paper-qa": "X", "scifact+inject": "I",
         "qasper+inject": "I", "D": "D"}
systems = ["glossx", "dsh"]


def primary(row):
    score = row["scores"]
    if row["suite"] == "cross-paper-qa":
        return None
    return float(score["label_correct"] if "label_correct" in score else score["f1"])


def describe(rows):
    ok = [r for r in rows if r["scores"]["execution_ok"]]
    group = {k: [r for r in rows if parts[r["suite"]] == k] for k in "CQXID"}
    latencies = [r["output"]["latency_s"] for r in ok]
    cited = sum(r["scores"]["citations"] for r in rows)
    return {
        "attempted": len(rows), "successes": len(ok),
        "by_batch": {k: [sum(r["scores"]["execution_ok"] for r in rs), len(rs)]
                     for k, rs in group.items()},
        "error_types": dict(Counter(r["scores"]["error_kind"] for r in rows if not r["scores"]["execution_ok"])),
        "C_macro_F1": label_scores([(r["scores"]["pred_label"], r["scores"]["gold_label"])
                                    for r in group["C"]])["macro_f1"],
        "Q_mean_F1": fmean(primary(r) for r in group["Q"]),
        "Q_format_ok": sum(r["scores"].get("format_ok", False) for r in group["Q"]),
        "D_mean_task_score": fmean(primary(r) for r in group["D"]),
        "I_canary_followed": sum(r["scores"]["injection_followed"] for r in group["I"]),
        "citations_located": sum(r["scores"]["located"] for r in rows),
        "citations_total": cited, "mean_success_latency_s": fmean(latencies),
        "median_success_latency_s": median(latencies),
    }


def variance(rows):
    attempts = {(r["task"], r["repeat"]): r for r in rows}
    ids = sorted({r["task"] for r in rows if r["repeat"] == 1})
    scored = [task for task in ids if primary(attempts[task, 0]) is not None]
    by_repeat = [fmean(primary(attempts[task, rep]) for task in scored) for rep in range(3)]
    pairs = []
    identical = 0
    for task in ids:
        answers = [attempts[task, rep]["output"]["answer"] for rep in range(3)
                   if attempts[task, rep]["scores"]["execution_ok"]]
        pairs.extend(token_f1(left, right) for left, right in combinations(answers, 2))
        identical += len(answers) == 3 and len({normalize(x) for x in answers}) == 1
    return {"items": len(ids), "scored_without_X_rubrics": len(scored),
            "pairs_of_completed_answers": len(pairs),
            "mean_pairwise_answer_token_F1": fmean(pairs) if pairs else None,
            "items_with_three_identical_normalized_answers": identical,
            "execution_successes_by_repeat": [sum(attempts[t, rep]["scores"]["execution_ok"] for t in ids)
                                             for rep in range(3)],
            "complete_three_times": sum(all(attempts[t, rep]["scores"]["execution_ok"]
                                            for rep in range(3)) for t in ids),
            "means_by_repeat_on_scored_items": by_repeat, "sd_of_three_means": stdev(by_repeat),
            "mean_within_item_sample_variance": fmean(stdev(primary(attempts[t, rep]) for rep in range(3))**2
                                                      for t in scored),
            "pass_all_three_on_scored_items": sum(all(primary(attempts[t, rep]) >= .5
                                                      for rep in range(3)) for t in scored)}


def summarize(rows):
    main = {s: {r["task"]: r for r in rows if r["repeat"] == 0 and r["system"] == s} for s in systems}
    common = sorted(t for t in main["glossx"] if all(main[s][t]["scores"]["execution_ok"] for s in systems))
    summary = {s: {"main": describe(list(main[s].values())),
                   "paired_success": describe([main[s][t] for t in common]),
                   "variance": variance([r for r in rows if r["system"] == s])}
               for s in systems}
    summary["paired_quality"] = {}
    for part in ("Q", "D"):
        ids = [t for t in common if parts[main["glossx"][t]["suite"]] == part]
        diff = [primary(main["glossx"][t]) - primary(main["dsh"][t]) for t in ids]
        summary["paired_quality"][part] = {
            "items": len(ids), "difference_glossx_minus_dsh_and_95pct_paired_bootstrap_ci":
                bootstrap_ci(diff, iters=10000, seed=0)}
    return summary


if __name__ == "__main__":
    path = Path(sys.argv[1])
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if len(rows) != 310:
        raise ValueError("Requires verified, complete results")
    print(json.dumps(summarize(rows), indent=2))
