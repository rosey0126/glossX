"""Export a sanitized historical pilot, without network or model calls.

Default: inspect the explicit historical allowlist and print a size/count plan.
Use --write to create the staged archive plus readable outer diagnostics.
Use --refresh-outer --write to derive diagnostics from an existing immutable tar.
Sources are read-only. Existing nonempty output directories are never overwritten.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tarfile


VERSION = "1.1"
DEFAULT_ROOT = Path(__file__).resolve().parents[1]
RUNS = {
    "20261120-231002-f8525c": {"role": "development_preflight", "expected_rows": 4},
    "20261120-231342-2b9f66": {"role": "public_full_batch", "expected_rows": 100},
    "20261120-231342-7af40c": {"role": "controlled_full_batch", "expected_rows": 80},
    "20261120-231642-d49386": {"role": "unexecuted_staging_error_replacement", "expected_rows": 2},
}
FINAL_FILES = (
    "results.scored.jsonl", "manifest.json", "summary.json", "METRICS.md",
    "provider_failures.jsonl", "infrastructure_history.json",
    "human_audit_blind.jsonl", "human_audit_key.jsonl",
)
CODE_FILES = (
    "evaluate.py", "build_tasks.py", "prepare_public.py", "rescore_and_audit.py",
    "summarize_results.py", "test_evaluate.py", "package_bundle.py",
    "adapters/dsh_adapter.mjs", "adapters/dsh_guard.mjs", "adapters/DSH_SETUP.md",
    "adapters/glossx_adapter.py", "vendor/dsh/package.json",
    "vendor/dsh/pnpm-lock.yaml", "vendor/dsh/pnpm-workspace.yaml",
)
DRIVE = re.compile(r"(?i)(?<![a-z0-9])(?:[a-z]):[\\/]+")
HOME = re.compile(r"(?i)\b[a-z]:[\\/]+users[\\/]+[^\\/\r\n\"'<>| ]+")
EMAIL = re.compile(r"(?i)\b[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9.-]+\.[a-z]{2,}\b")
API_KEY = re.compile(r"\bsk-[a-zA-Z0-9_-]{16,}\b")
BEARER = re.compile(r"(?i)(\bbearer\s+)[a-z0-9._~+/-]{12,}=*")
KEY_NAME = re.compile(r"(?i)^(?:api[-_]?key|x-api-key|access[-_]?token|password|authorization|secret)$")
SAFE_REFERENCES = {"DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "[REDACTED]", "[REDACTED_API_KEY]"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


class Sanitizer:
    def __init__(self, root: Path):
        self.root = root
        self.counts: Counter[str] = Counter()
        self.secret = os.environ.get("DEEPSEEK_API_KEY", "")
        parts = list(root.parts)
        self.usernames = set()
        for index, part in enumerate(parts[:-1]):
            if part.casefold() == "users":
                self.usernames.add(parts[index + 1])
        # Handle normal paths and paths embedded in a second JSON-encoded string.
        self.root_forms = set()
        for text in (str(root), root.as_posix()):
            self.root_forms.add(text)
            self.root_forms.add(json.dumps(text, ensure_ascii=False)[1:-1])
            self.root_forms.add(json.dumps(text, ensure_ascii=True)[1:-1])
        self.root_forms = sorted(self.root_forms, key=len, reverse=True)

    def text(self, value: str) -> str:
        if self.secret:
            value, hits = re.subn(re.escape(self.secret), "[REDACTED_API_KEY]", value)
            self.counts["environment_key_literal"] += hits
        value, hits = API_KEY.subn("[REDACTED_API_KEY]", value)
        self.counts["key_pattern"] += hits
        value, hits = BEARER.subn(r"\1[REDACTED_TOKEN]", value)
        self.counts["bearer_token"] += hits
        for local_root in self.root_forms:
            value, hits = re.subn(re.escape(local_root), ".", value, flags=re.I)
            self.counts["source_root_to_relative"] += hits
        if value.startswith((".\\", "./")) and "\n" not in value:
            value = re.sub(r"\\+", "/", value)
        value, hits = HOME.subn("[LOCAL_USER_HOME]", value)
        self.counts["other_user_home"] += hits
        for username in sorted(self.usernames, key=len, reverse=True):
            value, hits = re.subn(re.escape(username), "[LOCAL_USER_NAME]", value, flags=re.I)
            self.counts["username"] += hits
        value, hits = DRIVE.subn("[LOCAL_ABSOLUTE_PATH]/", value)
        self.counts["other_drive_path"] += hits
        value, hits = EMAIL.subn("[REDACTED_EMAIL]", value)
        self.counts["email"] += hits
        return value

    def obj(self, value: object) -> object:
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                safe_key = self.text(key)
                if safe_key in result:
                    raise ValueError("Sanitization would collide object keys")
                if KEY_NAME.fullmatch(key) and isinstance(item, str) and item not in SAFE_REFERENCES:
                    result[safe_key] = "[REDACTED]"
                    self.counts["credential_value"] += 1
                else:
                    result[safe_key] = self.obj(item)
            return result
        if isinstance(value, list):
            return [self.obj(item) for item in value]
        if isinstance(value, str):
            return self.text(value)
        return value

    def file(self, source: Path, data: bytes) -> bytes:
        text = data.decode("utf-8-sig")
        if source.suffix == ".json":
            return json_bytes(self.obj(json.loads(text)))
        if source.suffix == ".jsonl":
            rows = [self.obj(json.loads(line)) for line in text.splitlines() if line.strip()]
            return ("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows)).encode("utf-8")
        return self.text(text).encode("utf-8")

    def verify(self, data: bytes, logical_name: str) -> None:
        text = data.decode("utf-8")
        for pattern, label in ((DRIVE, "drive path"), (HOME, "user home"), (EMAIL, "email"), (API_KEY, "API-key pattern"), (BEARER, "bearer token")):
            if pattern.search(text):
                raise ValueError(f"Residual {label} in {logical_name}")
        if self.secret and self.secret in text:
            raise ValueError(f"Residual environment API key in {logical_name}")
        for username in self.usernames:
            if re.search(re.escape(username), text, flags=re.I):
                raise ValueError(f"Residual local username in {logical_name}")


def select_files(root: Path) -> list[tuple[Path, str, str]]:
    chosen: dict[str, tuple[Path, str, str]] = {}

    def add(source: Path, target: str, category: str) -> None:
        source = source.resolve(strict=True)
        if not source.is_relative_to(root) or not source.is_file():
            raise ValueError("Source outside the allowed historical evaluation directory")
        if target in chosen or target.startswith("/") or ".." in Path(target).parts:
            raise ValueError("Duplicate or unsafe archive path")
        chosen[target] = (source, target, category)

    for run, info in RUNS.items():
        folder = root / "results" / run
        for filename in ("plan.json", "results.jsonl"):
            add(folder / filename, f"results/{run}/{filename}", info["role"])
        for attempt in sorted((folder / "runs").iterdir()):
            if not attempt.is_dir():
                continue
            for filename in ("request.json", "response.json"):
                source = attempt / filename
                if source.exists():
                    add(source, source.relative_to(root).as_posix(), "run_request_response")
            for filename in ("events.jsonl", "stderr.log"):
                source = attempt / "response.json.dsh" / filename
                if source.exists():
                    add(source, source.relative_to(root).as_posix(), "dsh_native_projection")
    for folder in ("data", "public_benchmarks"):
        for source in sorted((root / folder).rglob("*")):
            relative = source.relative_to(root)
            if not source.is_file() or {"raw", "original_pdfs", "__pycache__"}.intersection(relative.parts):
                continue
            if source.suffix not in {".json", ".jsonl", ".md"}:
                continue
            add(source, relative.as_posix(), "historical_task_input_or_reference")
    for filename in FINAL_FILES:
        add(root / "final_results" / filename, f"final_results/{filename}", "postprocessed_result_or_human_review_template")
    for filename in CODE_FILES:
        add(root / filename, f"code_snapshot/{filename}", "export_time_code_snapshot")
    for source, target in (("NOTICE.md", "NOTICE.md"), ("README.md", "provenance/README.original.md"), ("RESULTS_ZH.md", "provenance/RESULTS_ZH.original.md")):
        add(root / source, target, "historical_handover")
    generator = Path(__file__).resolve()
    if generator.is_relative_to(root):
        add(generator, "provenance/archive_pilot.py", "archive_generator")
    return [chosen[key] for key in sorted(chosen)]


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def historical_counts(root: Path) -> dict:
    runs = {}
    for run, info in RUNS.items():
        rows = read_jsonl(root / "results" / run / "results.jsonl")
        if len(rows) != info["expected_rows"]:
            raise ValueError(f"Unexpected historical row count: {run}")
        runs[run] = {**info, "rows": len(rows), "distinct_tasks": len({r['task'] for r in rows})}
    scored = read_jsonl(root / "final_results" / "results.scored.jsonl")
    if len(scored) != 180 or len({r["task"] for r in scored}) != 90:
        raise ValueError("Expected 180 final rows for 90 paired task IDs")
    return {"runs": runs, "raw_rows_total": sum(info["rows"] for info in runs.values()),
            "full_batch_raw_rows": 180, "development_preflight_rows": 4,
            "staging_only_replacement_rows": 2, "final_scored_rows": len(scored),
            "final_distinct_task_ids": 90, "final_scoring_versions": sorted({r.get("scoring_version", "unknown") for r in scored})}


def terminal_http_status(result: dict) -> tuple[int | None, str]:
    """Use recorded terminal status only; do not infer HTTP 200 from agent success."""
    metadata = result.get("metadata") or {}
    reason = metadata.get("terminal_reason") or {}
    terminal = reason.get("error") or {}
    status = terminal.get("status")
    if isinstance(status, int) and not isinstance(status, bool):
        return status, "metadata.terminal_reason.error.status"
    observed = metadata.get("observed_requests") or []
    for request in reversed(observed):
        status = request.get("http_status")
        if isinstance(status, int) and not isinstance(status, bool):
            return status, "metadata.observed_requests[-1].http_status"
    message = str(result.get("error", "")) + " " + str(metadata.get("error", ""))
    match = re.search(r"\b(402|429|400|401|403|404|408|413|422|500|502|503|504)\b", message)
    if match:
        return int(match.group(1)), "retained_error_message"
    return None, "not_exposed"


def diagnostic_row(row: dict) -> dict:
    result = row["result"]
    status = result.get("status", "unknown")
    http_status, basis = terminal_http_status(result)
    message = str(result.get("error", "")) + " " + str((result.get("metadata") or {}).get("error", ""))
    if status == "ok":
        error_type = "none"
    elif "ambiguous document basename" in message:
        error_type = "staging_duplicate_document_reference"
    elif http_status == 402:
        error_type = "http_402_quota_payment"
    elif http_status == 429:
        error_type = "http_429_rate_limit"
    elif http_status is not None and http_status >= 400:
        error_type = "http_other"
    elif status in {"timeout", "step_limit"}:
        error_type = status
    else:
        error_type = "other_error"
    return {"task_id": row["task"], "system": row["system"], "suite": row.get("suite"),
            "repeat": row.get("repeat"), "status": status, "error_type": error_type,
            "http_status": http_status, "http_status_basis": basis,
            "model_invocation_not_started": error_type == "staging_duplicate_document_reference"}


def diagnostics(rows: list[dict]) -> dict:
    details = [diagnostic_row(row) for row in rows]
    systems = {}
    for system in sorted({row["system"] for row in details}):
        selected = [row for row in details if row["system"] == system]
        ok = sum(row["status"] == "ok" for row in selected)
        systems[system] = {"attempts": len(selected), "agent_completed": ok,
                           "agent_completion_rate": ok / len(selected) if selected else None,
                           "status_counts": dict(sorted(Counter(row["status"] for row in selected).items())),
                           "error_type_counts": dict(sorted(Counter(row["error_type"] for row in selected).items())),
                           "terminal_http_status_counts": dict(sorted(Counter(str(row["http_status"]) if row["http_status"] is not None else "null" for row in selected).items()))}
    cross = Counter((row["system"], row["status"], row["error_type"], row["http_status"]) for row in details)
    cross_rows = [{"system": key[0], "status": key[1], "error_type": key[2], "http_status": key[3], "count": count}
                  for key, count in sorted(cross.items(), key=lambda item: tuple(str(value) for value in item[0]))]
    failures = [row for row in details if row["status"] != "ok"]
    http_groups = {}
    for row in failures:
        if row["http_status"] is not None and row["http_status"] >= 400:
            http_groups.setdefault((row["system"], row["http_status"], row["error_type"]), []).append(row["task_id"])
    return {"attempts": len(rows), "by_system": systems, "status_error_http_counts": cross_rows,
            "http_failure_task_ids": [{"system": system, "http_status": status, "error_type": error,
                                       "count": len(ids), "task_ids": sorted(ids)}
                                      for (system, status, error), ids in sorted(http_groups.items())],
            "failed_attempts": failures}


def error_summary(payloads: dict[str, bytes], artifact_sha256: str) -> dict:
    def rows(name: str) -> list[dict]:
        return [json.loads(line) for line in payloads[name].decode("utf-8").splitlines() if line.strip()]

    final = rows("final_results/results.scored.jsonl")
    raw = {name: rows(f"results/{name}/results.jsonl") for name in RUNS}
    main_rows = [row for name, records in raw.items() if RUNS[name]["role"] in {"public_full_batch", "controlled_full_batch"} for row in records]
    stage_rows = [row for row in main_rows if diagnostic_row(row)["error_type"] == "staging_duplicate_document_reference"]
    replacement = raw["20261120-231642-d49386"]
    preflight = raw["20261120-231002-f8525c"]
    if len(final) != 180 or len(main_rows) != 180 or len(stage_rows) != 2 or len(replacement) != 2 or len(preflight) != 4:
        raise ValueError("Unexpected historical diagnostic denominators")
    final_selection = {(row["task"], row["system"], row["repeat"]): row for row in final}
    for row in replacement:
        key = (row["task"], row["system"], row["repeat"])
        if final_selection[key]["result"] != row["result"]:
            raise ValueError("Replacement record does not match selected final result")
    metadata_by_system = {system: [row["result"].get("metadata") or {} for row in final if row["system"] == system] for system in ("glossx", "dsh")}
    plans = [json.loads(payloads[f"results/{run}/plan.json"]) for run in RUNS]
    provenance = {
        "scope": "Historical configured systems only; templates are provenance, not instructions for a new experiment.",
        "requested_models": sorted({plan["model"] for plan in plans}),
        "timeout_seconds_from_plans": sorted({plan["timeout_seconds"] for plan in plans}),
        "max_steps_from_plans": sorted({plan["max_steps"] for plan in plans}),
        "actual_server_model_revision": None, "provider_default_temperature": None,
        "dsh": {"versions_observed": sorted({meta["version"] for meta in metadata_by_system["dsh"] if "version" in meta}),
                "adapter_command_template": "node adapters/dsh_adapter.mjs --request <request.json> --response <response.json>",
                "native_command_template": "node <dsh-install>/lib/bin.js headless --patch <run-state>/evaluation.patch.yml --json --permission-mode read-only --approval-policy never -",
                "prompt_transport": "stdin", "route": "https://api.deepseek.com/anthropic",
                "model_provider": "deepseek-official", "thinking": "disabled", "max_output_tokens": 4096,
                "timeout_seconds": 180, "max_steps": 12,
                "step_limit_semantics": "External headless step_start supervisor; a boundary request may already be in flight.",
                "tools_allowed": ["read", "glob", "grep"], "session_log_upload": False, "telemetry_upload": False,
                "actual_http_request_retry_counts": None},
        "glossx": {"repository_commits_observed": sorted({meta["repository_commit"] for meta in metadata_by_system["glossx"] if "repository_commit" in meta}),
                   "adapter_command_template": "python adapters/glossx_adapter.py --request <request.json> --response <response.json>",
                   "entrypoint": "app.harness.engine.run_turn", "route": "https://api.deepseek.com/chat/completions",
                   "thinking": "disabled", "max_output_tokens": 4096, "timeout_seconds": 180, "max_tool_rounds": 12,
                   "profile": "workspace-read-only", "library_workflow_enabled": False,
                   "tools_allowed": ["fs_list", "fs_read", "fs_glob", "fs_grep", "result_read"]},
    }
    return {"schema_version": "1.0", "not_frozen_comparable": True, "new_model_inference": False,
            "derived_from_artifact_sha256": artifact_sha256,
            "counting_unit": "One retained terminal agent attempt per task/system/repeat, not individual HTTP requests or hidden retries.",
            "agent_completion_is_not_scientific_correctness": True,
            "success_http_status_policy": "Only recorded HTTP statuses are counted; a successful DSH run has null because the native projection does not expose HTTP 200.",
            "interpretation": "Historical service diagnostics only. Concurrent shared-account rate limits, quota/payment failures and differing retry policies prevent a new capability or reliability ranking.",
            "selected_final_180": diagnostics(final),
            "main_batch_raw_180": diagnostics(main_rows),
            "original_staging_failures_2": {**diagnostics(stage_rows), "attempts_detail": [diagnostic_row(row) for row in stage_rows], "included_in_main_raw_180": True, "included_in_selected_final_180": False},
            "replacement_attempts_2": {**diagnostics(replacement), "attempts_detail": [diagnostic_row(row) for row in replacement], "included_in_selected_final_180": True, "new_genuine_answer_selection": False},
            "development_preflight_4": {**diagnostics(preflight), "included_in_selected_final_180": False},
            "runtime_provenance": provenance}


def diagnostic_readme(summary: dict) -> str:
    lines = ["## Readable historical service diagnostics", "", "`error-summary.json` is available without extraction. It is derived from the retained tarball and does not add inference or a new system comparison. Completion means the agent returned normally; it does not mean the research answer is correct. Counts below use the selected **180 final attempts**, 90 per system.", "", "| System | Final attempts | Agent completed | Completion rate | HTTP 402 | HTTP 429 | Other failures |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for system, values in sorted(summary["selected_final_180"]["by_system"].items()):
        errors = values["error_type_counts"]
        other = sum(count for error, count in errors.items() if error not in {"none", "http_402_quota_payment", "http_429_rate_limit"})
        lines.append(f"| {system} | {values['attempts']} | {values['agent_completed']} | {values['agent_completion_rate']:.2%} | {errors.get('http_402_quota_payment', 0)} | {errors.get('http_429_rate_limit', 0)} | {other} |")
    lines += ["", "Every failed HTTP task ID, system/status/error-type/terminal-HTTP cross-count, and status evidence source is listed in `error-summary.json`. These are terminal attempt counts, not counts of HTTP requests or hidden retries. DSH successes have HTTP status `null` because the native output does not expose 200; no missing value is imputed.", "", "The original main batches contain 180 attempts, including **two `scifact-1245` staging errors before model invocation** (one per system). Their later two replacements are separate: GlossX returned HTTP 429; DSH completed. The original two errors remain archived, while selected final results use only these replacements. The four development preflight attempts are excluded from both main/final denominators. `error-summary.json` reports each group independently.", "", "Runtime provenance: DSH **0.2.2-rc.5**, official `headless`, `https://api.deepseek.com/anthropic`; GlossX `app.harness.engine.run_turn`, `https://api.deepseek.com/chat/completions`. Both historical plans used a **180-second wall-clock limit, max_steps=12, max output 4096 and thinking disabled**; step semantics and retries differ. The original wrapper/native command templates, recorded GlossX commit, and missing actual model/temperature observations are in the outer manifest's `runtime_provenance`.", "", "Outer diagnostics may be regenerated with `archive_pilot.py --refresh-outer --write` using only the existing tarball. This preserves its exact bytes and original export-time code snapshots. The outer generator version may therefore be newer than the generator snapshot inside the tar.", ""]
    return "\n".join(lines)


def readme(counts: dict, artifact_bytes: int, summary: dict) -> bytes:
    return f"""# Historical DeepSeek pilot — 2026-11-20

**not_frozen_comparable: true. This is an exploratory historical pilot archive, not a frozen benchmark result or evidence that GlossX outperforms DSH.** It must remain separate from any subsequently frozen task suite and its results.

`pilot-artifacts.tar.gz` contains sanitized task inputs/references, raw answer records, exact submitted prompts, responses, DSH native event projections/diagnostics, postprocessed scores, and export-time code snapshots. `manifest.json` maps logical source paths to archived paths and records both source-content SHA256 and sanitized-content SHA256. No absolute source path is retained. All artifacts were prepared offline, without new model inference.

## Counts and selection

- Two main batches contain **180 raw rows**: 40 controlled task IDs + SciFact 30 + QASPER 20, each attempted once per system.
- A separate development preflight contains **4 rows** (2 task IDs × 2 systems). It is excluded from the 180 final scored rows.
- A separate infrastructure-only replacement contains **2 rows**. The repeated paper reference in SciFact-1245 caused staging to fail before either model was invoked. Both original staging failures remain in the main raw batch; the two later attempts replace them only in the selected final results. This is not selection among genuine repeated model answers.
- All four run directories therefore contain **{counts['raw_rows_total']} raw rows**; the selected, uniformly rescored result contains **180 rows / 90 paired task IDs**. The selection history is in `final_results/infrastructure_history.json`.
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

The archive is {artifact_bytes:,} bytes. Validate the tarball SHA256 and every extracted member against `manifest.json` before use. Do not execute the code snapshots as if they were a newly frozen experiment.

{diagnostic_readme(summary)}
""".encode("utf-8")


def tar_bytes(payloads: list[tuple[str, bytes]]) -> bytes:
    uncompressed = io.BytesIO()
    with tarfile.open(fileobj=uncompressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for target, data in payloads:
            info = tarfile.TarInfo(target)
            info.size = len(data)
            info.mode = 0o644
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            archive.addfile(info, io.BytesIO(data))
    result = io.BytesIO()
    with gzip.GzipFile(fileobj=result, mode="wb", filename="", mtime=0, compresslevel=6) as compressed:
        compressed.write(uncompressed.getvalue())
    return result.getvalue()


def verify_tarball(blob: bytes, payloads: list[tuple[str, bytes]], sanitizer: Sanitizer) -> None:
    expected = {name: data for name, data in payloads}
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as archive:
        members = archive.getmembers()
        if len(members) != len(expected):
            raise ValueError("Unexpected tar member count")
        for member in members:
            if not member.isfile() or member.name not in expected or member.name.startswith("/") or ".." in Path(member.name).parts:
                raise ValueError("Unsafe or unexpected tar member")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("Missing tar member stream")
            data = stream.read()
            if data != expected[member.name]:
                raise ValueError("Tarball round-trip content mismatch")
            sanitizer.verify(data, member.name)


def attach_outer_diagnostics(manifest: dict, summary: dict, summary_data: bytes, readme_data: bytes) -> None:
    manifest["runtime_provenance"] = summary["runtime_provenance"]
    manifest["outer_diagnostics"] = {
        "generator_version": VERSION,
        "generator_source_sha256": sha(Path(__file__).read_bytes()),
        "generator_logical_path": "frozen_delivery/archive_pilot.py",
        "derived_only_from_existing_archived_records": True,
        "tarball_modified": False,
        "files": {
            "error-summary.json": {"sha256": sha(summary_data), "bytes": len(summary_data)},
            "README.md": {"sha256": sha(readme_data), "bytes": len(readme_data)},
        },
    }


def refresh_outer(out: Path, root: Path, write: bool) -> None:
    """Rebuild only outer diagnostics, using immutable sanitized members as input."""
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    artifact = (out / "pilot-artifacts.tar.gz").read_bytes()
    artifact_hash = sha(artifact)
    if artifact_hash != manifest["artifact"]["sha256"]:
        raise ValueError("Existing tarball does not match manifest")
    sanitizer = Sanitizer(root)
    expected = {entry["archive_path"]: entry for entry in manifest["files"]}
    payloads = {}
    with tarfile.open(fileobj=io.BytesIO(artifact), mode="r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile() or member.name not in expected or member.name in payloads or member.name.startswith("/") or ".." in Path(member.name).parts:
                raise ValueError("Unsafe or unexpected archived member")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("Missing archived member")
            data = stream.read()
            if sha(data) != expected[member.name]["archived_content_sha256"]:
                raise ValueError("Existing member does not match manifest")
            sanitizer.verify(data, member.name)
            payloads[member.name] = data
    if set(payloads) != set(expected):
        raise ValueError("Incomplete existing archive")
    summary = error_summary(payloads, artifact_hash)
    summary_data = json_bytes(summary)
    readme_data = readme(manifest["counts"], manifest["artifact"]["bytes"], summary)
    attach_outer_diagnostics(manifest, summary, summary_data, readme_data)
    manifest_data = json_bytes(manifest)
    for name, data in (("error-summary.json", summary_data), ("README.md", readme_data), ("manifest.json", manifest_data)):
        sanitizer.verify(data, name)
        if write:
            (out / name).write_bytes(data)
    if sha((out / "pilot-artifacts.tar.gz").read_bytes()) != artifact_hash:
        raise ValueError("Tarball changed during outer-only refresh")
    print(json.dumps({"mode": "refresh-outer-write" if write else "refresh-outer-plan", "tarball_modified": False,
                      "tarball_sha256": artifact_hash, "outer_files": ["README.md", "manifest.json", "error-summary.json"],
                      "final_by_system": summary["selected_final_180"]["by_system"], "privacy_scan": "passed"}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "staged_archive")
    parser.add_argument("--write", action="store_true", help="Write the sanitized tarball, manifest and README; default is plan only")
    parser.add_argument("--refresh-outer", action="store_true", help="Derive outer error summary/provenance from the existing tarball without changing it")
    args = parser.parse_args()
    root = args.source_root.resolve(strict=True)
    if args.refresh_outer:
        refresh_outer(args.out.resolve(strict=True), root, args.write)
        return
    selected = select_files(root)
    counts = historical_counts(root)
    sanitizer = Sanitizer(root)
    payloads, entries = [], []
    for source, target, category in selected:
        original = source.read_bytes()
        sanitized = sanitizer.file(source, original)
        sanitizer.verify(sanitized, target)
        payloads.append((target, sanitized))
        entries.append({"logical_source_path": source.relative_to(root).as_posix(), "archive_path": target,
                        "category": category, "source_content_sha256": sha(original),
                        "archived_content_sha256": sha(sanitized), "source_bytes": len(original),
                        "archived_bytes": len(sanitized), "source_observed_mtime_utc": stamp(source.stat().st_mtime),
                        "reserialized_or_redacted": original != sanitized})
    artifact = tar_bytes(payloads)
    verify_tarball(artifact, payloads, sanitizer)
    for (source, _, _), entry in zip(selected, entries):
        if sha(source.read_bytes()) != entry["source_content_sha256"]:
            raise ValueError("Historical source changed during archive creation")
    manifest = {"schema_version": "1.0", "generator": f"archive_pilot.py/{VERSION}",
                "exported_utc": datetime.now(timezone.utc).isoformat(),
                "historical_run_date": "2026-11-20", "not_frozen_comparable": True,
                "historical_exploratory_pilot": True, "new_model_inference": False,
                "contains_complete_pre_run_frozen_code": False,
                "sanitized_not_byte_identical_to_local_raw_logs": True,
                "artifact": {"filename": "pilot-artifacts.tar.gz", "sha256": sha(artifact), "bytes": len(artifact)},
                "counts": counts, "file_count": len(entries),
                "sanitized_uncompressed_bytes": sum(len(data) for _, data in payloads),
                "privacy_scan": {"result": "passed", "known_environment_key_scanned": bool(sanitizer.secret),
                                 "patterns": ["local username", "drive/user-home path", "email", "API-key shape", "bearer token", "credential value"],
                                 "redaction_counts": dict(sorted(sanitizer.counts.items()))},
                "source_path_policy": "logical source paths only, relative to historical evaluation root",
                "snapshot_policy": "Current source files observed at export; per-file hashes/mtimes, not asserted pre-run frozen.",
                "files": entries}
    summary = error_summary(dict(payloads), manifest["artifact"]["sha256"])
    summary_data = json_bytes(summary)
    readme_data = readme(counts, len(artifact), summary)
    attach_outer_diagnostics(manifest, summary, summary_data, readme_data)
    manifest_data = json_bytes(manifest)
    sanitizer.verify(manifest_data, "manifest.json")
    sanitizer.verify(readme_data, "README.md")
    sanitizer.verify(summary_data, "error-summary.json")
    plan = {"mode": "write" if args.write else "plan", "not_frozen_comparable": True,
            "file_count": len(entries), "raw_rows": counts["raw_rows_total"], "selected_final_rows": 180,
            "source_bytes": sum(item["source_bytes"] for item in entries),
            "sanitized_bytes": manifest["sanitized_uncompressed_bytes"], "tar_gz_bytes": len(artifact),
            "output_files": ["README.md", "manifest.json", "error-summary.json", "pilot-artifacts.tar.gz"], "privacy_scan": "passed"}
    if args.write:
        out = args.out.resolve()
        if out == root or root.is_relative_to(out) or out in {source for source, _, _ in selected}:
            raise ValueError("Unsafe output directory")
        if out.exists() and any(out.iterdir()):
            raise ValueError("Refuse to overwrite a nonempty output directory")
        out.mkdir(parents=True, exist_ok=True)
        for name, data in (("pilot-artifacts.tar.gz", artifact), ("manifest.json", manifest_data), ("README.md", readme_data), ("error-summary.json", summary_data)):
            with (out / name).open("xb") as stream:
                stream.write(data)
        # Read back the final files; no extraction or source mutation is required.
        if sha((out / "pilot-artifacts.tar.gz").read_bytes()) != manifest["artifact"]["sha256"]:
            raise ValueError("Written artifact integrity mismatch")
        sanitizer.verify((out / "manifest.json").read_bytes(), "manifest.json")
        sanitizer.verify((out / "README.md").read_bytes(), "README.md")
        sanitizer.verify((out / "error-summary.json").read_bytes(), "error-summary.json")
    print(json.dumps(plan, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
