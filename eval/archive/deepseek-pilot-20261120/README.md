# Historical DeepSeek pilot — 2026-11-20

**not_frozen_comparable: true. This is an exploratory historical pilot archive, not a frozen benchmark result or evidence that GlossX outperforms DSH.** It must remain separate from any subsequently frozen task suite and its results.

`pilot-artifacts.tar.gz` contains sanitized task inputs/references, raw answer records, exact submitted prompts, responses, DSH native event projections/diagnostics, postprocessed scores, and export-time code snapshots. `manifest.json` maps logical source paths to archived paths and records both source-content SHA256 and sanitized-content SHA256. No absolute source path is retained. All artifacts were prepared offline, without new model inference.

## Counts and selection

- Two main batches contain **180 raw rows**: 40 controlled task IDs + SciFact 30 + QASPER 20, each attempted once per system.
- A separate development preflight contains **4 rows** (2 task IDs × 2 systems). It is excluded from the 180 final scored rows.
- A separate infrastructure-only replacement contains **2 rows**. The repeated paper reference in SciFact-1245 caused staging to fail before either model was invoked. Both original staging failures remain in the main raw batch; the two later attempts replace them only in the selected final results. This is not selection among genuine repeated model answers.
- All four run directories therefore contain **186 raw rows**; the selected, uniformly rescored result contains **180 rows / 90 paired task IDs**. The selection history is in `final_results/infrastructure_history.json`.
- `final_results/human_audit_blind.jsonl` is an uncompleted review template; its key maps audit IDs to task/system IDs only. No human quality rating or agreement statistic is claimed.

## Limits of comparison

Both systems requested `deepseek-flash` with thinking disabled, fresh local task workspaces, the same user prompt per paired task, and no external retrieval or shell. The actual server-resolved model revision and provider-default temperature were not measured. GlossX used its native read-only harness entrypoint at the recorded Git revision; its full library workflow/span validation was not enabled. DSH used official `@deepseek-ai/dsh@0.2.2-rc.5`, native headless, with `read`/`glob`/`grep` and a documented path-boundary guard. Its route was `https://api.deepseek.com/anthropic`; GlossX used the OpenAI-compatible chat-completions route. These are different system configurations and API routes. Tool-step semantics, token consumption, cold-start overhead, and native retry policies were not strictly identical.

The shared-account concurrent batches encountered **HTTP 429 rate limits and HTTP 402 quota/payment failures**. These are service failures, not evidence of scientific reasoning errors. Failure rows remain visible; successful-pair subsets have selection bias. Token usage is incomplete in some successful DSH runs and is explicitly `null`, never zero; cached and uncached input are separate buckets. No bill or cost total can be reconstructed reliably from this archive alone. The November 24 account state is not inferred from the November 20 records.

The controlled set comprises ten short synthetic task families with five parameterized variants each, not fifty independent research problems. Only forty held-out variants were used in the main batch; family overlap with development limits generalization. Public tasks used frozen released Markdown/abstract text, not a complete PDF/figure grounding protocol. QASPER token-F1 is sensitive to verbose explanations in the answer field. Strict JSON formatting, numerical tolerance, scientific correctness, quote location, and semantic citation support must be distinguished.

Scoring version 1.2 corrected the SciFact verdict-extraction problem uniformly for both systems; original answers and earlier scores remain retained. The main numerical tolerance remained fixed; the historical report separately describes a rounding sensitivity calculation. Read `provenance/RESULTS_ZH.original.md` and `final_results/METRICS.md` for the original interpretation. Do not silently merge historical scores with a new task suite.

## Provenance and privacy

`code_snapshot/` contains the **files present at archive export time**, including later postprocessing and runner fixes. Each file has an observed modification timestamp and source-content hash. These snapshots are not represented as a complete pre-run frozen source release. Native DSH version, GlossX commit, per-run patch hashes, original task hashes, and available protocol/scoring versions are retained in the historical records. Exported JSON/JSONL may be reserialized; “raw” means the retained original record content after privacy redaction, not byte-identical local files.

Local usernames, user-home/drive paths, email addresses, known environment API-key literals, API-key-shaped strings, and credential values are redacted. Paths under the historical evaluation root become relative references. API endpoints, public repository URLs, task identifiers, and scientific text are preserved except where a privacy pattern matches. Manifest source hashes refer to original local file contents without revealing their paths; archived hashes validate the sanitized content.

Excluded: local Python/Node runtimes, `node_modules`, venvs, cache files, workspaces duplicating input files, DSH home/session internals, GlossX internal state, original downloaded releases, and original arXiv PDFs. Input/reference text, source URLs, release hashes, and download/preparation snapshots are retained. The old preparation script's full offline raw-release integrity check requires reobtaining those excluded releases. See `NOTICE.md` for data attribution and licensing.

## Inspect without inference

```sh
tar -tzf pilot-artifacts.tar.gz
tar -xzf pilot-artifacts.tar.gz
```

The archive is 1,395,010 bytes. Validate the tarball SHA256 and every extracted member against `manifest.json` before use. Do not execute the code snapshots as if they were a newly frozen experiment.

## Readable historical service diagnostics

`error-summary.json` is available without extraction. It is derived from the retained tarball and does not add inference or a new system comparison. Completion means the agent returned normally; it does not mean the research answer is correct. Counts below use the selected **180 final attempts**, 90 per system.

| System | Final attempts | Agent completed | Completion rate | HTTP 402 | HTTP 429 | Other failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dsh | 90 | 85 | 94.44% | 5 | 0 | 0 |
| glossx | 90 | 69 | 76.67% | 7 | 14 | 0 |

Every failed HTTP task ID, system/status/error-type/terminal-HTTP cross-count, and status evidence source is listed in `error-summary.json`. These are terminal attempt counts, not counts of HTTP requests or hidden retries. DSH successes have HTTP status `null` because the native output does not expose 200; no missing value is imputed.

The original main batches contain 180 attempts, including **two `scifact-1245` staging errors before model invocation** (one per system). Their later two replacements are separate: GlossX returned HTTP 429; DSH completed. The original two errors remain archived, while selected final results use only these replacements. The four development preflight attempts are excluded from both main/final denominators. `error-summary.json` reports each group independently.

Runtime provenance: DSH **0.2.2-rc.5**, official `headless`, `https://api.deepseek.com/anthropic`; GlossX `app.harness.engine.run_turn`, `https://api.deepseek.com/chat/completions`. Both historical plans used a **180-second wall-clock limit, max_steps=12, max output 4096 and thinking disabled**; step semantics and retries differ. The original wrapper/native command templates, recorded GlossX commit, and missing actual model/temperature observations are in the outer manifest's `runtime_provenance`.

Outer diagnostics may be regenerated with `archive_pilot.py --refresh-outer --write` using only the existing tarball. This preserves its exact bytes and original export-time code snapshots. The outer generator version may therefore be newer than the generator snapshot inside the tar.

