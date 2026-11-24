"""Reliability and recovery scenarios (course requirement: >= 2 failure situations).

Each scenario injects one failure into a real GlossX run and checks how the
agent detects it, recovers within a bound or stops safely, and what the user
is told. The agent code is the real kernel (router, planner, gate, verifier,
repair, loops); only the language model is **scripted**: a fake provider
answers each role (planner, writer, verifier, ...) with a fixed reply, and
raises an error where the scenario says the model or a tool fails. That makes
the failures reproducible and costs no tokens. Failures that need a real
model's judgement (prompt injection, unreadable PDFs during a task) are in
``faults.py`` and run with the main evaluation.

    python -m glossx_eval.reliability                 # table on stdout
    python -m glossx_eval.reliability --out results/reliability   # + one trace per scenario
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[2]

PAPERS = {
    "p1": ["The Transformer uses multi-head self-attention instead of recurrence.",
           "On WMT 2014 English-German the big Transformer reaches 28.4 BLEU."],
    "p2": ["ConvS2S replaces recurrence with convolutions over the sequence.",
           "ConvS2S reaches 25.2 BLEU on WMT 2014 English-German."],
}

ROLES = [
    ("You repair a research answer", "repair"), ("self-reflection step", "critique"),
    ("reflection step of GlossX", "reflect"), ("planner of GlossX", "plan"),
    ("decider of GlossX", "decide"), ("strict fact checker", "verify"),
    ("careful research agent", "synth"),
]

DEFAULTS: dict[str, Any] = {
    "plan": {"sub_questions": ["What BLEU does each model reach?"], "steps": [
        {"id": "s1", "capability": "paper.search_spans", "args": {"query": "BLEU WMT 2014"},
         "purpose": "find the scores"}]},
    "synth": {"answer": "The Transformer reaches 28.4 BLEU [S:p1#1]. ConvS2S reaches 25.2 BLEU [S:p2#1].",
              "claims": [{"text": "The Transformer reaches 28.4 BLEU.", "span_ids": ["p1#1"]},
                         {"text": "ConvS2S reaches 25.2 BLEU.", "span_ids": ["p2#1"]}]},
    "verify": {"verdicts": [{"i": 0, "verdict": "supported", "confidence": 0.95, "note": "stated"},
                            {"i": 1, "verdict": "supported", "confidence": 0.95, "note": "stated"}]},
    "repair": {"answer": "The Transformer reaches 28.4 BLEU [S:p1#1]."},
    "reflect": {"decision": "stop", "reason": "covered"},
    "critique": {"done": False, "lessons": ["search the other paper too"]},
    "decide": {"choice": "generic", "confidence": 0.8, "reason": "focused question"},
}


class ScriptedLLM:
    """Answers each kernel role from ``DEFAULTS`` or a per-scenario override;
    an ``Exception`` override makes that role's call fail like a provider error."""

    def __init__(self, **overrides: Any) -> None:
        self.overrides = overrides
        self.calls: list[str] = []

    async def complete(self, system, messages, *, provider=None, model=None):
        role = next((r for needle, r in ROLES if needle in system), None)
        if role is None:
            raise RuntimeError(f"unscripted prompt: {system[:80]}")
        self.calls.append(role)
        out = self.overrides.get(role, DEFAULTS[role])
        if isinstance(out, Exception):
            raise out
        return json.dumps(out), {}


def _setup() -> None:
    """Isolate app data and make the backend importable (before any app import)."""
    data = Path(tempfile.mkdtemp(prefix="glossx-reliability-"))
    os.environ.setdefault("GLOSS_DATA_DIR", str(data))
    os.environ.setdefault("GLOSSX_HOME", str(data / "glossx-home"))
    backend = str(REPO / "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)


def _kernel():
    from app.agent import loop as loop_mod
    from app.agent.capabilities import Capability, build_registry
    from app.agent.context import SpanStore
    from app.agent.gate import BudgetMeter, Gate
    from app.features import retrieval
    from app.library import store
    from app.providers import registry as providers

    store.init_db()
    real_get = store.get_paper
    store.get_paper = lambda pid: ({"id": pid, "title": pid.upper(), "year": 2017}
                                   if pid in PAPERS else real_get(pid))

    class MemorySpans(SpanStore):
        def _load(self, paper_id: str) -> list[dict]:
            if paper_id not in self._chunks:
                self._chunks[paper_id] = [
                    {"text": t, "tokens": retrieval._tok(t), "page": i, "bbox": [0, 0, 10, 10], "span_index": i}
                    for i, t in enumerate(PAPERS.get(paper_id, []))]
                self._titles[paper_id] = paper_id.upper()
            return self._chunks[paper_id]

    return SimpleNamespace(loop=loop_mod, Capability=Capability, build_registry=build_registry,
                           MemorySpans=MemorySpans, BudgetMeter=BudgetMeter, Gate=Gate, providers=providers)


def _drive(k, llm: ScriptedLLM, *, registry=None, **run_attrs) -> tuple[dict, list[dict]]:
    """Run one goal; the run's route decision is copied into the result."""
    events: list[dict] = []
    run = SimpleNamespace(id="rel", goal="Compare the BLEU of the Transformer and ConvS2S on WMT14 En-De",
                          paper_ids=["p1", "p2"], max_rounds=2, provider=None, import_jobs=None,
                          project_id=None, workflow="generic", loop=None, plan=None, route=None)
    for key, value in run_attrs.items():
        setattr(run, key, value)
    original = k.providers.complete
    k.providers.complete = llm.complete
    try:
        result = asyncio.run(k.loop.run_agent(run, registry or k.build_registry(connections={}),
                                              k.MemorySpans(), events.append))
    finally:
        k.providers.complete = original
    result["route"] = run.route
    return result, events


def _has(events: list[dict], phase: str, status: str | None = None, text: str = "") -> bool:
    return any(e.get("phase") == phase and (status is None or e.get("status") == status)
               and text in (e.get("detail") or "") for e in events)


# -- scenarios ------------------------------------------------------------------
def s_hallucination(k):
    llm = ScriptedLLM(
        synth={"answer": "The Transformer reaches 28.4 BLEU [S:p1#1]. It was trained on 1B GPUs [S:p1#0].",
               "claims": [{"text": "The Transformer reaches 28.4 BLEU.", "span_ids": ["p1#1"]},
                          {"text": "It was trained on 1B GPUs.", "span_ids": ["p1#0"]}]},
        verify={"verdicts": [{"i": 0, "verdict": "supported", "confidence": 0.9, "note": "stated"},
                             {"i": 1, "verdict": "unsupported", "confidence": 0.9, "note": "not in the span"}]})
    result, events = _drive(k, llm)
    ok = ("GPUs" not in result["answer"] and len(result["rejected_claims"]) == 1
          and _has(events, "verify", "completed", "removed"))
    return ok, result, events


def s_verifier_down(k):
    llm = ScriptedLLM(verify=RuntimeError("provider HTTP 503"))
    result, events = _drive(k, llm)
    claims = result["claims"]
    ok = (bool(result["answer"]) and claims and all(c["verdict"] == "partial" for c in claims)
          and all("verification unavailable" in c.get("note", "") for c in claims)
          and _has(events, "verify", "failed"))
    return ok, result, events


def s_router_down(k):
    llm = ScriptedLLM(decide=RuntimeError("provider timeout"))
    result, events = _drive(k, llm, workflow="auto")
    route = result.get("route") or {}
    ok = bool(result["answer"]) and route.get("workflow") is None and "router failed" in (route.get("reason") or "")
    return ok, result, events


def s_tool_fails(k):
    registry = k.build_registry(connections={})

    async def broken(args, ctx):
        raise TimeoutError("web search did not answer")

    registry.register(k.Capability(name="web.flaky_search", kind="tool", card="Search the web (fails).",
                                   input_schema={"query": "string"}, handler=broken))
    llm = ScriptedLLM(plan={"sub_questions": ["BLEU of each model"], "steps": [
        {"id": "s1", "capability": "web.flaky_search", "args": {"query": "BLEU"}, "purpose": "web search"},
        {"id": "s2", "capability": "paper.search_spans", "args": {"query": "BLEU WMT 2014"},
         "purpose": "search the papers"}]})
    result, events = _drive(k, llm, registry=registry)
    ok = (_has(events, "execute", "failed") and bool(result["answer"])
          and any(c["verdict"] == "supported" for c in result["claims"]))
    return ok, result, events


def s_approval_denied(k):
    registry = k.build_registry(connections={})
    ran: list[bool] = []

    async def run_code(args, ctx):
        ran.append(True)
        return {"stdout": "ran"}

    registry.register(k.Capability(name="delegate.fake_coder", kind="tool", card="Run code in a sandbox.",
                                   input_schema={"task": "string"}, handler=run_code,
                                   permissions=["code:execute"], trust="external", source="cli"))
    llm = ScriptedLLM(plan={"sub_questions": ["reproduce"], "steps": [
        {"id": "s1", "capability": "delegate.fake_coder", "args": {"task": "train"}, "purpose": "run training"}]},
        synth={"answer": "", "claims": []})
    events: list[dict] = []

    async def deny(approval):
        return False, "user denied code execution"

    gate = k.Gate(events.append, delegate=deny)
    result, evs = _drive(k, llm, registry=registry, gate=gate, max_rounds=1)
    evs = events + evs
    ok = not ran and result["stop_reason"] == "approval_needed"
    return ok, result, evs


def s_budget(k):
    llm = ScriptedLLM(reflect={"decision": "replan", "reason": "need more", "new_steps": [
        {"id": "r1", "capability": "paper.search_spans", "args": {"query": "training cost"}, "purpose": "more"}]})
    result, events = _drive(k, llm, meter=k.BudgetMeter({"max_steps": 2}), max_rounds=3)
    ok = result["stop_reason"] == "budget" and any("budget" in (e.get("detail") or "") for e in events)
    return ok, result, events


def s_no_progress(k):
    llm = ScriptedLLM(verify={"verdicts": [{"i": 0, "verdict": "supported", "confidence": 0.9},
                                           {"i": 1, "verdict": "partial", "confidence": 0.4}]})
    result, events = _drive(k, llm, loop="reflexion", max_rounds=3)
    ok = result["stop_reason"] == "no_progress" and result["rounds"] < 3
    return ok, result, events


def s_corrupt_upload(k):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        before = len(client.get("/api/papers").json()["papers"])
        resp = client.post("/api/papers/upload",
                           files={"file": ("broken.pdf", b"%PDF-1.7\nthis is not a pdf", "application/pdf")})
        after = len(client.get("/api/papers").json()["papers"])
    result = {"status_code": resp.status_code, "detail": resp.json().get("detail"),
              "papers_before": before, "papers_after": after}
    return resp.status_code == 400 and before == after, result, []


SCENARIOS: list[tuple[str, str, str, str, Callable]] = [
    ("hallucinated-claim", "writer cites a span that does not support its sentence",
     "verifier labels the claim unsupported", "repair rewrites the answer without it; claim listed as rejected",
     s_hallucination),
    ("verifier-provider-down", "model call fails (HTTP 503) during verification",
     "exception caught in verify()", "answer kept, every claim marked 'partial: verification unavailable'",
     s_verifier_down),
    ("router-provider-down", "model call times out while routing",
     "exception caught in route()", "falls back to the generic loop and says why", s_router_down),
    ("tool-timeout", "a planned tool times out", "step marked failed and observed",
     "other steps continue; answer built from the evidence that was found", s_tool_fails),
    ("approval-denied", "plan needs code execution and the user denies it", "permission gate",
     "handler never runs; run stops with stop_reason=approval_needed", s_approval_denied),
    ("budget-exhausted", "reflection keeps asking for more rounds", "budget meter (max_steps=2)",
     "run stops with stop_reason=budget and returns what it has", s_budget),
    ("no-progress-loop", "Reflexion rounds stop improving coverage", "coverage compared across rounds",
     "stops with stop_reason=no_progress before max_rounds", s_no_progress),
    ("corrupt-pdf-upload", "user uploads an unreadable PDF", "PDF parse fails at import",
     "HTTP 400 with a message; no half-imported paper", s_corrupt_upload),
]


def run_all(out: Path | None = None) -> list[dict]:
    _setup()
    k = _kernel()
    rows = []
    for name, failure, detection, recovery, fn in SCENARIOS:
        try:
            ok, result, events = fn(k)
            error = None
        except Exception as exc:  # report, never hide
            ok, result, events, error = False, {}, [], f"{type(exc).__name__}: {exc}"
        row = {"scenario": name, "failure": failure, "detection": detection, "expected_recovery": recovery,
               "passed": bool(ok), "stop_reason": result.get("stop_reason"), "error": error}
        rows.append(row)
        if out:
            out.mkdir(parents=True, exist_ok=True)
            (out / f"{name}.json").write_text(json.dumps(
                {**row, "result": result, "events": events}, ensure_ascii=False, indent=1, default=str),
                encoding="utf-8")
    return rows


def markdown(rows: list[dict]) -> str:
    lines = ["| scenario | injected failure | detection | recovery / safe stop | stop reason | result |",
             "| --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        lines.append(f"| {r['scenario']} | {r['failure']} | {r['detection']} | {r['expected_recovery']} "
                     f"| {r['stop_reason'] or '—'} | {'pass' if r['passed'] else 'FAIL ' + (r['error'] or '')} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="glossx_eval.reliability")
    ap.add_argument("--out", default=None, help="directory for one JSON trace per scenario")
    args = ap.parse_args(argv)
    rows = run_all(Path(args.out) if args.out else None)
    print(markdown(rows))
    return 0 if all(r["passed"] for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
