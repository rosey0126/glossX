"""Systems under test, all returning the same :class:`Output`.

Fairness rules (see README): the same base model, the same task text from
:func:`task_prompt`, the same papers in a fresh working directory, the same
wall-clock and token caps, one fresh session per task and repeat.

* ``glossx``  -- the GlossX agent through its HTTP API (``/api/agent/runs``).
  ``glossx-noverify`` / ``glossx-noreflect`` are the same agent with the
  verifier or the reflection round switched off (ablations).
* ``gloss-chat`` -- baseline B0/B1: Gloss v1.0.2's paper chat (one BM25
  retrieval, one prompt, one paper) through ``/api/ai/chat``.
* ``codex``   -- ``codex exec --json`` in the task directory.
* ``pi``      -- the pi coding agent in print mode.
* ``command`` -- any other CLI agent given a command template.

Baselines answer in the JSON shape of :data:`ANSWER_SHAPE`, which asks for the
same verifiable citations GlossX produces (paper, page, verbatim quote).
"""
from __future__ import annotations

import json
import re
import os
import shlex
import shutil
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from . import metrics
from .tasks import Task

OUTPUT_PROTOCOL = "answer-fields-v2"

ANSWER_SHAPE = (
    '{"answer": "<direct answer only>", "explanation": "<reasoning and limitations>", '
    '"verdict": <"SUPPORTED", "REFUTED", "NOT ENOUGH EVIDENCE", or null>, '
    '"citations": [{"claim": "<supported factual statement>", '
    '"paper": "<file name of the paper>", "page": <1-based page>, "quote": "<verbatim text from that page>"}], '
    '"confidence": <0..1>}'
)

KIND_INSTRUCTIONS = {
    "qa": "Answer the question using only the papers in this directory.",
    "claim": ("Decide whether the papers in this directory support the claim. Set the JSON verdict "
              "field to SUPPORTED, REFUTED or NOT ENOUGH EVIDENCE; keep the answer concise."),
    "review": "Write a short literature review answering the question from the papers in this directory.",
    "tutor": "Teach the topic to a student using the papers, slides or notes in this directory.",
    "repro": "Reproduce the paper's main result in this directory and report what matches the paper.",
    "route": "Handle the request.",
}


def task_prompt(task: Task) -> str:
    """The task text every system receives (GlossX gets the same goal)."""
    papers = "\n".join(f"- {Path(p).name}" for p in task.papers) or "- (none)"
    answer_rule = (
        "For question answering, put only the shortest complete direct answer in answer: "
        "a yes/no, requested value, or concise phrase as appropriate. If the papers do not answer "
        "the question, use 'unanswerable'. Put reasoning, uncertainty, qualifications and citations "
        "in explanation and citations, not in answer. Do not shorten an answer by omitting requested parts. "
        if task.kind == "qa" else
        "For reviews, tutoring and reproduction, answer may contain the requested full response. "
    )
    return (
        f"{KIND_INSTRUCTIONS[task.kind]}\n\n{task.question}\n\nPapers:\n{papers}\n\n"
        "Back every factual sentence with a citation: the paper's file name, the 1-based page "
        "and a verbatim quote from that page. Do not cite anything you did not read. "
        f"{answer_rule}For non-claim tasks set verdict to null. "
        f"Finish with one JSON object exactly in this shape:\n{ANSWER_SHAPE}"
    )


@dataclass
class Output:
    answer: str = ""
    citations: list[dict[str, Any]] = field(default_factory=list)
    confidence: float | None = None
    latency_s: float = 0.0
    tokens_in: int | None = None
    tokens_out: int | None = None
    tool_calls: int | None = None
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    explanation: str = ""
    verdict: str | None = None


class System(Protocol):
    name: str

    def run(self, task: Task, workdir: Path, timeout_s: float) -> Output: ...


def _last_answer_object(text: str) -> tuple[dict[str, Any] | None, int]:
    """The last top-level JSON object in a model's final message."""
    decoder = json.JSONDecoder()
    answer: tuple[dict[str, Any] | None, int] = (None, len(text or ""))
    cursor = 0
    while cursor < len(text or ""):
        start = text.find("{", cursor)
        if start < 0:
            break
        try:
            obj, cursor = decoder.raw_decode(text, start)
        except ValueError:
            cursor = start + 1
            continue
        if isinstance(obj, dict) and "answer" in obj:
            answer = obj, start
        # Skip nested objects (including citation objects with an 'answer' key).
    return answer


def last_json_object(text: str) -> dict[str, Any] | None:
    return _last_answer_object(text)[0]


def _verdict(answer: str, prefix: str, field: Any = None) -> tuple[str | None, dict]:
    """Keep explicit decisions from legacy answers without guessing from prose.

    Only the answer and text preceding the final JSON are inspected. Quotes
    inside citation objects cannot become a predicted label. Disagreement is
    retained as a diagnostic instead of picking a convenient label.
    """
    labels = metrics.verdict_candidates(answer) | metrics.verdict_candidates(prefix)
    sources = {}
    if field is not None:
        structured = str(field).strip().upper()
        if structured not in metrics.CLAIM_LABELS:
            return None, {"verdict_error": "invalid structured verdict"}
        labels.add(structured)
        sources["structured_verdict"] = structured
    if len(labels) > 1:
        return None, {**sources, "verdict_conflict": sorted(labels)}
    return next(iter(labels), None), sources


ANSWER_LINE = re.compile(r"^[ \t>*_#-]*answer[ \t*_]*[:：][ \t*_]*(?P<answer>\S.*)$", re.I | re.M)
SPAN_MARKER = re.compile(r"\s*\[(?:S|P|p\.?)\s*:[^\]]*\]")


def answer_line(text: str) -> str | None:
    """The explicit final ``Answer: ...`` line, with span markers removed.

    Same rule for every system without a JSON answer object: only a line that
    starts with ``Answer:`` counts, and the last such line wins. Nothing is
    picked out of free prose.
    """
    matches = list(ANSWER_LINE.finditer(text or ""))
    if not matches:
        return None
    line = SPAN_MARKER.sub("", matches[-1].group("answer")).strip().strip("*_ ").strip()
    return line or None


def output_from_text(text: str) -> Output:
    obj, start = _last_answer_object(text)
    if obj is None:
        # Missing JSON is an output-format diagnostic, not an API failure.
        # An explicit "Answer:" line is the answer field; otherwise the whole
        # text is scored. The full text stays available for fault checks.
        verdict, diagnostic = _verdict(text, "")
        line = answer_line(text)
        extra = {"answer_source": "answer_line", "full_answer": text.strip()} if line else {"answer_source": "full_text"}
        return Output(answer=line or text.strip(), verdict=verdict,
                      raw={"text": text, "format_ok": False,
                           "format_error": "no JSON answer object", **extra, **diagnostic})
    cites = obj.get("citations") if isinstance(obj.get("citations"), list) else []
    conf = obj.get("confidence")
    answer = str(obj.get("answer") or "")
    verdict, diagnostic = _verdict(answer, text[:start], obj.get("verdict"))
    return Output(answer=answer, citations=[c for c in cites if isinstance(c, dict)],
                  confidence=float(conf) if isinstance(conf, (int, float)) else None,
                  explanation=str(obj.get("explanation") or ""), verdict=verdict,
                  raw={"text": text, "format_ok": True, **diagnostic})


def save_trace(workdir: Path | None, name: str, text: str) -> None:
    """Keep a run's raw output next to its staged papers (best effort)."""
    if workdir is None:
        return
    try:
        Path(workdir).mkdir(parents=True, exist_ok=True)
        (Path(workdir) / name).write_text(text or "", encoding="utf-8")
    except OSError:
        pass


def stage_papers(task: Task, task_dir: Path, workdir: Path) -> None:
    workdir.mkdir(parents=True, exist_ok=True)
    for p in task.papers:
        src = (task_dir / p).resolve()
        if src.exists():
            shutil.copy2(src, workdir / src.name)


# -- CLI agents ---------------------------------------------------------------------
@dataclass
class CommandSystem:
    """Any CLI agent. ``template`` is split like a shell command line and the
    ``{prompt}`` word is replaced by the task text; no shell is involved, so it
    works the same on Windows (``codex.cmd``) and POSIX."""

    name: str
    template: str
    env: dict[str, str] = field(default_factory=dict)

    def parse(self, stdout: str) -> Output:
        return output_from_text(stdout)

    def run(self, task: Task, workdir: Path, timeout_s: float) -> Output:
        prompt = task_prompt(task)
        argv = [prompt if word == "{prompt}" else word for word in shlex.split(self.template)]
        argv[0] = shutil.which(argv[0]) or argv[0]
        start = time.monotonic()
        try:
            proc = subprocess.run(argv, cwd=workdir, capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=timeout_s, env={**os.environ, **self.env})
        except FileNotFoundError:
            return Output(error=f"{argv[0]} is not installed")
        except subprocess.TimeoutExpired:
            return Output(error=f"timeout after {timeout_s:.0f}s", latency_s=time.monotonic() - start)
        save_trace(workdir, "stdout.txt", proc.stdout)
        out = self.parse(proc.stdout)
        out.latency_s = time.monotonic() - start
        if proc.returncode != 0:
            out.error = f"exit {proc.returncode}: {proc.stderr[-500:]}"
        return out


class CodexSystem(CommandSystem):
    """``codex exec --json``: JSONL events; the last agent message holds the answer."""

    def __init__(self, model: str | None = None) -> None:
        model_flag = f" -m {shlex.quote(model)}" if model else ""
        super().__init__("codex", "codex exec --json --skip-git-repo-check" + model_flag + " {prompt}")

    def parse(self, stdout: str) -> Output:
        messages, usage, tools = [], {}, 0
        for line in stdout.splitlines():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            item = ev.get("item") or {}
            if item.get("type") == "agent_message" and item.get("text"):
                messages.append(item["text"])
            elif item.get("type") in {"command_execution", "mcp_tool_call", "file_change"}:
                tools += ev.get("type") == "item.completed"
            if isinstance(ev.get("usage"), dict):
                usage = ev["usage"]
        out = output_from_text(messages[-1] if messages else stdout)
        out.tokens_in = usage.get("input_tokens")
        out.tokens_out = usage.get("output_tokens")
        out.tool_calls = tools
        return out


class PiSystem(CommandSystem):
    """The pi coding agent (github.com/badlogic/pi-mono) in non-interactive print mode.

    Check ``pi --help`` on the machine that runs the evaluation: flags have
    changed between releases, so the template is configurable.
    """

    def __init__(self, provider: str | None = None, model: str | None = None,
                 template: str | None = None) -> None:
        flags = ""
        if provider:
            flags += f" --provider {shlex.quote(provider)}"
        if model:
            flags += f" --model {shlex.quote(model)}"
        super().__init__("pi", template or ("pi -p" + flags + " {prompt}"))


# -- GlossX --------------------------------------------------------------------------
@dataclass
class GlossXSystem:
    """GlossX through its HTTP API. Papers must already be imported into the
    library; ``paper_ids`` maps a task's paper file name to its library id
    (``None`` when GlossX refused the file at import)."""

    base_url: str = "http://127.0.0.1:8000"
    paper_ids: dict[str, str | None] = field(default_factory=dict)
    workflow: str = "auto"
    loop: str = "auto"
    provider: str | None = None
    name: str = "glossx"
    ablate: tuple[str, ...] = ()

    def _call(self, method: str, path: str, body: dict | None = None) -> dict:
        req = urllib.request.Request(
            self.base_url + path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())

    def run(self, task: Task, workdir: Path, timeout_s: float) -> Output:
        names = [Path(p).name for p in task.papers]
        rejected = [n for n in names if n in self.paper_ids and self.paper_ids[n] is None]
        if rejected and len(rejected) == len(names):
            # GlossX refused every paper at import (unreadable PDF): that refusal is its answer
            verdict = "Verdict: NOT ENOUGH EVIDENCE\n" if task.kind == "claim" else ""
            return Output(answer=f"{verdict}GlossX could not import {', '.join(rejected)}: the PDF is unreadable.",
                          raw={"import_rejected": rejected})
        ids = [self.paper_ids[n] for n in names if self.paper_ids.get(n)]
        start = time.monotonic()
        body = {
            "goal": task_prompt(task), "paper_ids": ids,
            "workflow": self.workflow, "loop": self.loop, "provider": self.provider,
        }
        if self.ablate:
            body["ablate"] = list(self.ablate)
        if task.kind == "route":
            # only the routing decision is scored: one LLM call (the router), then stop
            body["goal"] = task.question
            body["budget"] = {"max_llm_calls": 1}
        snap = self._call("POST", "/api/agent/runs", body)
        while snap.get("status") not in {"completed", "failed", "cancelled"}:
            if time.monotonic() - start > timeout_s:
                self._call("DELETE", f"/api/agent/runs/{snap['id']}")
                return Output(error=f"timeout after {timeout_s:.0f}s", latency_s=timeout_s)
            if snap.get("status") == "awaiting_approval":
                return Output(error="needs approval", latency_s=time.monotonic() - start, raw=snap)
            time.sleep(2)
            snap = self._call("GET", f"/api/agent/runs/{snap['id']}")
        # full run snapshot (route, plan, every event, verdicts): the success/failure trace
        save_trace(workdir, "glossx-run.json", json.dumps(snap, ensure_ascii=False, indent=1, default=str))
        return self.to_output(snap, time.monotonic() - start)

    def to_output(self, snap: dict, latency: float) -> Output:
        result = snap.get("result") or {}
        by_id = {c["id"]: c for c in result.get("citations") or []}
        names = {v: k for k, v in self.paper_ids.items()}
        citations = []
        for claim in result.get("claims") or []:
            for sid in claim.get("span_ids") or []:
                span = by_id.get(sid)
                if span:
                    page = span.get("page")
                    citations.append({
                        "claim": claim.get("text"), "paper": names.get(span.get("paper_id"), span.get("paper_id")),
                        "page": page + 1 if isinstance(page, int) else None, "quote": span.get("text", ""),
                    })
        claims = result.get("claims") or []
        conf = [c.get("confidence") for c in claims if isinstance(c.get("confidence"), (int, float))]
        budget = snap.get("budget") or {}
        out = output_from_text(str(result.get("answer") or ""))
        # The workflow API can produce span citations outside its answer field.
        # Keep that native evidence mapping instead of asking the scorer to
        # infer a paper name from model prose.
        out.citations = citations or out.citations
        out.confidence = sum(conf) / len(conf) if conf else out.confidence
        out.latency_s = latency
        out.tokens_in = budget.get("tokens_est")
        out.tool_calls = budget.get("steps")
        out.error = snap.get("error")
        if snap.get("status") in {"failed", "cancelled"} and not out.error:
            out.error = f"run {snap['status']}"
        out.raw.update(stop_reason=result.get("stop_reason"), route=snap.get("route"))
        return out


# -- Gloss v1 chat (baseline) ----------------------------------------------------------
@dataclass
class GlossChatSystem:
    """Baseline B0/B1: the single-prompt, BM25-grounded paper chat that Gloss
    v1.0.2 shipped, reached through the same backend (``/api/ai/chat``). It
    answers over one paper only, so multi-paper tasks see just their first
    paper; that limitation is part of what the baseline measures."""

    base_url: str = "http://127.0.0.1:8000"
    paper_ids: dict[str, str | None] = field(default_factory=dict)
    provider: str | None = None
    name: str = "gloss-chat"

    def run(self, task: Task, workdir: Path, timeout_s: float) -> Output:
        names = [Path(p).name for p in task.papers]
        ids = [self.paper_ids.get(n) for n in names]
        paper_id = next((i for i in ids if i), None)
        if names and paper_id is None:
            verdict = "Verdict: NOT ENOUGH EVIDENCE\n" if task.kind == "claim" else ""
            return Output(answer=f"{verdict}Gloss could not import {', '.join(names)}.",
                          raw={"import_rejected": names})
        body = {"paper_id": paper_id, "messages": [{"role": "user", "content": task_prompt(task)}]}
        if self.provider:
            body["provider"] = self.provider
        req = urllib.request.Request(
            self.base_url + "/api/ai/chat", method="POST", data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        start = time.monotonic()
        parts: list[str] = []
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                for line in resp:
                    line = line.decode("utf-8", "replace").strip()
                    if not line.startswith("data:"):
                        continue
                    try:
                        ev = json.loads(line[5:].strip())
                    except ValueError:
                        continue
                    if isinstance(ev, dict) and ev.get("error"):
                        return Output(error=str(ev["error"]), latency_s=time.monotonic() - start)
                    if isinstance(ev, dict) and isinstance(ev.get("delta"), str):
                        parts.append(ev["delta"])
                    if time.monotonic() - start > timeout_s:
                        return Output(error=f"timeout after {timeout_s:.0f}s", latency_s=timeout_s)
        except OSError as error:
            return Output(error=f"chat request failed: {error}", latency_s=time.monotonic() - start)
        save_trace(workdir, "chat.txt", "".join(parts))
        out = output_from_text("".join(parts))
        out.latency_s = time.monotonic() - start
        out.tool_calls = 0
        return out
