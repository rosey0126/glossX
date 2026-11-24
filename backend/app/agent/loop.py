"""The GlossX core agent: route -> plan -> execute -> verify -> reflect.

:func:`run_agent` drives one goal to a grounded answer:

1. **Context**: recall the project's memory notes relevant to the goal.
2. **Route**: the decider picks a built-in or ranked plugin workflow, or
   ``generic``, based on intent. Missing explicitly referenced papers are
   checked after this choice. The loop is the requested one, else the
   workflow's ``loop.use``, else ``plan-execute-verify``.
3. **Workflow** (if routed): the engine runs the manifest's steps.
4. **Loop**: plan/execute (generic) then synthesize -> verify -> reflect.
5. **Repair**: claims the verifier judged unsupported are removed from the
   answer and listed separately as ``rejected_claims``.
6. **Memory**: supported claims are appended to the project's memory.

Every claim in the answer cites evidence spans (``[S:<paper_id>#<chunk>]``)
and is graded by the verifier. Step failures become observations; only an
unrecoverable synthesis failure in the first round fails the run. Every
provider call is metered against the run's budget.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable

from ..config import output_language
from ..providers import registry as providers
from . import projects
from .capabilities import CapabilityRegistry, RunContext
from .context import SpanStore, WorkingContext
from .core import (  # re-exported for backwards compatibility
    MAX_PLAN_STEPS,
    MAX_STEP_EXECUTIONS,
    STEP_TIMEOUT,
    RunState,
    err,
    event,
    final,
    repair,
)
from .decider import get_decider
from .gate import BudgetExceeded, BudgetMeter, Gate
from .loops import DEFAULT_LOOP, LOOPS, normalize_loop_id
from .workflow import execute_workflow, manifest_for

Emit = Callable[[dict[str, Any]], None]
ROUTE_TOP_K = 5
MEMORY_TOP_K = 5
GENERIC_CARD = (
    "Direct single-paper lookup or ordinary conversation, such as returning a title, "
    "authors, equation, or figure description. No specialized task fits."
)
ROUTE_QUESTION = (
    "Choose the workflow by the user's intent in any language, even if the necessary "
    "papers are missing. Use the available workflow cards and these boundaries:\n"
    "- Tutoring: teach a learner, explain step by step for learning, or give practice "
    "questions. This includes requests with no specific paper.\n"
    "- Claim verification: test an asserted fact against evidence, including whether "
    "a paper actually reports a particular result, statistic, or experimental detail.\n"
    "- Cross-paper QA: answer a specific comparison using multiple papers, even if "
    "the comparison is simple. Use literature review for open-ended surveys.\n"
    "- Reproduction: recreate or run a paper's method or experiment. Use team review "
    "when the goal calls for a team of readers and critics.\n"
    "- Generic: direct title, author, section, equation, or figure lookups and goals "
    "not covered by an available workflow.\n"
    "Independently set source_scope to 'selected' if the goal depends on a specific "
    "user-referenced selection or attachment (e.g. 'this paper', 'the selected papers', "
    "'这篇论文', '附件'). This includes implicit references such as asking what 'the authors' "
    "reported in 'the appendix' without naming the paper or supplying the relevant text. "
    "Set it to 'open' for general topics, requests to find papers or identify papers by title "
    "in the library, and requests that include the needed source text. Do not infer selected scope "
    "just because papers happen to be present."
)

__all__ = [
    "MAX_PLAN_STEPS",
    "MAX_STEP_EXECUTIONS",
    "STEP_TIMEOUT",
    "route",
    "run_agent",
]


async def route(state: RunState) -> dict[str, Any]:
    """Pick a workflow and loop, with source scope and fallback diagnostics."""
    run, registry, emit = state.run, state.registry, state.emit
    requested_wf = str(getattr(run, "workflow", None) or "auto")
    requested_loop = normalize_loop_id(getattr(run, "loop", None))
    workflow: str | None = None
    reason = ""
    confidence = 1.0
    source_scope = None
    failed = False
    emit(event("route", "started", "routing the goal"))

    if requested_wf == "generic":
        reason = "generic loop requested"
    elif requested_wf != "auto":
        if manifest_for(registry, requested_wf):
            workflow, reason = requested_wf, "workflow requested"
        else:
            reason = f"requested workflow {requested_wf} is not available; using the generic loop"
            confidence = 0.0
            failed = True
    else:
        candidates = registry.ranked(state.wc.goal, ROUTE_TOP_K, kinds={"workflow"})
        if not candidates:
            reason = "no workflows installed"
        else:
            # Keyword ranking still limits plugin candidates. It should not hide
            # built-ins from short requests or languages absent from their cards.
            included = {c.name for c in candidates}
            candidates.extend(c for c in registry.all()
                              if c.kind == "workflow" and c.source == "builtin" and c.name not in included)
            options = [{"id": c.name, "card": c.card} for c in candidates]
            options.append({"id": "generic", "card": GENERIC_CARD})
            context = f"GOAL: {state.wc.goal}"
            try:
                choose = getattr(state.decider, "decide_route", state.decider.decide)
                decision = await choose(ROUTE_QUESTION, options, context)
                if decision["choice"] not in {opt["id"] for opt in options}:
                    raise ValueError("router selected an unavailable workflow")
                workflow = decision["choice"] if decision["choice"] != "generic" else None
                source_scope = decision.get("source_scope")
                reason = decision["reason"] or ("routed to " + (workflow or "generic"))
                confidence = decision["confidence"]
            except (asyncio.CancelledError, BudgetExceeded):
                raise
            except Exception as error:
                workflow, source_scope = None, None
                reason = f"router failed, using the generic loop: {err(error)}"
                confidence = 0.0
                failed = True

    loop_id = requested_loop
    if loop_id is None and workflow:
        manifest = manifest_for(registry, workflow) or {}
        use = ((manifest.get("loop") or {}).get("use") or "").removeprefix("loop:")
        loop_id = use if use in LOOPS else None
    loop_id = loop_id or DEFAULT_LOOP
    result = {"workflow": workflow, "loop": loop_id, "reason": reason[:500],
              "confidence": round(float(confidence), 3)}
    if source_scope == "selected":
        result["source_scope"] = source_scope
    if failed:
        result["failed"] = True
    emit(event("route", "failed" if failed else "completed",
               f"workflow={workflow or 'generic'}, loop={loop_id}: {reason}"[:600]))
    return result


async def run_agent(
    run: Any,
    registry: CapabilityRegistry,
    spans: SpanStore,
    emit: Emit,
) -> dict:
    """Drive one goal to a verified, cited answer.

    ``run`` needs ``id``, ``goal``, ``paper_ids``, ``max_rounds``, ``provider``
    and ``import_jobs`` attributes, and may carry ``project_id``, ``workflow``,
    ``loop``, ``meter`` (:class:`BudgetMeter`) and ``gate`` (:class:`Gate`).
    ``run.plan`` and ``run.route`` are updated as the run evolves.
    """
    meter = getattr(run, "meter", None) or BudgetMeter(emit=emit)
    gate = getattr(run, "gate", None) or Gate(emit)
    project_id = getattr(run, "project_id", None)
    decider = get_decider(getattr(run, "decider", None), provider=run.provider)
    ctx = RunContext(
        run_id=run.id,
        paper_ids=list(run.paper_ids),
        spans=spans,
        import_jobs=getattr(run, "import_jobs", None),
        provider=run.provider,
        project_id=project_id,
        goal=run.goal,
        decider=decider,
        emit=emit,
    )
    state = RunState(
        run=run,
        registry=registry,
        spans=spans,
        ctx=ctx,
        wc=WorkingContext(run.goal, ctx.paper_ids),
        meter=meter,
        gate=gate,
        decider=decider,
        emit=emit,
        max_rounds=max(1, int(run.max_rounds or 1)),
    )
    first_paper = ctx.paper_ids[0] if ctx.paper_ids else None
    with providers.usage_context("agent", paper_id=first_paper), providers.call_meter(meter):
        return await _drive(state)


async def _drive(state: RunState) -> dict:
    run, emit = state.run, state.emit
    project_id = state.ctx.project_id

    if project_id:
        notes = projects.recall(project_id, state.wc.goal, k=MEMORY_TOP_K)
        state.wc.memory_notes = [{"id": n["id"], "text": n["text"]} for n in notes]
        emit(event("plan", "info", f"recalled {len(notes)} project memory note(s)"))

    try:
        decision = await route(state)
        run.route = decision
        min_papers = 2 if decision["workflow"] in {"workflow.cross-paper-qa", "workflow.team-review"} else 1
        if decision.get("source_scope") == "selected" and len(state.ctx.paper_ids) < min_papers:
            lang = output_language().lower()
            if "中文" in lang or "chinese" in lang:
                answer = f"请先在文库中选择或上传至少 {min_papers} 篇你要分析的论文，然后重新运行。"
            else:
                answer = f"Select or upload at least {min_papers} of the relevant papers, then run the task again."
            state.draft = {"answer": answer, "claims": []}
            state.stop_reason = "missing_papers"
            emit(event("final", "completed", "stop_reason=missing_papers"))
            return final(state)
        manifest = manifest_for(state.registry, decision["workflow"]) if decision["workflow"] else None
        if manifest:
            stop = dict((manifest.get("loop") or {}).get("stop") or {})
            state.stop = stop
            if stop.get("max_rounds") and not getattr(run, "max_rounds_explicit", False):
                state.max_rounds = int(stop["max_rounds"])
            await execute_workflow(state, manifest)
        await LOOPS[decision["loop"]].run(state)
    except BudgetExceeded as error:
        state.stop_reason = "budget"
        emit(event("budget", "stopped", f"run stopped: {err(error)}"))
    # unsupported claims never reach the answer, the claim list or project memory
    await repair(state)
    if state.gate.denied and (
        state.stop_reason == "no_progress"
        or (state.stop_reason in {"goal_met", "max_rounds"}
            and not any(c.get("verdict") == "supported" for c in state.claims))
    ):
        # denied approvals blocked the evidence this goal needed
        state.stop_reason = "approval_needed"
    if state.draft is None:
        state.draft = {"answer": "", "claims": []}
    if state.rounds == 0 and state.draft["answer"]:
        state.rounds = 1

    result = final(state)
    if project_id:
        try:
            added = projects.remember_claims(project_id, run.id, result["claims"])
            if added:
                emit(event("final", "info", f"saved {added} supported claim(s) to project memory"))
        except Exception as error:  # memory is best-effort; never fail the run
            emit(event("final", "info", f"could not update project memory: {err(error)}"))
    emit(event("final", "completed",
               f"stop_reason={result['stop_reason']}, {len(result['claims'])} claim(s), "
               f"{len(result['citations'])} citation(s)"))
    return result
