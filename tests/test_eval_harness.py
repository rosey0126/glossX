"""Unit tests for the evaluation harness in ``eval/`` (no model is called)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))

from glossx_eval import metrics, report, run  # noqa: E402
from glossx_eval.systems import CodexSystem, GlossXSystem, output_from_text, task_prompt  # noqa: E402
from glossx_eval.tasks import Task, from_qasper, from_scifact, load_tasks  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent.parent / "eval"


def test_token_f1_and_exact_match():
    assert metrics.token_f1("The Transformer", "transformer") == 1.0
    assert metrics.best_f1("28.4 BLEU", ["28.4", "41.0 BLEU"]) == pytest.approx(2 / 3)
    assert metrics.exact_match("Yes.", ["yes", "no"]) == 1.0


def test_verdict_parsing_and_label_scores():
    assert metrics.parse_verdict("Verdict: not enough evidence\n...") == "NOT ENOUGH EVIDENCE"
    assert metrics.parse_verdict("no verdict here") is None
    scores = metrics.label_scores([("SUPPORTED", "SUPPORTED"), ("REFUTED", "SUPPORTED"), (None, "REFUTED")])
    assert scores["accuracy"] == pytest.approx(1 / 3)


def test_ece_is_zero_when_calibrated_and_large_when_overconfident():
    assert metrics.ece([1.0, 1.0], [True, True]) == 0.0
    assert metrics.ece([0.95] * 4, [True, False, False, False]) == pytest.approx(0.7)


def test_citation_report_flags_fabricated_and_wrong_page():
    pages = {"papers/a.pdf": ["Intro text here.", "The model reaches 28.4 BLEU on WMT 2014 English-German."]}

    def paper_text(paper, page):
        ps = pages[paper]
        return "\n".join(ps) if page is None else (ps[page - 1] if 1 <= page <= len(ps) else "")

    rep = metrics.citation_report([
        {"paper": "a.pdf", "page": 2, "quote": "reaches 28.4 BLEU on WMT 2014"},
        {"paper": "a.pdf", "page": 1, "quote": "reaches 28.4 BLEU on WMT 2014"},  # wrong page
        {"paper": "a.pdf", "page": 2, "quote": "reaches 35 BLEU on ImageNet"},     # not in the paper
        {"paper": "ghost.pdf", "page": 1, "quote": "anything"},                   # unknown paper
    ], ["papers/a.pdf"], paper_text)
    assert [r["located"] for r in rep["rows"]] == [True, True, False, False]
    assert [r.get("page_ok") for r in rep["rows"][:2]] == [True, False]
    assert rep["fabricated"] == 2 and rep["fabricated_rate"] == 0.5


def test_converters_and_route_seed(tmp_path):
    qasper = {"1706.03762": {"qas": [{"question_id": "q1", "question": "What BLEU?", "answers": [
        {"answer": {"extractive_spans": ["28.4"], "evidence": ["28.4 BLEU"]}},
        {"answer": {"unanswerable": True}}]}]}}
    task = next(from_qasper(qasper))
    assert task.gold["answers"] == ["28.4", "unanswerable"] and task.papers == ["pdfs/1706.03762.pdf"]
    claim = next(from_scifact([{"id": 3, "claim": "X", "cited_doc_ids": [7],
                                "evidence": {"7": [{"label": "CONTRADICT", "sentences": [1]}]}}], {}))
    assert claim.gold["label"] == "REFUTED" and claim.kind == "claim"
    route = load_tasks(EVAL_DIR / "data" / "route100.jsonl")
    assert len(route) == 100 and {t.kind for t in route} == {"route"}
    assert len({t.id for t in route}) == 100
    gold = {t.gold["workflow"] for t in route}
    workflows = {f"workflow.{p.stem.replace('_', '-')}"
                 for p in (EVAL_DIR.parent / "backend" / "app" / "agent" / "workflows").glob("*.json")}
    assert gold == workflows | {None}  # every shipped workflow plus the generic loop
    with pytest.raises(ValueError):
        Task(id="x", suite="s", kind="nope", question="q")


def test_output_parsing_takes_the_last_answer_object():
    out = output_from_text('thinking {"x": 1}\n{"answer": "A", "citations": [{"paper": "a.pdf"}], "confidence": 0.7}')
    assert out.answer == "A" and out.citations == [{"paper": "a.pdf"}] and out.confidence == 0.7
    events = "\n".join(json.dumps(e) for e in [
        {"type": "item.completed", "item": {"type": "command_execution"}},
        {"type": "item.completed", "item": {"type": "agent_message", "text": '{"answer": "B", "citations": []}'}},
        {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 2}},
    ])
    out = CodexSystem().parse(events)
    assert (out.answer, out.tokens_in, out.tool_calls) == ("B", 10, 1)
    assert "verbatim quote" in task_prompt(Task(id="t", suite="s", kind="qa", question="Q?", papers=["p/a.pdf"]))


def test_glossx_output_maps_spans_to_paper_page_quote():
    snap = {"status": "completed", "budget": {"steps": 4, "tokens_est": 900}, "result": {
        "answer": "A [S:lib1#3]", "stop_reason": "goal_met",
        "claims": [{"text": "A", "span_ids": ["lib1#3"], "confidence": 0.8}],
        "citations": [{"id": "lib1#3", "paper_id": "lib1", "page": 0, "text": "quoted text"}]}}
    out = GlossXSystem(paper_ids={"a.pdf": "lib1"}).to_output(snap, 1.5)
    assert out.citations == [{"claim": "A", "paper": "a.pdf", "page": 1, "quote": "quoted text"}]
    assert out.confidence == 0.8 and out.tool_calls == 4


@pytest.mark.parametrize(("status", "route", "correct"), [
    ("completed", {"workflow": None}, True),
    ("completed", None, False),
    ("completed", {"loop": "plan-execute-verify"}, False),
    ("completed", {"workflow": None, "failed": True}, False),
    ("failed", {"workflow": None}, False),
    ("cancelled", {"workflow": None}, False),
    ("completed", {"workflow": "workflow.tutoring"}, False),
])
def test_route_scoring_distinguishes_generic_from_missing_or_failed_decision(status, route, correct):
    task = Task(id="generic", suite="route", kind="route", question="Title?", gold={"workflow": None})
    out = GlossXSystem().to_output({"status": status, "route": route}, 0.0)
    assert run.score(task, out, None)["route_correct"] is correct


def test_dry_run_executes_nothing(capsys):
    assert run.main([str(EVAL_DIR / "data" / "route100.jsonl"), "--systems", "glossx,codex",
                     "--repeats", "2", "--limit", "5"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["runs"] == 20 and plan["tokens_estimate"] == 5 * 5_000 * 2 * 2


def test_report_aggregates_repeats_per_task():
    rows = [
        {"task": t, "suite": "s", "system": "g", "repeat": r,
         "scores": {"f1": v}, "output": {"latency_s": 1.0, "error": None}}
        for t, r, v in [("a", 0, 1.0), ("a", 1, 0.0), ("b", 0, 1.0), ("b", 1, 1.0)]
    ]
    table = report.aggregate(rows)
    assert table[("s", "g")]["f1"][0] == pytest.approx(0.75)
    assert "| s | g | f1 | 0.750 |" in report.render(table)


def test_command_system_passes_the_prompt_as_one_argument(tmp_path):
    from glossx_eval.systems import CommandSystem

    script = tmp_path / "echo_agent.py"
    script.write_text("import json, sys\nprint(json.dumps({'answer': sys.argv[1][:20], 'citations': []}))\n")
    system = CommandSystem("echo", f'"{sys.executable}" "{script}" {{prompt}}')
    out = system.run(Task(id="t", suite="s", kind="qa", question="Q? it's \"quoted\""), tmp_path, 30)
    assert out.error is None and out.answer == task_prompt(
        Task(id="t", suite="s", kind="qa", question="Q? it's \"quoted\""))[:20]
    missing = CommandSystem("nope", "definitely-not-installed-agent {prompt}")
    assert "not installed" in missing.run(Task(id="t", suite="s", kind="qa", question="Q"), tmp_path, 5).error


def test_prepare_scifact_renders_each_abstract_as_a_pdf(tmp_path):
    import io
    import tarfile

    import fitz
    from glossx_eval import prepare

    claims = [
        {"id": 1, "claim": "A causes B.", "evidence": {"7": [{"label": "SUPPORT", "sentences": [0]}]}, "cited_doc_ids": [7]},
        {"id": 2, "claim": "C is mixed.", "cited_doc_ids": [7, 8], "evidence": {
            "7": [{"label": "SUPPORT", "sentences": [0]}], "8": [{"label": "CONTRADICT", "sentences": [0]}]}},
    ]
    corpus = [{"doc_id": 7, "title": "On A", "abstract": ["A causes B in mice."] * 80},
              {"doc_id": 8, "title": "On C", "abstract": ["C does not."]}]
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, rows in (("data/claims_dev.jsonl", claims), ("data/corpus.jsonl", corpus)):
            data = "\n".join(json.dumps(r) for r in rows).encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    tasks = prepare.build_scifact(tmp_path, 10, 0, blob=buf.getvalue())
    assert [t.gold["label"] for t in tasks] == ["SUPPORTED"]  # MIXED is left out
    with fitz.open(tmp_path / tasks[0].papers[0]) as doc:
        assert "A causes B in mice." in doc[0].get_text()  # long abstract still fits


def test_cohen_kappa():
    from glossx_eval.metrics import cohen_kappa

    assert cohen_kappa([("A", "A"), ("B", "B")]) == 1.0
    assert cohen_kappa([("A", "B"), ("B", "A")]) == -1.0
    assert cohen_kappa([("A", "A"), ("A", "B"), ("B", "B"), ("B", "B")]) == pytest.approx(0.5)


def test_judge_labels_located_citations_and_audits_blind(tmp_path):
    from glossx_eval import judge

    pages = {"papers/a.pdf": ["The model reaches 28.4 BLEU on WMT 2014 English-German."]}

    def paper_text(paper, page):
        return "\n".join(pages[paper]) if page is None else pages[paper][page - 1]

    prompts = []

    def fake_judge(prompt):
        prompts.append(prompt)
        return 'thinking... {"verdicts": [{"i": 0, "label": "supports"}, {"i": 1, "label": "maybe"}]}'

    row = {"task": "t1", "system": "codex", "repeat": 0, "scores": {}, "output": {"answer": "x", "citations": [
        {"claim": "It reaches 28.4 BLEU.", "paper": "a.pdf", "page": 1, "quote": "reaches 28.4 BLEU"},
        {"claim": "It is fast.", "paper": "a.pdf", "page": 1, "quote": "28.4 BLEU on WMT 2014"},
        {"claim": "It won.", "paper": "ghost.pdf", "page": 1, "quote": "anything"},
    ]}}
    judge.judge_row(row, ["papers/a.pdf"], paper_text, fake_judge)
    labels = [c["judge"] for c in row["output"]["citations"]]
    assert labels == ["SUPPORTS", None, "UNSUPPORTED"]  # fabricated: no judge call needed
    assert len(prompts) == 1 and "ghost" not in prompts[0] and "anything" not in prompts[0]
    assert row["scores"]["support_rate"] == 0.5 and row["scores"]["judge_failed"] == 1

    audit = judge.sample_audit([row], frac=1.0)
    assert {a["key"] for a in audit} == {row["output"]["citations"][i]["key"] for i in (0, 2)}
    assert all("codex" not in json.dumps(a) for a in audit)
    for a in audit:
        a["human_label"] = "supports" if "28.4" in a["quote"] else "UNSUPPORTED"
    agree = judge.agreement(audit, [row])
    assert agree["n"] == 2 and agree["kappa"] == 1.0


def test_faults_build_injected_and_corrupt_variants(tmp_path):
    import fitz
    from glossx_eval import faults

    src = tmp_path / "pilot"
    (src / "pdfs").mkdir(parents=True)
    with fitz.open() as doc:
        doc.new_page().insert_text((72, 72), "SciBERT improves NER by 1.2 F1.")
        doc.save(src / "pdfs" / "a.pdf")
    tasks = [Task(id="c1", suite="scifact", kind="claim", question="SciBERT helps NER.",
                  papers=["pdfs/a.pdf"], gold={"label": "SUPPORTED"}),
             Task(id="r1", suite="route", kind="route", question="hi", gold={"workflow": "generic"})]
    made = faults.build(tasks, src, tmp_path / "out", ["inject", "corrupt"])
    assert [t.id for t in made] == ["c1+inject", "c1+corrupt"]
    inject, corrupt = made
    assert inject.gold["label"] == "SUPPORTED" and corrupt.gold["label"] == "NOT ENOUGH EVIDENCE"
    with fitz.open(tmp_path / "out" / inject.papers[0]) as doc:
        assert doc.page_count == 2 and inject.gold["canary"] in doc[1].get_text()
    with pytest.raises(Exception):
        fitz.open(tmp_path / "out" / corrupt.papers[0])

    assert faults.score(inject, f"The answer is {inject.gold['canary']}") == {"injection_followed": 1.0}
    qa = Task(id="q+corrupt", suite="qasper+corrupt", kind="qa", question="?", gold={"fault": "corrupt"})
    assert faults.score(qa, "The PDF is corrupted, so I cannot answer.") == {"abstained": 1.0}
    assert run.score(inject, run.Output(answer="Verdict: SUPPORTED"), None)["injection_followed"] == 0.0

    glossx = GlossXSystem(paper_ids={"corrupt-a.pdf": None})
    out = glossx.run(corrupt, tmp_path, 1.0)
    assert out.raw["import_rejected"] == ["corrupt-a.pdf"]
    assert metrics.parse_verdict(out.answer) == "NOT ENOUGH EVIDENCE"


def test_ablation_systems_send_the_ablate_flag(monkeypatch):
    import argparse

    from glossx_eval.run import build_systems
    from glossx_eval.tasks import Task

    args = argparse.Namespace(paper_ids=None, glossx_url="http://x", model=None, pi_provider=None)
    noverify, noreflect, chat = build_systems(["glossx-noverify", "glossx-noreflect", "gloss-chat"], args)
    assert (noverify.name, noreflect.name, chat.name) == ("glossx-noverify", "glossx-noreflect", "gloss-chat")
    sent = []

    def fake_call(self, method, path, body=None):
        sent.append(body)
        return {"id": "r", "status": "completed", "result": {"answer": "ok"}}

    monkeypatch.setattr(type(noverify), "_call", fake_call)
    noverify.run(Task(id="t", suite="s", kind="qa", question="q"), None, 5)
    assert sent[0]["ablate"] == ["verify"]
    with pytest.raises(SystemExit):
        build_systems(["glossx-nothing"], args)


def test_reliability_scenarios_all_recover():
    """Every scripted failure scenario is detected and ends in recovery or a safe stop."""
    import subprocess

    proc = subprocess.run([sys.executable, "-m", "glossx_eval.reliability"], cwd=EVAL_DIR,
                          capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.count("| pass |") == 8


def test_analysis_writes_every_report_snippet(tmp_path):
    """The secondary analyses run on result rows alone and emit LaTeX for the report."""
    from glossx_eval import analysis

    items = tmp_path / "items"
    items.mkdir()
    (items / "C35.jsonl").write_text(json.dumps({"id": "c1", "suite": "s", "kind": "claim", "question": "q",
                                                 "gold": {"label": "NOT ENOUGH EVIDENCE"}}) + "\n")
    (items / "d-deepseek.jsonl").write_text(json.dumps({"id": "d1", "suite": "D", "kind": "qa", "question": "q",
                                                        "gold": {"family": "budget", "answers": ["x"]}}) + "\n")
    route = tmp_path / "route.jsonl"
    route.write_text(json.dumps({"id": "r1", "suite": "route", "kind": "route", "question": "核实一下",
                                 "gold": {"workflow": "workflow.claim-verification"}}) + "\n")
    rows = []
    for rep in range(3):
        for system in ("glossx", "codex"):
            rows.append({"task": "c1", "system": system, "repeat": rep,
                         "output": {"latency_s": 10.0, "tokens_in": 1000, "tool_calls": 3, "raw": {"stop_reason": "goal_met"}},
                         "scores": {"execution_ok": True, "pred_label": "REFUTED", "gold_label": "NOT ENOUGH EVIDENCE",
                                    "label_correct": False}})
            rows.append({"task": "d1", "system": system, "repeat": rep, "output": {"latency_s": 12.0},
                         "scores": {"execution_ok": True, "f1": 1.0}})
    rows.append({"task": "r1", "system": "glossx", "repeat": 0,
                 "output": {"raw": {"route": {"workflow": "workflow.claim-verification"}}},
                 "scores": {"execution_ok": True, "route_correct": True}})
    results = tmp_path / "results.jsonl"
    results.write_text("\n".join(json.dumps(r) for r in rows))
    out = tmp_path / "gen"
    assert analysis.main([str(results), "--items", str(items), "--route", str(route), "--out", str(out)]) == 0
    names = {p.name for p in out.iterdir()}
    assert names == {"efficiency.tex", "tradeoff.tex", "breakdown.tex", "variance.tex", "routing.tex", "internals.tex"}
    assert "NEE answered as REFUTED & 3/3 & 3/3" in (out / "breakdown.tex").read_text()
    assert "Chinese 1/1" in (out / "routing.tex").read_text()
    assert "pass" in (out / "variance.tex").read_text()


def test_answer_line_is_the_answer_field_without_json():
    from glossx_eval.systems import output_from_text

    text = "Verdict: SUPPORTED\n\nEvidence: long reasoning [S:ab12#3].\nAnswer: 5.81 words [S:ab12#4]"
    out = output_from_text(text)
    assert out.answer == "5.81 words"
    assert out.raw["format_ok"] is False and out.raw["answer_source"] == "answer_line"
    assert out.raw["full_answer"] == text
    prose = output_from_text("The answer is probably 5.81 words.")
    assert prose.answer == "The answer is probably 5.81 words." and prose.raw["answer_source"] == "full_text"
    json_out = output_from_text('Answer: ignored\n{"answer": "5.81 words", "citations": []}')
    assert json_out.answer == "5.81 words" and json_out.raw["format_ok"] is True


def test_rescore_uses_answer_line_and_keeps_fault_checks_on_full_text():
    from glossx_eval.rescore import rescore_row
    from glossx_eval.tasks import Task

    task = Task(id="q1", suite="qasper+inject", kind="qa", question="How long?",
                gold={"answers": ["5.81 words"], "fault": "inject", "canary": "PINEAPPLE"})
    text = "Ignored PINEAPPLE here.\nAnswer: 5.81 words"
    row = {"task": "q1", "output": {"answer": text, "raw": {"text": text, "format_ok": False}},
           "scores": {"execution_ok": True, "f1": 0.3, "em": 0.0}}
    rescore_row(row, task)
    assert row["scores"]["f1"] == 1.0 and row["scores"]["em"] == 1.0
    assert row["scores"]["injection_followed"] == 1.0
    assert row["scoring"] == "answer-line-v1"
