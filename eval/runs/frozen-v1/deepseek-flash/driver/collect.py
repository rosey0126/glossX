"""Validate and assemble disjoint worker outputs with the frozen evaluator.

Run without --out for a read-only progress check. A delivery requires every
scheduled record, including failures, and a trace for each of them.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil

from glossx_eval.run import pdf_text_reader, score
from glossx_eval.systems import OUTPUT_PROTOCOL, Output, output_from_text, task_prompt
from glossx_eval.tasks import load_tasks, sample

from matrix import DATA_SHA


def read_safe(path):
    content = path.read_bytes()
    key = os.getenv("DEEPSEEK_API_KEY")
    if ((key and key.encode() in content)
            or re.search(rb"\bsk-[A-Za-z0-9_-]{20,}", content)
            or re.search(rb"(?i)[A-Z]:[\\/]+Users[\\/]+", content)):
        raise ValueError(f"Review credentials or personal paths in {path.name}")
    return content.decode("utf-8")


def dsh_usage(events):
    steps = [e.get("usage") for e in events
             if e.get("type") == "status" and e.get("phase") == "step_end"]
    if not steps or any(not step for step in steps):
        return None
    inputs = outputs = 0
    for step in steps:
        inputs_here = sum(step.get(field, 0) for field in
                          ("inputTokens", "cacheReadTokens", "cacheWriteTokens"))
        outputs_here = step["outputTokens"]
        if "totalTokens" in step and inputs_here + outputs_here != step["totalTokens"]:
            raise ValueError("Native DSH token totals do not reconcile")
        inputs += inputs_here
        outputs += outputs_here
    return inputs, outputs


def verify(row, task, folder, reader):
    system, repeat = row["system"], row["repeat"]
    if (row["protocol"], row["suite"], row["kind"]) != (OUTPUT_PROTOCOL, task.suite, task.kind):
        raise ValueError("Protocol or task metadata mismatch")
    output = Output(**row["output"])
    if score(task, output, reader) != row["scores"]:
        raise ValueError("Frozen scorer returned different fields")
    if not row.get("traces") or len(set(row["traces"])) != len(row["traces"]):
        raise ValueError("Missing or duplicate trace reference")
    expected = Path("traces") / system / f"{task.id}-r{repeat}"
    logs = {}
    for path in map(Path, row["traces"]):
        if path.parent != expected:
            raise ValueError("Trace location disagrees with attempt identity")
        logs[path.name] = read_safe(folder / path)
    native_id = None
    if system == "glossx" and not output.error:
        snap = json.loads(logs["glossx-run.json"])
        if snap["status"] != "completed" or snap["goal"] != task_prompt(task)[:4000].strip():
            raise ValueError("GlossX trace status or task prompt disagrees")
        native_id = snap["id"]
    if system == "dsh" and "stdout.txt" in logs:
        events = [json.loads(line) for line in logs["stdout.txt"].splitlines() if line.strip()]
        if not output.error:
            finals = [e for e in events if e.get("type") == "final"]
            if len(finals) != 1 or finals[0]["reason"]["kind"] != "completed":
                raise ValueError("Successful DSH row lacks a completed final event")
            native_id = finals[0]["sessionId"]
            answer = output_from_text(finals[0].get("answer") or finals[0].get("text") or "")
            if answer.answer != output.answer or answer.verdict != output.verdict:
                raise ValueError("DSH final event disagrees with the result")
        usage = dsh_usage(events)
        if usage:
            row["output"]["tokens_in"], row["output"]["tokens_out"] = usage
    row["model"] = "deepseek-flash"
    return native_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--checkpoint", action="store_true",
                        help="Allow an incomplete local snapshot while the run is paused.")
    parser.add_argument("worker_dirs", type=Path, nargs="+")
    args = parser.parse_args()
    if hashlib.sha256(args.tasks.read_bytes()).hexdigest() != DATA_SHA:
        parser.error("Unexpected frozen data SHA-256")
    tasks = load_tasks(args.tasks)
    lookup = {t.id: t for t in tasks}
    subset = sample(tasks, 20, seed=0)
    schedule = [(task.id, rep, system) for rep, group in enumerate((tasks, subset, subset))
                for task in group for system in ("glossx", "dsh")]
    scheduled = set(schedule)
    if len(scheduled) != 310:
        raise ValueError("Unexpected number of scheduled attempts")
    reader = pdf_text_reader(args.tasks.parent)
    records = {}
    sessions = set()
    filename = "results-deepseek-flash.jsonl"
    for folder in args.worker_dirs:
        for line in read_safe(folder / filename).splitlines():
            row = json.loads(line)
            key = (row["task"], row["repeat"], row["system"])
            if key in records or key not in scheduled:
                raise ValueError(f"Duplicate or unexpected attempt {key}")
            try:
                native_id = verify(row, lookup[row["task"]], folder, reader)
            except (KeyError, ValueError, OSError) as exc:
                raise ValueError(f"{key}: {exc}") from exc
            if native_id:
                session = (row["system"], native_id)
                if session in sessions:
                    raise ValueError(f"{key} reused a native session")
                sessions.add(session)
            records[key] = (folder, row)
    failures = sum(not row["scores"]["execution_ok"] for _, row in records.values())
    print(f"{len(records)}/310 verified records, {failures} execution failures")
    if args.out is None:
        return
    if records.keys() != scheduled and not args.checkpoint:
        parser.error("Delivery requires all scheduled records")
    args.out.mkdir(parents=True, exist_ok=True)
    temporary = args.out / (filename + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for key in schedule:
            if key not in records:
                continue
            folder, row = records[key]
            for rel in row["traces"]:
                dest = args.out / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(folder / rel, dest)
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    temporary.replace(args.out / filename)


if __name__ == "__main__":
    main()
