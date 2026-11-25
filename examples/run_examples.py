"""Run the sample requests in ``cases.json`` against a running GlossX backend.

Start GlossX first (``npm start``, default http://localhost:8010) with a provider
configured in Settings. Then:

    python examples/run_examples.py                       # all cases
    python examples/run_examples.py --case ordinary       # one case
    python examples/run_examples.py --url http://127.0.0.1:8010

For every case the script uploads the case's PDFs from ``examples/papers/``,
starts an agent run in a project (follow-ups reuse the first case's project, so
project memory carries over), waits for it, prints the route, stop reason and
answer, and saves the full run snapshot (plan, every event, verdicts) to
``examples/traces/<case>.json``. Uses only the Python standard library.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent


def call(base: str, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(base + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as error:
        try:
            return error.code, json.loads(error.read().decode() or "{}")
        except ValueError:
            return error.code, {}


def upload(base: str, path: Path) -> tuple[int, dict]:
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\n"
            "Content-Type: application/pdf\r\n\r\n").encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(base + "/api/papers/upload", method="POST", data=body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode() or "{}")


def run_case(base: str, case: dict, projects: dict[str, str], timeout: float) -> dict:
    print(f"\n=== {case['id']} ({case['kind']})\n{case['goal']}")
    paper_ids = []
    for name in case["papers"]:
        status, paper = upload(base, HERE / "papers" / name)
        if status != 200:
            print(f"upload of {name} refused: HTTP {status} {paper.get('detail')}")
            return {"case": case["id"], "upload_refused": {"file": name, "status": status,
                                                          "detail": paper.get("detail")}}
        paper_ids.append(paper["id"])
    project_id = projects.get(case.get("follow_up_of") or case["id"])
    if project_id is None:
        status, project = call(base, "POST", "/api/agent/projects", {"name": f"example: {case['id']}"})
        project_id = project.get("id")
    projects[case["id"]] = project_id
    status, snap = call(base, "POST", "/api/agent/runs",
                        {"goal": case["goal"], "paper_ids": paper_ids, "project_id": project_id})
    if status != 200:
        print(f"run refused: HTTP {status} {snap}")
        return {"case": case["id"], "run_refused": {"status": status, "detail": snap.get("detail")}}
    start = time.monotonic()
    while snap.get("status") not in {"completed", "failed", "cancelled"}:
        if snap.get("status") == "awaiting_approval":
            print("waiting for approval in the GlossX window:", (snap.get("pending_approval") or {}).get("reason"))
        if time.monotonic() - start > timeout:
            call(base, "DELETE", f"/api/agent/runs/{snap['id']}")
            print(f"cancelled after {timeout:.0f}s")
            break
        time.sleep(2)
        _, snap = call(base, "GET", f"/api/agent/runs/{snap['id']}")
    result = snap.get("result") or {}
    print(f"route: {(snap.get('route') or {}).get('workflow') or 'generic'} | status: {snap.get('status')} | "
          f"stop: {result.get('stop_reason')} | {time.monotonic() - start:.1f}s")
    print(result.get("answer") or snap.get("error") or "(no answer)")
    if result.get("rejected_claims"):
        print("removed as unsupported:", [c.get("text") for c in result["rejected_claims"]])
    return snap


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8010")
    ap.add_argument("--case", action="append", help="case id (repeatable); default: all")
    ap.add_argument("--timeout", type=float, default=600)
    args = ap.parse_args(argv)
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    if args.case:
        wanted = set(args.case) | {c.get("follow_up_of") for c in cases if c["id"] in args.case} - {None}
        cases = [c for c in cases if c["id"] in wanted]
    out = HERE / "traces"
    out.mkdir(exist_ok=True)
    projects: dict[str, str] = {}
    for case in cases:
        snap = run_case(args.url.rstrip("/"), case, projects, args.timeout)
        (out / f"{case['id']}.json").write_text(
            json.dumps({"case": case, "run": snap}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"\ntraces written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
