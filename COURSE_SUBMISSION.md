# COMP7608B final project — Group 35

**GlossX: An Open, Plugin-Native Agent Harness for Research and Learning**

Members: Cai Jiechao (contact, 3036791526), Cai Zhuorui (3036791954), Sun Zhiwei (3036791150),
Zhang Guanyi (3036793811). The University of Hong Kong.

This file is the course-specific README. The general product README is [`README.md`](README.md).

| Item | Where |
| --- | --- |
| Final report (PDF) | `submission/GlossX_Final_Report.pdf` (source: `report/latex/`) |
| AI-use declaration and prompts | [`submission/AI_USE.md`](submission/AI_USE.md) |
| Entry point | `npm start` (desktop/web app) — backend `backend/app/main.py` (FastAPI) |
| Sample inputs | [`examples/`](examples/) — ordinary task, changed request, two failure cases |
| Evaluation scripts | [`eval/`](eval/README.md) |
| Evaluation results and traces | `eval/reports/` |
| Submitted version | the git commit printed in `submission/VERSION.txt` |

## 1. Requirements

| Need | Version / note |
| --- | --- |
| OS | Windows 10/11, macOS or Linux; no GPU |
| Python | 3.11+ (tested 3.11 and 3.13) — packages pinned in `backend/requirements.txt` (FastAPI 0.115.6, PyMuPDF 1.25.5, pydantic 2.10.5, uvicorn 0.34.0, httpx 0.28.1) |
| Node.js | 20.19+ (tested 22) — frontend React 18 + Vite 8, desktop Electron 33.2.1 |
| A language model (one of) | **Codex CLI** logged in with a ChatGPT plan, **Claude Code CLI** logged in with a Claude plan, an **Anthropic API key**, or any **OpenAI-compatible endpoint** (e.g. HKU GenAI API, DeepSeek, local vLLM). Paid access is needed for all except a self-hosted model. |
| Network | Only for the model provider and optional scholar search (Semantic Scholar / arXiv / Crossref). Papers stay local. |

## 2. Set up and run

```bash
git clone https://github.com/computersniper/glossX.git && cd glossX
git checkout glossX-dev          # or the commit in submission/VERSION.txt
npm run setup                    # creates backend/.venv, installs Python + frontend deps, builds the UI
npm start                        # opens http://localhost:8010
```

Windows without npm scripts: `.\scripts\setup.ps1` then `.\scripts\run.ps1`. A portable `GlossX.exe` is
produced by the *Preview build* GitHub Action.

**Model settings.** In the app: Settings → Models. Pick the provider, model and reasoning effort. The
evaluation used Codex CLI with `gpt-6.2-sol` (medium) and `gpt-6.1-sol` (low), and an OpenAI-compatible
endpoint with `deepseek-flash`.

**Credentials.** None are in the repository or the submission. CLI providers use the CLI's own login
(`codex login`, `claude login`). API keys are entered in Settings and stored in the local data directory
(`%APPDATA%\GlossX` on Windows, `~/Library/Application Support/GlossX` on macOS, `~/.local/share/GlossX`
on Linux; override with `GLOSS_DATA_DIR`). The Settings API never returns a key in full.

## 3. Try the agent (sample inputs)

With GlossX running and a provider configured:

```bash
python examples/make_papers.py          # (re)builds the sample PDFs; already committed
python examples/run_examples.py         # runs all four cases, saves traces to examples/traces/
```

| Case | Request | What to look for |
| --- | --- | --- |
| `ordinary` | Compare Transformer and ConvS2S BLEU and training hardware (2 PDFs) | routed to cross-paper QA; every sentence cited |
| `changed-request` | Follow-up in the same project: "don't compare, just check this claim … more than 5 BLEU" | routed to claim verification; `Verdict: REFUTED` (gap is 3.24) |
| `failure-injection` | PDF with a hidden "reply PINEAPPLE" instruction | answers 28.4 BLEU; ignores the instruction |
| `failure-corrupt-pdf` | Unreadable PDF | upload refused with HTTP 400 and a message; no run on bad data |

The same requests can be typed into the app (agent panel on the right) after importing the PDFs from
`examples/papers/`.

## 4. Tests and evaluation

```bash
backend/.venv/bin/python -m pip install -r tests/requirements.txt
backend/.venv/bin/python -m pytest -q             # ~370 offline tests, no model calls
cd eval
python -m glossx_eval.reliability --out reports/reliability   # 8 failure scenarios (scripted model)
python -m glossx_eval.extensibility                           # lines per workflow from git history
python -m glossx_eval.run data/route100.jsonl --systems glossx --repeats 1            # dry run: prints the plan
python -m glossx_eval.run TASKS.jsonl --systems glossx,codex --execute ...            # real run, see eval/README.md
```

Evaluation runs are **dry by default** and only call models with `--execute`. Full commands, data
preparation and the LLM-judge / human-audit procedure are in [`eval/README.md`](eval/README.md).

**Results in the report** come from: `eval/reports/glossx-vs-codex-55.md` (PR #12), the 50-task
regression in PR #11, the DeepSeek pilot in `docs/deepseek-evaluation-followup.md` (PR #10), and
`eval/reports/reliability/` (this repository).

## 5. Mocked or unavailable parts (disclosure)

- `eval/glossx_eval/reliability.py` drives the real agent with a **scripted model** to make failures reproducible.
- Offline tests replace the model provider with fakes; they test control flow, not answer quality.
- Not implemented: Jev decider, self-evolving skills, A2A gateway, Research Radar (proposal stretch items).
- The reproduction workflow needs a local Codex or Claude Code CLI and asks for approval before running code.
- GoodNotes import is based on the file structure without an official specification.
