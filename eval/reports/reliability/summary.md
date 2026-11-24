| scenario | injected failure | detection | recovery / safe stop | stop reason | result |
| --- | --- | --- | --- | --- | --- |
| hallucinated-claim | writer cites a span that does not support its sentence | verifier labels the claim unsupported | repair rewrites the answer without it; claim listed as rejected | goal_met | pass |
| verifier-provider-down | model call fails (HTTP 503) during verification | exception caught in verify() | answer kept, every claim marked 'partial: verification unavailable' | goal_met | pass |
| router-provider-down | model call times out while routing | exception caught in route() | falls back to the generic loop and says why | goal_met | pass |
| tool-timeout | a planned tool times out | step marked failed and observed | other steps continue; answer built from the evidence that was found | goal_met | pass |
| approval-denied | plan needs code execution and the user denies it | permission gate | handler never runs; run stops with stop_reason=approval_needed | approval_needed | pass |
| budget-exhausted | reflection keeps asking for more rounds | budget meter (max_steps=2) | run stops with stop_reason=budget and returns what it has | budget | pass |
| no-progress-loop | Reflexion rounds stop improving coverage | coverage compared across rounds | stops with stop_reason=no_progress before max_rounds | no_progress | pass |
| corrupt-pdf-upload | user uploads an unreadable PDF | PDF parse fails at import | HTTP 400 with a message; no half-imported paper | — | pass |
