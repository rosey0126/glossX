# DeepSeek frozen-v1 evaluation

GlossX and DSH each attempted all 115 frozen items on the same DeepSeek account and chat completions endpoint. The same seed-0 sample of 20 items received two additional attempts per system after the main runs. Each of the 310 result rows links to its native trace.

| System | Main executions succeeded | Additional executions succeeded | Claim macro-F1 | ShortQA mean F1 | Research mean score | Injection canaries followed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GlossX | 115/115 | 40/40 | 0.888 | 0.574 | 0.508 | 0/10 |
| DSH | 115/115 | 40/40 | 0.917 | 0.891 | 0.657 | 0/10 |

The table uses repeat 0, apart from the additional-executions column. The ten CrossPaper responses per system are available for shared rubric scoring. The manifest reports variance on all twenty items for execution and answer stability, and on the seventeen with native quality scores.

This is the second complete English run of the frozen protocol. The first encountered PDF-staging and account-credit failures. An intervening run stopped when the fresh backend's default answer language was found to be Simplified Chinese. For the final run the launcher explicitly set and verified English in Settings before inference, used a fresh backend and allocated new workspaces to both agents. The manifest gives the earlier full run's checksum and the number of intervening diagnostics. All reported figures come from the final English run.

[Raw JSONL](results-deepseek-flash.jsonl) · [Manifest](manifest.json) · [Variance sample](variance-ids.json) · [Traces](traces/)

## Reproduce

Use a clean runtime checkout at `99ded17` and the exact dataset bytes from `3612244`. On Windows, extract the task JSONL directly from its Git blob if checkout newline conversion changes its published checksum. Put it and its `papers/` directory in a private run directory. Start the frozen backend on loopback with separate GlossX data, home and cache directories. Set `PYTHONPATH` to that checkout's `eval` directory for the following commands. Install the frozen backend requirements and official `@deepseek-ai/dsh@0.2.2-rc.5` using Node 24.9 or later.

```sh
python -m glossx_eval.prepare import --tasks PRIVATE/data/frozen-v1.jsonl --glossx-url http://127.0.0.1:18765
python driver/matrix.py --tasks PRIVATE/data/frozen-v1.jsonl --scratch PRIVATE/work --out PRIVATE/results --dsh-cli DSH_PACKAGE/lib/bin.js --output-language English
```

To execute, make the funded account's `DEEPSEEK_API_KEY` available in the worker environment and append `--execute` to the second command. Use one worker per output directory. The worker checks credit, sets the isolated backend's provider, model, endpoint and credential through Settings, and confirms every PDF maps to an imported library ID. The same credential goes to DSH. Both use the official chat completions endpoint and a 900-second task timeout. The GlossX runner receives one scheduled item at a time. The DSH CLI receives the frozen `task_prompt(task)` on stdin with a fresh session and a workspace containing the task PDFs and page-numbered text extractions. Each trace records the scheduled repeat through its directory name.

The DSH profile disables the native retry plugin. Its external request wrapper retries the same five HTTP statuses as GlossX up to twice before returning successful stream headers. GlossX also retries selected connection-establishment failures. The DSH wrapper propagates connection errors directly. A separate local fixture verified the production DSH invocation, request path, model name and a 429 → 503 → success sequence.

For concurrent reproduction, assign disjoint slices with `--main-range START STOP` and `--variance-range START STOP`. The indices are zero-based and the end index is exclusive. Give each worker its own output directory and use a shared scratch directory for exclusive attempt reservations. Keep at most four paired workers active and run each repeat after its base item has finished. `driver/collect.py --tasks PRIVATE/data/frozen-v1.jsonl WORKER_DIR ...` validates the schedule, native scores and traces. Adding `--out DEST` assembles a complete 310-row delivery in frozen order. DSH token counts come from step-end usage events, including cache reads and writes. GlossX reports its native budget estimate.

On resumption, the worker skips recorded attempts, including failures. If it finds an unfinished scratch directory without a corresponding result, check the native trace before resuming to avoid billing a duplicate. Review raw outputs and traces for personal paths and credentials before copying them from private storage. Keep local credentials, the backend database, DSH homes and staged paper copies in private storage.
