# PR #11 Development Diagnostics Archive (`gpt-6.1-sol`, `831b48f` vs `7fa8002`)

> **Comparability status**: `not_frozen_comparable`. These runs are **development-stage before/after diagnostics** from PR #11 on `gpt-6.1-sol` (`effort=low`). They are archived for auditability and do **not** enter the unified `frozen-v1` comparison table in `eval/UNIFIED_PROTOCOL.md`.

## Directory Layout

- `before-831b48f/` — Pre-fix baseline (`831b48f15615ad3282bab428e87dde1efb84e2c2`) on the 50-task corpus:
  - `formal-glossx.jsonl`: 50 raw GlossX runs (`qasper-14` failed with HTTP 502 / empty answer)
  - `scored-glossx.jsonl`: 50 scored GlossX rows from frozen `score_results.py`
  - `semantic_audit-glossx.jsonl`: 49 blind semantic audit records (SHA-256 bound; `qasper-14` had 0 citations)
  - `summary.json`: baseline summary statistics
- `after-7fa8002/` — Post-fix candidate (`7fa800237eb477b6c61dc88e19422e7da8fecd35`) on the full 50-task corpus:
  - `full50-v2-glossx.jsonl`: 50 raw GlossX runs (0 errors)
  - `scored.jsonl`: 50 scored rows from frozen `score_results.py`
  - `semantic_audit.jsonl`: 50 blind semantic audit records (SHA-256 bound)
  - `summary.json`: post-fix summary statistics
- `after-7fa8002-cross10-repro/` — Independent 10-task `cross-paper-qa` (`X10`) reproducibility run on `7fa8002` (also `97.50%` mean score)
- `manifest.json` — Commit hashes, runtime config, headline metrics, and per-file SHA-256 checksums

## Summary (Development Diagnostics Only)

| Metric | Before (`831b48f`) | After (`7fa8002`) |
| --- | ---: | ---: |
| Completed nonempty runs | 49/50 | 50/50 |
| `cross-paper-qa` (`X10`, N=10) | 59.00% | 97.50% |
| `SciFact` macro-F1 (N=20) | 84.24% | 84.24% |
| `QASPER` token F1 (N=20) | 12.42% | 12.98% |
| Citation located / correct page | 233/233 (100.0%) | 288/288 (100.0%) |
| Citation blind-audit `SUPPORTS` (pooled) | 152/233 (65.24%) | 288/288 (100.00%) |
| Mean latency (completed nonempty) | 86.13s | 90.63s |
