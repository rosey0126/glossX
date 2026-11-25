"""One local worker for the paired benchmark. Set PYTHONPATH to the pinned eval/."""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import urlparse

import httpx
from glossx_eval.run import pdf_text_reader, score
from glossx_eval.systems import OUTPUT_PROTOCOL, Output
from glossx_eval.tasks import load_tasks, sample
import dsh

PIN = "99ded17ecfde04e0e589e9b11606b90cd5a7eb23"
DATA_SHA = "493d198ed39f4ae850bb925a165235e5c54950de3afcee800a8d34861cc9a5a7"


def open_glossx(url, key, output_language=None):
    if urlparse(url).hostname not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("Expected a local evaluation backend")
    with httpx.Client(base_url=url, trust_env=False, timeout=30) as client:
        settings = {"model": dsh.MODEL, "base_url": dsh.ROUTE, "timeout": 900,
                    "enabled": True, "api_key": key}
        patch = {"provider": "openai", "providers": {"openai": settings}}
        if output_language:
            patch["output_language"] = output_language
        client.post("/api/settings", json=patch).raise_for_status()
        cfg = client.get("/api/settings").raise_for_status().json()["config"]
        if output_language and cfg.get("output_language") != output_language:
            raise RuntimeError("Unexpected saved GlossX output language")
        active = cfg["providers"][cfg["provider"]]
        if (cfg["provider"], active["model"], active["base_url"], active["api_key"]) != (
                "openai", dsh.MODEL, dsh.ROUTE, "set"):
            raise RuntimeError("Unexpected saved provider settings")
        return {p["id"] for p in client.get("/api/papers").raise_for_status().json()["papers"]}


def run_glossx(task_row, args, work):
    # The native CLI always numbers a one-item, one-repeat invocation as r0.
    # The caller assigns the scheduled repeat to its returned row and trace.
    with tempfile.NamedTemporaryFile(dir=args.tasks.parent, suffix=".jsonl", delete=False) as tmp:
        tmp.write((json.dumps(task_row, ensure_ascii=False) + "\n").encode())
        single = Path(tmp.name)
    try:
        # The native runner nests the task ID twice. Long QASPER names can put
        # a staged PDF beyond MAX_PATH before the model sees its prompt.
        native_work = "\\\\?\\" + str(work) if os.name == "nt" else str(work)
        with (work / "cli.log").open("wb") as log:
            subprocess.run([sys.executable, "-m", "glossx_eval.run", str(single),
                            "--execute", "--systems", "glossx", "--model", dsh.MODEL,
                            "--repeats", "1", "--timeout", "900", "--glossx-url", args.glossx_url,
                            "--paper-ids", str(args.tasks.with_name("paper_ids.json")),
                            "--out", native_work], check=True, stdout=log, stderr=log)
    finally:
        single.unlink()
    result, = work.glob("results-*.jsonl")
    row = json.loads(result.read_text(encoding="utf-8"))
    trace = work / "work/glossx" / (row["task"] + "-r0") / "glossx-run.json"
    logs = {"glossx-run.json": trace.read_text(encoding="utf-8")} if trace.exists() else {
        "cli.log": (work / "cli.log").read_text(encoding="utf-8", errors="replace")}
    return row, logs


def main():
    p = argparse.ArgumentParser()
    for name in ("tasks", "scratch", "out", "dsh-cli"):
        p.add_argument("--"+name, required=True, type=Path)
    scope = p.add_mutually_exclusive_group()
    scope.add_argument("--main-range", type=int, nargs=2, metavar=("START", "STOP"),
                       help="Run repeat 0 for the zero-based, half-open slice of frozen tasks.")
    scope.add_argument("--variance-only", action="store_true",
                       help="Run repeats 1 and 2 for the frozen seed-0 subset.")
    scope.add_argument("--variance-range", type=int, nargs=2, metavar=("START", "STOP"),
                       help="Run repeats 1 and 2 for a half-open slice of the seed-0 subset.")
    p.add_argument("--glossx-url", default="http://127.0.0.1:18765")
    p.add_argument("--output-language", help="Set and verify the backend's response language before starting.")
    p.add_argument("--execute", action="store_true")
    args = p.parse_args()
    args.tasks = args.tasks.resolve()
    if hashlib.sha256(args.tasks.read_bytes()).hexdigest() != DATA_SHA:
        raise ValueError("Frozen JSONL checksum mismatch")
    import glossx_eval.run as native
    root = Path(native.__file__).resolve().parents[2]
    rev = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if rev != PIN:
        raise ValueError("Unexpected runtime commit")
    tasks = load_tasks(args.tasks)
    subset = sample(tasks, 20, seed=0)
    phases = [(0, tasks), (1, subset), (2, subset)]
    if len(tasks) != 115 or len({t.id for t in tasks}) != 115:
        raise ValueError("Unexpected task count")
    if args.main_range:
        start, stop = args.main_range
        if not 0 <= start < stop <= len(tasks):
            p.error("main range must satisfy 0 <= START < STOP <= 115")
        phases = [(0, tasks[start:stop])]
    elif args.variance_only:
        phases = phases[1:]
    elif args.variance_range:
        start, stop = args.variance_range
        if not 0 <= start < stop <= len(subset):
            p.error("variance range must satisfy 0 <= START < STOP <= 20")
        phases = [(r, subset[start:stop]) for r in (1, 2)]
    print("Scheduled paired items:", sum(len(group) for _, group in phases), flush=True)
    if not args.execute:
        return
    if (args.scratch.parent / "pause-new-workers").is_file():
        raise SystemExit("New workers paused before provider access.")
    key = os.environ["DEEPSEEK_API_KEY"]
    with httpx.Client(timeout=30) as c:
        credit = c.get(dsh.ROUTE + "/user/balance", headers={"Authorization": "Bearer " + key})
        if not credit.raise_for_status().json()["is_available"]:
            raise SystemExit("Credit unavailable. No inference attempted.")
    known = open_glossx(args.glossx_url, key, args.output_language)
    paper_ids = json.loads(args.tasks.with_name("paper_ids.json").read_text(encoding="utf-8"))
    if any(paper_ids.get(Path(f).name) not in known for t in tasks for f in t.papers):
        raise ValueError("Paper import incomplete")
    reader = pdf_text_reader(args.tasks.parent)
    args.out.mkdir(parents=True, exist_ok=True)
    rows_path = args.out / "results-deepseek-flash.jsonl"
    rows = [json.loads(s) for s in rows_path.read_text(encoding="utf-8").splitlines()] if rows_path.exists() else []
    done = {(r["task"], r["repeat"], r["system"]) for r in rows}
    if len(done) != len(rows):
        raise RuntimeError("Duplicate results found")
    for repeat, group in phases:
        for t in group:
            for system in ("glossx", "dsh"):
                if (t.id, repeat, system) in done:
                    continue
                rel = Path(system) / f"{t.id}-r{repeat}"
                work = (args.scratch / rel).resolve()
                # An interrupted launch must be reconciled before further billing.
                work.mkdir(parents=True, exist_ok=False)
                if system == "glossx":
                    row, logs = run_glossx(asdict(t), args, work)
                    row["repeat"] = repeat
                else:
                    try:
                        output, stdout, stderr = dsh.run(t, args.tasks.parent, work, args.dsh_cli)
                        logs = {"stdout.txt": stdout, "stderr.txt": stderr}
                    except (ValueError, OSError, subprocess.SubprocessError) as exc:
                        output = Output(error=f"{type(exc).__name__}: {exc}")
                        logs = {"launcher.txt": output.error}
                    row = {"protocol": OUTPUT_PROTOCOL, "task": t.id, "suite": t.suite,
                           "kind": t.kind, "system": system, "repeat": repeat,
                           "output": asdict(output), "scores": score(t, output, reader)}
                trace_dir = args.out / "traces" / rel
                trace_dir.mkdir(parents=True, exist_ok=False)
                def scrub(text):
                    for src, new in [(key, "[redacted]"), (str(work), "<run>"),
                                     (str(Path.home()), "<home>")]:
                        for spelling in (json.dumps(src, ensure_ascii=False)[1:-1], src, src.replace("\\", "/")):
                            text = text.replace(spelling, new)
                    return text
                row["traces"] = []
                for name, value in logs.items():
                    path = trace_dir / name
                    path.write_bytes(scrub(value).encode())
                    row["traces"].append(path.relative_to(args.out).as_posix())
                with rows_path.open("ab") as f:
                    f.write((scrub(json.dumps(row, ensure_ascii=False)) + "\n").encode())
                print(system, t.id, repeat, row["scores"]["execution_ok"], flush=True)
                if not row["scores"]["execution_ok"] and repeat == 0 and t.id == tasks[0].id:
                    raise SystemExit("First item failed. Inspect retained output before further calls.")
                if row["scores"].get("error_kind") in {"payment", "authentication"}:
                    raise SystemExit("Recorded failure. Check account before resuming.")


if __name__ == "__main__":
    main()
