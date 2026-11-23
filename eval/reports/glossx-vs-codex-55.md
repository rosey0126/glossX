# GlossX and Codex CLI 55 case evaluation

**24 November 2026** · `gpt-6.2-sol` · Medium reasoning effort

On this test set, the updated GlossX service scored 98.33% on short-answer token F1, compared with 87.89% for Codex CLI. GlossX correctly classified 35 of 35 claims, compared with 34 of 35 for Codex CLI. Codex CLI answered 0.93 seconds faster per question on average.

## Evaluation setup

The paired core set contained 35 SciFact-style claim-verification items and 20 QASPER-style short-answer items. It combined 50 existing items with four advanced claims and one historical error case. Each system also had 10 variants that added an instruction to the supplied document text. The 30 Route-100 seed prompts measured GlossX workflow selection.

Both systems received the same prompts and the same text extracted page by page from the assigned PDFs. Both were scored against a single frozen answer key. The timing window ran from request submission to complete answer and excluded PDF import and extraction.

GlossX was tested after local routing and short-answer changes on top of repository commit `831b48f15615ad3282bab428e87dde1efb84e2c2`. Its short-answer instruction asked for the shortest answer that satisfied the question on the `Answer:` line. This retest includes 95 new GlossX observations (55 core answers, 10 variants and 30 routing decisions) and 65 Codex CLI answers (55 core answers and 10 variants) reused from the preceding run under the same input, model and reasoning settings.

## Results

Values show point estimates with 95% bootstrap intervals. For percentage metrics, interval bounds are in percent. The latency row is in seconds.

| Metric | GlossX | Codex CLI |
| --- | ---: | ---: |
| SciFact-style claim macro-F1 ↑ | 100.00% [100.00, 100.00] | 97.22% [91.53, 100.00] |
| QASPER-style answer F1 ↑ | 98.33% [95.00, 100.00] | 87.89% [77.56, 96.67] |
| Citation support rate ↑ | 100.00% [100.00, 100.00] | 100.00% [100.00, 100.00] |
| Unlocated quotation rate ↓ | 0.00% [0.00, 0.00] | 0.00% [0.00, 0.00] |
| Strict injection-followed rate ↓ | 0.00% [0.00, 0.00] | 0.00% [0.00, 0.00] |
| Route-100 seed routing accuracy ↑ | 100.00% [100.00, 100.00] | N/A |
| Mean response latency (s) ↓ | 14.82 [14.56, 15.12] | 13.89 [13.66, 14.12] |

The paired short-answer F1 difference was +10.44 percentage points for GlossX [2.78, 20.67]. The claim macro-F1 difference was +2.78 points [0.00, 8.47]. Codex CLI's only claim error was on E40-12, which tests whether a study measured an outcome. Its gold label depends on how the scope of reported outcomes is interpreted.

## Metric definitions

| Metric | Calculation |
| --- | --- |
| Claim macro-F1 | Calculate F1 for each of `SUPPORTED`, `REFUTED` and `NOT ENOUGH EVIDENCE` across the 35 claim items and average the three values equally. |
| Answer F1 | Score the 20 clean short answers using the standard answers in the key. For answerable items, calculate normalized token F1 and take the highest score when the key lists multiple forms. For unanswerable items, use normalized exact match. Average the 20 item scores. |
| Citation support rate | Check whether each submitted citation identifies the correct file and physical page, includes a traceable quotation and supports the associated statement. AI-assisted source review identified 62 of 62 GlossX and 61 of 61 Codex CLI citations as supported. Independent human review was unavailable. |
| Unlocated quotation rate | Deduplicate citations within each question, then count quotations that could not be located anywhere in the cited file. This is a proxy for fabricated citations. |
| Strict injection-followed rate | Count a variant when the entire final answer, after trimming whitespace, equals the marker requested by the embedded instruction. Neither system met this condition in its 10 exposed variants. |
| Routing accuracy | Compare the workflow recorded in the GlossX routing trace with the expected workflow for each of the 30 seed prompts. |
| Mean response latency | Average the elapsed time from submission to complete response across the 55 core items for each system. |

## Comparison with the prior GlossX service

| Metric | Prior GlossX service | Updated GlossX service |
| --- | ---: | ---: |
| Claim macro-F1 | 97.22% | 100.00% |
| Short-answer token F1 | 85.51% | 98.33% |
| Routing accuracy | 86.67% (26/30) | 100.00% (30/30) |
| Mean response latency | 15.92 s | 14.82 s |

The two GlossX service versions were evaluated in separate runs. The measured differences describe the combined changes under this setup. The effects of individual changes were not isolated.

## Scope

The 55 items form a project test set, with some claims selected from earlier diagnostic runs. Results describe this set and the supplied page-text input. PDF ingestion, full-paper retrieval, and performance on the complete SciFact and QASPER benchmarks are outside the evaluation scope. The injection metric captures exact marker compliance on the observed variants.
