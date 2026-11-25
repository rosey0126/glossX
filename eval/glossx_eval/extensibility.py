"""Extensibility metric (proposal §4, O1): what it took to add each workflow.

For every built-in workflow manifest this finds the commit that added it and
splits the lines that commit changed under ``backend/app/agent`` into

* ``manifest``  -- the workflow's own JSON manifest,
* ``plugin``    -- first-party capabilities, loops and other plugin code,
* ``kernel``    -- the fixed kernel: capability registry, permission/budget
  gate, run manager (scheduler + trace log) and the loop driver.

The proposal's success criterion is that the last workflows need no kernel
changes. When one commit added several workflows together with other work, the
numbers are shared by all of them and the row says so.

    python -m glossx_eval.extensibility            # Markdown table
    python -m glossx_eval.extensibility --json
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AGENT = "backend/app/agent"
WORKFLOWS = f"{AGENT}/workflows"
KERNEL = {f"{AGENT}/{name}" for name in ("capabilities.py", "gate.py", "runs.py", "loop.py")}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, check=True, capture_output=True, text=True).stdout


def added_in(path: str) -> str | None:
    out = git("log", "--diff-filter=A", "--format=%h", "--", path).split()
    return out[-1] if out else None


def numstat(commit: str) -> list[tuple[str, int]]:
    rows = []
    for line in git("show", "--numstat", "--format=", commit).splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0] != "-":
            rows.append((parts[2], int(parts[0]) + int(parts[1])))
    return rows


def measure() -> list[dict]:
    manifests = sorted((REPO / WORKFLOWS).glob("*.json"))
    rows = []
    for path in manifests:
        rel = path.relative_to(REPO).as_posix()
        commit = added_in(rel)
        stat = numstat(commit) if commit else []
        agent = [(f, n) for f, n in stat if f.startswith(AGENT + "/")]
        shared = sorted(Path(f).stem for f, _ in agent if f.startswith(WORKFLOWS + "/") and f != rel)
        rows.append({
            "workflow": json.loads(path.read_text(encoding="utf-8"))["id"],
            "manifest_lines": len(path.read_text(encoding="utf-8").splitlines()),
            "commit": commit,
            "kernel_lines": sum(n for f, n in agent if f in KERNEL),
            "kernel_files": sorted(Path(f).name for f, _ in agent if f in KERNEL),
            "plugin_lines": sum(n for f, n in agent if f not in KERNEL and not f.startswith(WORKFLOWS + "/")),
            "added_with": shared,
        })
    return rows


def markdown(rows: list[dict]) -> str:
    out = ["| workflow | manifest lines | plugin code changed | kernel lines changed | commit | note |",
           "| --- | ---: | ---: | ---: | --- | --- |"]
    for r in rows:
        note = []
        if r["kernel_files"]:
            note.append("kernel: " + ", ".join(r["kernel_files"]))
        if r["added_with"]:
            note.append("same commit as " + ", ".join(r["added_with"]))
        out.append(f"| {r['workflow']} | {r['manifest_lines']} | {r['plugin_lines']} | {r['kernel_lines']} "
                   f"| `{r['commit']}` | {'; '.join(note)} |")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="glossx_eval.extensibility")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    rows = measure()
    print(json.dumps(rows, indent=2) if args.json else markdown(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
