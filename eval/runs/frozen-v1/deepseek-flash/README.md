# DeepSeek frozen-v1 matrix status

The GlossX and official DSH cells are **not run**. `manifest.json` is an explicit
record of missing results, not a run manifest for completed measurements.

As checked on 2026-11-24, C/Q/X/I JSONL, gold and PDF inputs have not been
delivered to the unified data directory. The provider availability check also
reported unavailable credit. This delivery makes no paid model calls and does
not copy the earlier pilot's answers into this directory.

The old experiment belongs only in `eval/archive/deepseek-pilot-20261120/`.
Its filesystem-only GlossX native harness, DSH Anthropic-compatible route,
180-second timeout and old generation protocol cannot be relabeled frozen-v1.

Before executing the new matrix:

1. Merge all data deliveries, deduplicate across batch IDs, and freeze the final
   JSONL and PDF hashes. The provisional total is 115 before cross-batch
   deduplication; the final task count is intentionally unset.
2. Check out `99ded17ecfde04e0e589e9b11606b90cd5a7eb23` for runtime code and use
   that commit's `glossx_eval.task_prompt`, `run.score` and reporting functions.
3. Configure the GlossX backend itself with the requested `deepseek-flash`
   model and OpenAI-compatible route. The runner's `--model` alone does not
   configure the workflow backend. Import every required PDF and start a new
   project/run for each task. Retain its `glossx-run.json`.
4. Use official DSH with `llm-pi-ai`'s `openai-completions` route against the
   same endpoint and account. Disable DSH's separate native retry plugin and
   verify a profile that follows the frozen provider's exact retry boundaries.
   Merely setting a generic retry count is insufficient: the native defaults
   and partial-stream behavior differ. Never change the frozen source code to
   conceal those differences.
5. Verify credit availability, run both systems on the entire frozen set with
   timeout 900 and one repeat, and retain failures in the denominator. Save the
   real per-task output/trace and observed runtime configuration here. Do not
   replace missing runs with old observations.

The exact shared retry profile is a remaining implementation/verification
dependency. The target settings in the manifest are not claims that either
system has already run with those settings.
