# Frozen DeepSeek results

GlossX used the v1.1 merge `7a9a246225ca0907282de5c3755f1179292af8a9`. Its backend started with fresh data, home and cache directories. The runner set and checked English, the OpenAI-compatible provider, the credential and the endpoint before inference. DSH 0.2.2-rc.5 uses its original #17 observations. The exact dataset bytes, 115 PDF hashes and seed-0 repeat IDs were checked before the v1.1 run.

| Primary measure | GlossX v1.1 | DSH on the same 114 prompts |
| --- | ---: | ---: |
| Original prompts completed | 114/114 attempted | 114/114 attempted |
| Claim macro-F1 (35) | 0.915 | 0.917 |
| ShortQA mean token F1 (20) | 0.861 | 0.891 |
| Research mean task score (39) | 0.618 | 0.674 |
| Injection canaries followed (10) | 0/10 | 0/10 |
| Located quotations | 489/503 | 329/329 |
| Mean latency (seconds) | 68.2 | 19.7 |

For `scifact-507`, GlossX ran a separate study-population classification. The frozen prompt has no v1.1 result. The classification has its own prompt, output and trace, and is excluded from the table, paired intervals and original-prompt JSONL. DSH completed the full D40 and 115/115 original primary prompts. The report gives DSH's full column and identifies its matched D39 score in the text. CrossPaper rubric scores and citation-support judgments belong to the shared judging step.

Each of the 20 frozen repeat IDs has all three original observations for both systems. Among the 17 items with native quality scores, GlossX and DSH reached the 0.5 threshold in all three runs on 13 and 13 items. The manifest includes all three means, within-item variability, and paired bootstrap intervals for the primary Q and D scores.

- [GlossX v1.1 original prompts](results-glossx.jsonl) (114 base + 40 repeats), [new traces](traces/glossx-v1.1/) and [separate classification](variants/scifact-507-scope.jsonl)
- [Frozen DSH rows](results-dsh.jsonl) (115 base + 40 repeats) and [original traces](traces/dsh/)
- [Manifest](manifest.json), [repeat IDs](variance-ids.json) and [archived v1.0 raw matrix](../../archive-v1.0/deepseek-flash/results-deepseek-flash-v1.0.jsonl)

## Execution and scoring

Use the runtime commit above and the frozen data at `3612244`. Import the selected task PDFs with `python -m glossx_eval.prepare import` into a fresh backend. Run each original task with `python -m glossx_eval.run ONE_TASK.jsonl --execute --systems glossx --paper-ids PAPER_IDS.json --glossx-url BACKEND_URL --model deepseek-flash --repeats 1 --timeout 900 --out OUTPUT_DIR`. Each invocation has a fresh task workspace. Assign repeat 0 to the primary sweep, then 1 and 2 to the same [20 IDs](variance-ids.json). The separate classification used the exact goal recorded in the manifest and its own one-paper backend.

Both systems used the same DeepSeek chat completions endpoint and account. GlossX retried HTTP 429, 500, 502, 503 and 504 up to twice, plus selected connection-establishment errors. DSH disabled its built-in retries and used the [request wrapper](driver/retry.mjs) for those HTTP statuses. The manifest records the connection-error difference, DSH entry point and original execution dates. Re-score original-prompt rows with `glossx_eval.rescore` and `answer-line-v1`. Automated citation location checks whether a quotation can be found in the file. Citation support is a separate judge decision.
