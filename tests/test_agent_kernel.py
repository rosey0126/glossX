"""Unit tests for the GlossX agent kernel (``backend/app/agent``).

Unlike the black-box API tests, these drive the kernel in-process with a
scripted fake provider: ``providers.registry.complete`` is replaced by a
function that answers each role (planner, writer, verifier, ...) by
recognising its system prompt. Papers live in an in-memory span store, so no
PDF, network or real model is involved.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from app.agent import core
from app.agent.capabilities import Capability, CapabilityRegistry, build_registry
from app.agent.context import SpanStore
from app.agent.decider import LLMJsonDecider
from app.agent.gate import BudgetMeter
from app.agent.loop import run_agent
from app.agent.loops import LOOPS, normalize_loop_id
from app.features import retrieval
from app.agent.workflow import ROLE_ALIASES, builtin_manifests, render_args
from app.plugins import manager
from app.providers import registry as providers

PAPERS = {
    "p1": [
        "The Transformer uses multi-head self-attention instead of recurrence.",
        "On WMT 2014 English-German the big Transformer reaches 28.4 BLEU.",
    ],
    "p2": [
        "ConvS2S replaces recurrence with convolutions over the sequence.",
        "ConvS2S reaches 25.2 BLEU on WMT 2014 English-German.",
    ],
}


class MemorySpanStore(SpanStore):
    """A span store over the in-memory ``PAPERS`` (no library access)."""

    def _load(self, paper_id: str) -> list[dict]:
        if paper_id not in self._chunks:
            self._chunks[paper_id] = [
                {"text": text, "tokens": retrieval._tok(text), "page": i, "bbox": [0, 0, 10, 10],
                 "span_index": i}
                for i, text in enumerate(PAPERS.get(paper_id, []))
            ]
            self._titles[paper_id] = paper_id.upper()
        return self._chunks[paper_id]


class FakeLLM:
    """Answers each kernel role by its system prompt; records every call."""

    def __init__(self, **overrides):
        self.calls: list[tuple[str, str, str]] = []
        self.overrides = overrides

    def role(self, system: str) -> str:
        table = [
            ("You repair a research answer", "repair"),
            ("self-reflection step", "critique"),
            ("reflection step of GlossX", "reflect"),
            ("planner of GlossX", "plan"),
            ("You plan a literature search", "wf_plan"),
            ("decider of GlossX", "decide"),
            ("strict fact checker", "verify"),
            ("strict judge", "judge"),
            ("critic of a GlossX reading team", "critic"),  # mentions readers: match first
            ("reader sub-agent", "reader"),
            ("careful research agent", "synth"),
            ("academic translator", "translate"),
        ]
        for needle, name in table:
            if needle in system:
                return name
        raise AssertionError(f"unexpected prompt: {system[:120]}")

    def default(self, role: str, user: str):
        if role == "plan":
            return {"sub_questions": ["What BLEU does each model reach?"], "steps": [
                {"id": "s1", "capability": "paper.search_spans",
                 "args": {"query": "BLEU WMT 2014"}, "purpose": "find scores"},
            ]}
        if role == "wf_plan":
            return {"sub_questions": ["BLEU of each model"], "queries": ["BLEU WMT 2014"]}
        if role == "synth":
            return {
                "answer": "The Transformer reaches 28.4 BLEU [S:p1#1]. It was trained on Mars [S:p1#0]. "
                          "Made-up support [S:p9#3].",
                "claims": [
                    {"text": "The Transformer reaches 28.4 BLEU.", "span_ids": ["p1#1"]},
                    {"text": "It was trained on Mars.", "span_ids": ["p1#0", "p9#3"]},
                ],
            }
        if role == "verify":
            return {"verdicts": [
                {"i": 0, "verdict": "supported", "confidence": 0.9, "note": "stated"},
                {"i": 1, "verdict": "unsupported", "confidence": 0.8, "note": "not stated"},
            ]}
        if role == "repair":
            return {"answer": "The Transformer reaches 28.4 BLEU [S:p1#1]. Invented [S:p7#1]."}
        if role == "reflect":
            return {"decision": "stop", "reason": "covered"}
        if role == "critique":
            return {"done": False, "lessons": ["search for the training data"]}
        if role == "decide":
            return {"choice": "generic", "confidence": 0.7, "reason": "focused question"}
        if role == "judge":
            return {"verdict": "supported", "confidence": 0.9, "note": "relevant"}
        if role == "translate":
            return "译文: " + user[:40]
        if role == "critic":
            return {"conflicts": [{"finding_ids": ["r0.f0", "r1.f0"], "issue": "different BLEU"},
                                  {"finding_ids": ["r9.f9"], "issue": "made up"}],
                    "unsupported": [],
                    "challenges": [{"paper_id": "p2", "question": "Which test set gives 25.2 BLEU?"},
                                   {"paper_id": "p9", "question": "not a paper the team read"}]}
        if role == "reader":
            pid = "p1" if "p1#" in user else "p2"
            return {"relevance": 0.8, "findings": [{"claim": "a score", "span_ids": [f"{pid}#1"]}]}
        raise AssertionError(role)

    async def complete(self, system, messages, *, provider=None, model=None):
        role = self.role(system)
        user = messages[-1]["content"]
        self.calls.append((role, system, user))
        override = self.overrides.get(role)
        if isinstance(override, Exception):
            raise override
        out = override(user) if callable(override) else (override or self.default(role, user))
        return json.dumps(out), {}

    def users(self, role: str) -> list[str]:
        return [u for r, _, u in self.calls if r == role]


@pytest.fixture(scope="module", autouse=True)
def library_schema():
    from app.library import store

    store.init_db()  # scope titles are looked up in the (empty) test library


@pytest.fixture(autouse=True)
def library_papers(monkeypatch):
    """``p1``/``p2`` exist as library papers (metadata only; text is in ``PAPERS``)."""
    from app.library import store

    real = store.get_paper
    monkeypatch.setattr(store, "get_paper", lambda pid: (
        {"id": pid, "title": pid.upper(), "year": 2017} if pid in PAPERS else real(pid)))


@pytest.fixture
def fake_llm(monkeypatch):
    def install(**overrides) -> FakeLLM:
        llm = FakeLLM(**overrides)
        monkeypatch.setattr(providers, "complete", llm.complete)
        return llm

    return install


def make_run(goal="Compare BLEU of the Transformer and ConvS2S", **extra):
    run = SimpleNamespace(
        id="run-test", goal=goal, paper_ids=["p1", "p2"], max_rounds=2, provider=None,
        import_jobs=None, project_id=None, workflow="generic", loop=None, plan=None, route=None,
    )
    for key, value in extra.items():
        setattr(run, key, value)
    return run


def drive(run, registry=None):
    events: list[dict] = []
    registry = registry or build_registry(connections={})
    result = asyncio.run(run_agent(run, registry, MemorySpanStore(), events.append))
    return result, events


# -- registry and templating ---------------------------------------------------
def test_registry_resolves_kind_aliases_and_ranks_by_card():
    reg = build_registry(connections={})
    assert reg.resolve("tool:scholar.search") is reg.get("scholar.search")
    assert reg.resolve("agent:reader") is reg.get("agent.reader")
    assert reg.resolve("nope:missing") is None
    top = reg.ranked("search semantic scholar arxiv for papers", k=1)
    assert top[0].name == "scholar.search"


def test_registry_rejects_unknown_kind():
    async def handler(args, ctx):
        return {}

    with pytest.raises(ValueError):
        CapabilityRegistry().register(Capability("x", "gadget", "card", {}, handler))


def test_render_args_projects_lists_and_fills_strings():
    scope = {"goal": "g", "screen": {"accepted": [{"paper_id": "p1"}, {"paper_id": "p2"}]},
             "item": {"title": "T"}}
    out = render_args({"ids": "{{screen.accepted.paper_id}}", "q": "about {{item.title}}",
                       "missing": "{{nothing}}"}, scope)
    assert out == {"ids": ["p1", "p2"], "q": "about T"}


def test_normalize_steps_drops_unknown_capabilities_and_bad_deps():
    state = SimpleNamespace(registry=build_registry(connections={}), emit=lambda e: None,
                            ctx=SimpleNamespace(project_id=None))
    steps = core.normalize_steps([
        {"id": "a", "capability": "paper.search_spans", "args": {"query": "x"}, "depends_on": ["zz"]},
        {"id": "a", "capability": "paper.read", "depends_on": ["a"]},
        {"id": "c", "capability": "workflow.literature-review"},
        {"id": "d", "capability": "does.not.exist"},
    ], state, prefix="s", taken=set(), phase="plan")
    assert [s["capability"] for s in steps] == ["paper.search_spans", "paper.read"]
    assert steps[0]["depends_on"] == []
    assert steps[1]["id"] != "a" and steps[1]["depends_on"] == ["a"]


# -- workflows and loops --------------------------------------------------------
def test_builtin_workflows_validate_and_use_known_capabilities():
    manifests = {m["id"]: m for m in builtin_manifests()}
    assert {"literature-review", "cross-paper-qa", "claim-verification", "tutoring",
            "reproduction", "team-review"} <= set(manifests)
    reg = build_registry(connections={"cli_agents": {"codex": {"enabled": True},
                                                     "claude": {"enabled": True}}})
    for manifest in manifests.values():
        assert manifest["loop"]["use"].removeprefix("loop:") in LOOPS
        for step in manifest["steps"]:
            for use in [step["use"], *step["fallback"]]:
                known = use in ROLE_ALIASES or reg.resolve(use) is not None or use.startswith("mcp.")
                assert known, f"{manifest['id']}: unknown capability {use}"


def test_loop_ids_and_patience_validation():
    assert normalize_loop_id("loop:reflexion") == "reflexion"
    assert normalize_loop_id("auto") is None
    with pytest.raises(ValueError):
        normalize_loop_id("loop:nope")
    base = {"api_version": 2, "id": "wf-x", "kind": "workflow", "name": "X",
            "capability": {"card": "Do x."}, "steps": [{"id": "plan", "use": "agent.planner"}]}
    ok = manager.validate_manifest_v2({**base, "loop": {"use": "reflexion", "stop": {"patience": 2}}})
    assert ok["loop"] == {"use": "loop:reflexion", "stop": {"patience": 2}}
    with pytest.raises(ValueError):
        manager.validate_manifest_v2({**base, "loop": {"stop": {"patience": 9}}})


# -- end-to-end runs with the fake provider -------------------------------------
def test_generic_run_repairs_unsupported_claims(fake_llm):
    llm = fake_llm()
    result, events = drive(make_run())
    assert [c["text"] for c in result["claims"]] == ["The Transformer reaches 28.4 BLEU."]
    assert [c["text"] for c in result["rejected_claims"]] == ["It was trained on Mars."]
    assert "Mars" not in result["answer"]
    # citation markers the repair invented are stripped; real ones stay
    assert "[S:p1#1]" in result["answer"] and "p7#1" not in result["answer"]
    assert {c["id"] for c in result["citations"]} == {"p1#1"}
    # the synthesizer never got to cite a span it was not shown
    assert all("p9#3" not in sid for c in result["claims"] + result["rejected_claims"]
               for sid in c["span_ids"])
    assert result["stop_reason"] == "goal_met"
    assert len(llm.users("repair")) == 1
    assert any(e["phase"] == "verify" and "repaired" in e["detail"] for e in events)


def test_repair_failure_keeps_text_but_drops_claim(fake_llm):
    fake_llm(repair=RuntimeError("provider down"))
    result, events = drive(make_run())
    assert "Mars" in result["answer"]
    assert [c["text"] for c in result["claims"]] == ["The Transformer reaches 28.4 BLEU."]
    assert any(e["phase"] == "verify" and e["status"] == "failed" for e in events)


def test_no_repair_call_when_every_claim_is_supported(fake_llm):
    llm = fake_llm(verify={"verdicts": [{"i": 0, "verdict": "supported", "confidence": 1},
                                        {"i": 1, "verdict": "partial", "confidence": 0.5}]})
    result, _ = drive(make_run())
    assert llm.users("repair") == []
    assert len(result["claims"]) == 2 and result["rejected_claims"] == []


def test_verify_ablation_skips_the_verifier_and_keeps_every_claim(fake_llm):
    llm = fake_llm()
    result, events = drive(make_run(ablate=["verify"]))
    assert llm.users("verify") == [] and llm.users("repair") == []
    assert "Mars" in result["answer"] and result["rejected_claims"] == []
    assert {c["verdict"] for c in result["claims"]} == {"partial"}
    assert any(e["phase"] == "verify" and "ablation" in e["detail"] for e in events)


def test_run_manager_validates_ablations():
    from app.agent import runs

    manager = runs.AgentRunManager.__new__(runs.AgentRunManager)
    manager._accepting = True
    with pytest.raises(ValueError, match="unknown ablation"):
        manager.start("goal", [], ablate=["planner"])


def test_short_answer_contract_reaches_writer_and_repair(fake_llm):
    llm = fake_llm()
    drive(make_run(goal="What BLEU does the Transformer reach? Begin with Answer: followed by the number."))
    prompts = {role: system for role, system, _ in llm.calls if role in {"synth", "repair"}}
    assert prompts.keys() == {"synth", "repair"}
    for prompt in prompts.values():
        assert "only the shortest complete answer on that line" in prompt
        assert "Cite the short answer in that supporting text" in prompt


def test_reflexion_feeds_lessons_into_the_next_plan_and_stops_without_progress(fake_llm):
    llm = fake_llm()
    result, events = drive(make_run(loop="reflexion", max_rounds=3))
    plans = llm.users("plan")
    assert len(plans) == 2
    assert "LESSONS FROM EARLIER ROUNDS" not in plans[0]
    assert "search for the training data" in plans[1]
    # same verdicts every round -> coverage never improves -> stop after one stale round
    assert result["stop_reason"] == "no_progress"
    assert result["rounds"] == 2


def test_reflexion_stops_when_critique_says_done(fake_llm):
    llm = fake_llm(critique={"done": True, "lessons": []})
    result, _ = drive(make_run(loop="reflexion", max_rounds=3))
    assert result["stop_reason"] == "goal_met" and result["rounds"] == 1
    assert len(llm.users("plan")) == 1


def test_cross_paper_qa_workflow_reads_every_scope_paper(fake_llm):
    llm = fake_llm()
    run = make_run(workflow="workflow.cross-paper-qa")
    result, events = drive(run)
    assert run.route["workflow"] == "workflow.cross-paper-qa"
    assert run.route["loop"] == "plan-execute-verify"
    readers = llm.users("reader")
    assert len(readers) == 2 and any("p1#" in u for u in readers) and any("p2#" in u for u in readers)
    # the workflow's writer instructions reach the synthesizer
    assert "compare what each paper says" in llm.users("synth")[0]
    # passages were searched across the accepted papers
    passages = [s for s in run.plan["steps"] if s.get("workflow_step") == "passages"]
    assert passages and passages[0]["args"]["paper_ids"] == ["p1", "p2"]
    assert result["claims"]


def test_team_review_runs_a_critic_and_a_rebuttal_round(fake_llm):
    llm = fake_llm()
    run = make_run(workflow="workflow.team-review")
    result, _ = drive(run)
    critic_input = llm.users("critic")
    assert len(critic_input) == 1 and "[r0.f0]" in critic_input[0] and "[r1.f0]" in critic_input[0]
    readers = llm.users("reader")
    # one reader per paper, then one rebuttal for the critic's valid challenge (p9 is dropped)
    assert len(readers) == 3 and "Which test set gives 25.2 BLEU?" in readers[2]
    critic_step = next(s for s in run.plan["steps"] if s.get("workflow_step") == "critic")
    assert critic_step["status"] == "completed"
    assert result["claims"]


def test_claim_verification_workflow_runs_on_reflexion(fake_llm):
    fake_llm(synth={"answer": "Verdict: SUPPORTED\n\n28.4 BLEU [S:p1#1].",
                    "claims": [{"text": "28.4 BLEU", "span_ids": ["p1#1"]}]},
             verify={"verdicts": [{"i": 0, "verdict": "supported", "confidence": 0.9}]})
    run = make_run(goal="The Transformer reaches 28.4 BLEU on WMT14 En-De",
                   workflow="workflow.claim-verification")
    result, _ = drive(run)
    assert run.route["loop"] == "reflexion"
    assert result["answer"].startswith("Verdict: SUPPORTED")
    assert result["stop_reason"] == "goal_met"  # coverage 1.0 >= 0.9


def test_auto_routing_uses_the_decider_choice(fake_llm):
    fake_llm(decide={"choice": "workflow.tutoring", "confidence": 0.8, "reason": "teaching request"})
    run = make_run(goal="Explain self-attention to me like a student", workflow="auto")
    drive(run)
    assert run.route["workflow"] == "workflow.tutoring"


@pytest.mark.parametrize(("goal", "workflow", "selected", "min_papers"), [
    ("用简单的话解释一下什么是对比学习，并给我出三道练习题。", "tutoring", False, 1),
    ("我看不懂这篇论文里的 KL 散度那一节，能一步一步讲给我吗？", "tutoring", True, 1),
    ("这句话对不对：作者在附录里报告了方差。", "claim-verification", True, 1),
    ("Which of the selected papers uses the largest pretraining corpus, and how much larger is it than the smallest?",
     "cross-paper-qa", True, 2),
    ("List the authors of the selected paper.", None, True, 1),
    ("Compare Transformer and ConvS2S using the library.", "cross-paper-qa", False, 2),
])
def test_auto_route_intent_does_not_depend_on_attachment_count(
    fake_llm, goal, workflow, selected, min_papers,
):
    expected = f"workflow.{workflow}" if workflow else None
    llm = fake_llm(decide={"choice": expected or "generic", "confidence": 0.9,
                           "source_scope": "selected" if selected else "open"})
    registry = build_registry(connections={})
    # Compare the same question with insufficient and sufficient attached papers.
    missing = make_run(goal=goal, workflow="auto", paper_ids=[])
    ready = make_run(goal=goal, workflow="auto", paper_ids=["p1", "p2"][:min_papers])
    result, events = drive(missing, registry)
    missing_calls = [role for role, _, _ in llm.calls]
    ready_result, _ = drive(ready, registry)
    assert missing.route["workflow"] == ready.route["workflow"] == expected
    route_prompts = [prompt for prompt in llm.users("decide") if "Choose the workflow" in prompt]
    assert len(route_prompts) == 2 and route_prompts[0] == route_prompts[1]
    assert all(f"- workflow.{manifest['id']}:" in route_prompts[0] for manifest in builtin_manifests())
    if selected:
        assert result["stop_reason"] == "missing_papers"
        assert str(min_papers) in result["answer"]
        assert result["citations"] == [] and result["rounds"] == 0
        assert missing_calls == ["decide"]
        assert any(e["phase"] == "final" and "missing_papers" in e["detail"] for e in events)
    else:
        assert result["stop_reason"] != "missing_papers"
        assert "wf_plan" in missing_calls
    assert ready_result["stop_reason"] != "missing_papers"
    if selected and min_papers == 2:
        partial = make_run(goal=goal, workflow="auto", paper_ids=["p1"])
        partial_result, _ = drive(partial, registry)
        assert partial.route["workflow"] == expected
        assert partial_result["stop_reason"] == "missing_papers"


def test_router_invalid_model_choice_records_fallback(fake_llm):
    fake_llm(decide={"choice": "unavailable"})
    run = make_run(workflow="auto")
    result, events = drive(run)
    assert run.route["workflow"] is None and run.route["failed"] is True
    assert any(e["phase"] == "route" and e["status"] == "failed" for e in events)
    assert result["answer"]


def test_budget_exhaustion_stops_with_budget_reason(fake_llm):
    fake_llm()
    run = make_run(meter=BudgetMeter({"max_steps": 1}))
    result, _ = drive(run)
    assert result["stop_reason"] == "budget"


# -- decider --------------------------------------------------------------------
def test_decider_tolerates_decorated_and_invalid_choices(fake_llm):
    fake_llm(decide=lambda user: {"choice": "workflow.x (best)", "confidence": 3})
    out = asyncio.run(LLMJsonDecider().decide("q?", ["workflow.x", "generic"]))
    assert out["choice"] == "workflow.x" and out["confidence"] == 1.0
    fake_llm(decide={"choice": "zzz", "confidence": 0.9})
    out = asyncio.run(LLMJsonDecider().decide("q?", ["a", "b"]))
    assert out == {"choice": "a", "confidence": 0.0, "reason": "invalid choice 'zzz'; defaulted to first option"}


def test_run_api_accepts_every_registered_loop():
    from pydantic import ValidationError

    from app.routers.agent import RunCreateBody

    for loop_id in LOOPS:
        assert RunCreateBody(goal="x", loop=f"loop:{loop_id}").loop == f"loop:{loop_id}"
    with pytest.raises(ValidationError):
        RunCreateBody(goal="x", loop="loop:nope")


# -- shared tools and capability cards -----------------------------------------
def _ctx():
    from app.agent.capabilities import RunContext

    return RunContext(run_id="r1", paper_ids=["p1"], spans=MemorySpanStore())


def test_translate_keeps_span_ids_attached(fake_llm):
    llm = fake_llm()
    cap = build_registry(connections={}).get("paper.translate")
    out = asyncio.run(cap.handler({"span_ids": ["p1#1", "nope#9"], "language": "Chinese"}, _ctx()))
    assert out["span_ids"] == ["p1#1"]
    assert "[S:p1#1]" in llm.users("translate")[0]
    with pytest.raises(ValueError):
        asyncio.run(cap.handler({}, _ctx()))


def test_highlight_anchors_spans_with_their_bbox(monkeypatch):
    from app.library import store

    saved = []
    monkeypatch.setattr(store, "add_highlight",
                        lambda pid, h: saved.append((pid, h)) or {"id": f"h{len(saved)}", **h})
    cap = build_registry(connections={}).get("paper.highlight")
    out = asyncio.run(cap.handler({"span_ids": ["p1#1", "p1#99"], "category": "result"}, _ctx()))
    assert [h["span_id"] for h in out["highlights"]] == ["p1#1"] and out["skipped"] == ["p1#99"]
    pid, h = saved[0]
    assert pid == "p1" and h["page"] == 1 and h["rects"] == [[0, 0, 10, 10]] and h["kind"] == "agent"
    assert cap.side_effects and not cap.approval_permissions()


def test_cards_show_full_schemas_only_for_the_best_matches():
    reg = build_registry(connections={})
    state = SimpleNamespace(registry=reg, ctx=SimpleNamespace(project_id=None),
                            gate=SimpleNamespace(auto_approved=lambda: set()))
    lines = core.cards_text(state, "search evidence passages in papers", k=12).splitlines()
    assert len(lines) == 12
    assert all('args: {' in line for line in lines[:core.FULL_SCHEMA_CARDS])
    assert all('args: [' in line for line in lines[core.FULL_SCHEMA_CARDS:])
    described = reg.get("library.import").describe()
    assert described["side_effects"] == "adds a paper to the library" and described["requirements"] == []


# -- learner model ---------------------------------------------------------------
@pytest.fixture
def learner_dir(monkeypatch, tmp_path):
    from app import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    return tmp_path


def test_learner_mastery_moves_with_quiz_answers(learner_dir):
    from app.agent import learner

    assert learner.record("Self-attention", "explained")["mastery"] == 0.5
    learner.record("self-attention ", "correct")
    entry = learner.record("SELF-ATTENTION", "correct", note="got the scaling factor")
    assert entry["correct"] == 2 and entry["explained"] == 1 and entry["mastery"] == 0.75
    learner.record("Beam search", "wrong")
    names = [c["name"] for c in learner.profile("attention heads")]
    assert names == ["Self-attention"]
    assert {c["name"] for c in learner.profile()} == {"Self-attention", "Beam search"}
    with pytest.raises(ValueError):
        learner.record("x", "maybe")
    assert (learner_dir / "learner.json").exists()


def test_learner_capabilities_are_global_but_project_memory_is_not(learner_dir):
    reg = build_registry(connections={})
    no_project = SimpleNamespace(registry=reg, emit=lambda e: None, ctx=SimpleNamespace(project_id=None),
                                 gate=SimpleNamespace(auto_approved=lambda: set()))
    steps = core.normalize_steps([
        {"id": "a", "capability": "learner.profile", "args": {"query": "attention"}},
        {"id": "b", "capability": "memory.recall", "args": {"query": "attention"}},
    ], no_project, prefix="s", taken=set(), phase="plan")
    assert [s["capability"] for s in steps] == ["learner.profile"]
    names = [c.name for c in core.planner_ranked(no_project, "learner memory recall concepts", 40)]
    assert "learner.profile" in names and not any(n.startswith("memory.") for n in names)
    in_project = SimpleNamespace(**{**vars(no_project), "ctx": SimpleNamespace(project_id="proj1")})
    assert core.planner_can_use(in_project, reg.get("memory.recall"))

    record = reg.get("learner.record")
    out = asyncio.run(record.handler({"concept": "BLEU", "outcome": "correct"}, _ctx()))
    assert out["status"] == "saved" and out["mastery"] == round(2 / 3, 3)
    out = asyncio.run(reg.get("learner.profile").handler({"query": "BLEU score"}, _ctx()))
    assert out["concepts"][0]["name"] == "BLEU"


def test_tutoring_workflow_reads_the_learner_profile(fake_llm, learner_dir):
    from app.agent import learner

    learner.record("BLEU", "wrong", note="confuses BLEU with accuracy")
    llm = fake_llm()
    run = make_run(goal="Teach me how BLEU is used to compare the Transformer and ConvS2S",
                   workflow="workflow.tutoring")
    result, _ = drive(run)
    profile = [s for s in run.plan["steps"] if s.get("workflow_step") == "profile"]
    assert profile and profile[0]["status"] == "completed"
    writer = llm.users("synth")[0]
    assert "confuses BLEU with accuracy" in writer and "mastery score" in writer
    assert result["claims"]


# -- table coalescing & sub-question coverage regressions -----------------------
def test_build_chunks_coalesces_split_pdf_table_with_header_and_caption():
    parsed = {
        "pages": [{
            "index": 6,
            "width": 612.0,
            "height": 792.0,
            "blocks": [
                # Table 2 (caption below)
                {"id": 1, "bbox": [80, 60, 280, 80], "text": "System\nDev\nEM\nF1"},
                {"id": 2, "bbox": [80, 88, 280, 120], "text": "ModelA\n84.1 90.9"},
                {"id": 3, "bbox": [72, 130, 290, 155], "text": "Table 2: SQuAD 1.1 results."},
                # Table 3 (caption below; short <30-char header must not be dropped)
                {"id": 4, "bbox": [80, 200, 280, 220], "text": "System\nDev\nTest\nEM\nF1\nEM\nF1"},
                {"id": 5, "bbox": [80, 228, 280, 260], "text": "Ours\nBERTLARGE (Single)\n78.7 81.9 80.0 83.1"},
                {"id": 6, "bbox": [72, 270, 290, 295], "text": "Table 3: SQuAD 2.0 results."},
                # Prose followed by caption-above Table 4
                {"id": 7, "bbox": [310, 60, 525, 220], "text": "A" * 400},
                {"id": 8, "bbox": [310, 235, 525, 255], "text": "Table 4: Benchmark Z accuracy."},
                {"id": 9, "bbox": [310, 262, 525, 290], "text": "Method\nAcc\nOurs 92.5"},
                # Footer page number should be ignored
                {"id": 10, "bbox": [295, 740, 315, 755], "text": "7"},
            ],
        }]
    }
    chunks = retrieval.build_chunks(parsed)
    hits = retrieval.retrieve("SQuAD 2.0 Dev EM F1 Table 3", chunks, k=1)
    assert hits and "78.7 81.9" in hits[0]["text"]
    assert "System\nDev\nTest\nEM\nF1\nEM\nF1" in hits[0]["text"]
    assert "Table 3: SQuAD 2.0 results." in hits[0]["text"]
    assert "Table 2:" not in hits[0]["text"]

    hits_above = retrieval.retrieve("Benchmark Z accuracy Table 4", chunks, k=1)
    assert hits_above and "Ours 92.5" in hits_above[0]["text"] and "A" * 100 not in hits_above[0]["text"]

    # Symbol-only chunks must not raise ZeroDivisionError in BM25
    sym_chunks = [{"page": 0, "bbox": [0, 0, 10, 10], "block_id": 0, "text": "--- *** ###", "tokens": []}]
    assert retrieval.retrieve("anything", sym_chunks, k=1) == []


def test_missing_sub_questions_triggers_reflect_and_recovers_missing_fact(fake_llm):
    synth_round = {"n": 0}

    def synth(user: str):
        synth_round["n"] += 1
        if synth_round["n"] == 1:
            return {
                "answer": "The Transformer reaches 28.4 BLEU [S:p1#1]. ConvS2S BLEU is not in the supplied spans.",
                "claims": [{"text": "The Transformer reaches 28.4 BLEU.", "span_ids": ["p1#1"]}],
                "missing_sub_questions": ["What BLEU score does ConvS2S reach on WMT 2014 English-German?"],
            }
        return {
            "answer": "The Transformer reaches 28.4 BLEU [S:p1#1] while ConvS2S reaches 25.2 BLEU [S:p2#1].",
            "claims": [
                {"text": "The Transformer reaches 28.4 BLEU.", "span_ids": ["p1#1"]},
                {"text": "ConvS2S reaches 25.2 BLEU.", "span_ids": ["p2#1"]},
            ],
            "missing_sub_questions": [],
        }

    def verify(user: str):
        n = user.count("CLAIM ")
        return {"verdicts": [{"i": i, "verdict": "supported", "confidence": 0.95, "note": "ok"} for i in range(n)]}

    def reflect(user: str):
        assert "UNANSWERED SUB-QUESTIONS" in user and "ConvS2S" in user
        return {
            "decision": "replan",
            "reason": "Need ConvS2S BLEU score",
            "new_steps": [{"id": "r1", "capability": "paper.search_spans",
                           "args": {"query": "ConvS2S BLEU", "paper_ids": ["p2"]}, "purpose": "find ConvS2S BLEU"}],
        }

    llm = fake_llm(synth=synth, verify=verify, reflect=reflect)
    run = make_run(workflow="workflow.cross-paper-qa", max_rounds=2)
    result, _ = drive(run)
    assert result["rounds"] == 2
    assert result["stop_reason"] == "goal_met"
    assert len(llm.users("reflect")) == 1
    assert "25.2 BLEU" in result["answer"]


def test_missing_sub_questions_stops_within_budget_when_paper_lacks_evidence(fake_llm):
    def synth(user: str):
        return {
            "answer": "The Transformer reaches 28.4 BLEU [S:p1#1]. Training energy cost is not reported.",
            "claims": [{"text": "The Transformer reaches 28.4 BLEU.", "span_ids": ["p1#1"]}],
            "missing_sub_questions": ["What is the exact kWh energy cost of training?"],
        }

    def verify(user: str):
        return {"verdicts": [{"i": 0, "verdict": "supported", "confidence": 0.95, "note": "ok"}]}

    def reflect(user: str):
        assert "energy cost" in user
        return {"decision": "stop", "reason": "The paper does not report training energy cost.", "new_steps": []}

    llm = fake_llm(synth=synth, verify=verify, reflect=reflect)
    run = make_run(goal="Give Transformer BLEU and exact kWh energy cost", workflow="workflow.cross-paper-qa", max_rounds=2)
    result, _ = drive(run)
    assert result["rounds"] == 1
    assert result["stop_reason"] == "goal_met"
    assert len(llm.users("reflect")) == 1
    assert "not reported" in result["answer"]
    assert core.coverage(result["claims"], ["missing fact"]) == 0.5


def test_build_chunks_large_table_caption_and_sibling_token_propagation():
    from app.features import retrieval

    # 1. Medium-large table (~620 chars body + ~480 chars caption = ~1100 chars <= 1350):
    #    caption stays attached to the table body in one verbatim chunk.
    body_rows = "\n".join(f"Model-{i}  8{i}.5  7{i}.2  6{i}.1  5{i}.0  4{i}.8" for i in range(1, 16))
    cap_med = (
        "Table 2: Comparison with state of the art on ImageNet benchmark. "
        + "Detailed evaluation protocol notes and standard deviations across three runs. " * 5
    )
    # 2. Very tall table (>1500 chars) split into 3 groups + below-table caption:
    #    middle row chunk keeps verbatim text AND inherits caption/header tokens for BM25.
    tall_blocks = [
        {"id": 10, "bbox": [100, 100, 480, 120], "text": "Network\n#param.\nImNet\ntop-1"},
    ]
    y = 125
    for idx in range(1, 35):
        name = "TargetNet-B-384" if idx == 18 else f"Baseline-{idx:02d}"
        val = "83.1" if idx == 18 else f"7{idx % 10}.4"
        tall_blocks.append({
            "id": 10 + idx,
            "bbox": [100, y, 480, y + 12],
            "text": f"{name}  86M  384  {val}  87.7  72.4",
        })
        y += 14
    tall_blocks.append({
        "id": 99,
        "bbox": [100, y + 8, 480, y + 90],
        "text": "Table 5: Throughput and accuracy on ImageNet for vision models without distillation. " + "Note. " * 60,
    })

    parsed = {
        "pages": [
            {
                "index": 0,
                "width": 612,
                "height": 792,
                "blocks": [
                    {"id": 1, "bbox": [80, 80, 500, 100], "text": "Ours-Big\nImageNet\nCIFAR-10"},
                    {"id": 2, "bbox": [80, 105, 500, 220], "text": body_rows},
                    {"id": 3, "bbox": [80, 230, 500, 310], "text": cap_med},
                ],
            },
            {"index": 1, "width": 612, "height": 792, "blocks": tall_blocks},
        ]
    }
    chunks = retrieval.build_chunks(parsed)
    hits_med = retrieval.retrieve("Table 2 ImageNet Model-9 benchmark", chunks, k=2)
    assert hits_med and "Model-9" in hits_med[0]["text"] and "Table 2:" in hits_med[0]["text"]

    hits_tall = retrieval.retrieve("Table 5 TargetNet-B-384 ImageNet top-1 accuracy without distillation", chunks, k=3)
    target_hit = [h for h in hits_tall if "TargetNet-B-384" in h["text"]]
    assert target_hit, f"Expected TargetNet-B-384 row in top-3, got: {[h['text'][:60] for h in hits_tall]}"
    # Text stays strictly verbatim (does not synthetically prepend caption/header)
    assert "Table 5:" not in target_hit[0]["text"]


def test_evidence_block_rank_interleaves_parallel_searches():
    from app.agent.context import SpanStore, WorkingContext

    class DummySpans(SpanStore):
        def get(self, span_id: str) -> dict | None:
            return {"id": span_id, "paper_id": "p1", "title": "T", "page": 0, "bbox": None, "text": f"fact for {span_id}"}

    wc = WorkingContext("compare six metrics", ["p1"])
    # Simulate 6 parallel Round-2 search steps returning 10 spans each (= 60 total > MAX_EVIDENCE_SPANS).
    for step_idx in range(1, 7):
        spans = [{"id": f"p1#{step_idx * 100 + rank}", "text": f"s{step_idx}r{rank}"} for rank in range(10)]
        wc.observe(f"r{step_idx}", "paper.search_spans", "completed", result={"spans": spans})

    state = core.RunState(
        run=None,
        registry=None,
        spans=DummySpans(),
        ctx=None,
        wc=wc,
        meter=None,
        gate=None,
        decider=None,
        emit=lambda _: None,
        claims=[{"text": "prev claim", "span_ids": ["p1#1"], "verdict": "supported"}],
    )
    _, provided = core.evidence_block(state)
    # Round 1 verified claim span is preserved
    assert "p1#1" in provided
    # Top-ranked hits (#0, #1, #2) of ALL 6 search steps (including earliest r1..r4) are present!
    for step_idx in range(1, 7):
        for rank in range(3):
            assert f"p1#{step_idx * 100 + rank}" in provided, f"Evicted r{step_idx} rank {rank}"
