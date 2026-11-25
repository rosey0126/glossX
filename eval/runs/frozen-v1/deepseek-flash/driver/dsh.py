"""Official DSH headless invocation for one fresh frozen-v1 workspace."""
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from glossx_eval.systems import Output, output_from_text, stage_papers, task_prompt

HERE = Path(__file__).resolve().parent
ROUTE = "https://api.deepseek.com"
MODEL = "deepseek-flash"
VERSION = "0.2.2-rc.5"


def profile(base_url):
    provider = {
        "api": "openai-completions", "baseURL": base_url,
        "apiKeyEnv": "DEEPSEEK_API_KEY", "models": [{"id": MODEL}],
        "compat": {"supportsDeveloperRole": False, "supportsStore": False},
    }
    entries = [
        {"id": "llm-pi-ai", "config": {"providers": {"matrix-deepseek": provider}}},
        {"id": "agent-default-model", "config": {"provider": "matrix-deepseek", "model": MODEL}},
        {"id": "session-log-deepseek", "config": {"enabled": False}},
        {"id": "tool-fs", "config": {"read": True, "readImage": False, "write": False,
                                     "edit": False, "applyPatch": False}},
    ]
    for plugin in ("llm-retry session-title-llm agent-instructions tool-working-directory "
                   "tool-bash tool-pwsh tool-jobs tool-web tool-skill skill-filesystem "
                   "tool-subagent tool-subagent-fork tool-subagent-control tool-agent-team "
                   "tool-workflow tool-goal tool-todo tool-plugin-manager").split():
        entries.append({"id": plugin, "disabled": True})
    entries.append({"insert": [{"id": "evaluation-read-boundary",
                                 "name": str(HERE / "read-boundary.mjs")}]})
    return entries


def run(task, data_dir, scratch, cli, base_url=ROUTE):
    import fitz
    if base_url != ROUTE and not base_url.startswith("http://127.0.0.1:"):
        raise ValueError("Only the official endpoint or a loopback fixture is supported")
    cli = cli.resolve()
    if json.loads((cli.parent.parent / "package.json").read_text())["version"] != VERSION:
        raise ValueError("Unexpected DSH version")
    home, work = scratch / "home", scratch / "papers"
    home.mkdir(parents=True, exist_ok=False)
    stage_papers(task, data_dir, work)
    # The read-only filesystem tools consume text. Supply the original PDFs
    # and an explicitly page-numbered extraction from each of those same bytes.
    for pdf in work.glob("*.pdf"):
        with fitz.open(pdf) as doc:
            text = "\n".join(f"Page {page.number+1}\n{page.get_text()}" for page in doc)
        pdf.with_suffix(".pdf.pages.txt").write_text(text, encoding="utf-8")
    patch = home / "settings.patch.yml"
    patch.write_text(json.dumps(profile(base_url)), encoding="utf-8")
    env = {**os.environ, "DSH_HOME": str(home.resolve()), "DSH_TELEMETRY_MODE": "DISABLED",
           "DSH_TELEMETRY_DISABLED": "1", "MATRIX_ENDPOINT": base_url + "/chat/completions"}
    if base_url != ROUTE:
        env["DEEPSEEK_API_KEY"] = "offline-fixture"
    command = [shutil.which("node"), "--import", (HERE / "retry.mjs").as_uri(), str(cli),
               "headless", "--patch", str(patch.resolve()), "--json", "--permission-mode",
               "read-only", "--approval-policy", "never", "-"]
    started = time.monotonic()
    proc = subprocess.Popen(command, cwd=work, env=env, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    timeout = False
    try:
        stdout, stderr = proc.communicate(task_prompt(task).encode(), timeout=900)
    except subprocess.TimeoutExpired:
        timeout = True
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        proc.kill()
        stdout, stderr = proc.communicate()
    stdout = stdout.decode("utf-8", "replace")
    stderr = stderr.decode("utf-8", "replace")
    # Keep private paths and credentials out of both traces and terminal errors.
    for literal, replacement in [(env.get("DEEPSEEK_API_KEY"), "[redacted]"),
                                  (str(scratch.resolve()), "<run>"), (str(Path.home()), "<home>")]:
        if literal:
            for token in (json.dumps(literal, ensure_ascii=False)[1:-1], literal, literal.replace("\\", "/")):
                stdout = stdout.replace(token, replacement)
                stderr = stderr.replace(token, replacement)
    final, errors, calls = {}, [], 0
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "final":
            final = event
        elif event.get("type") == "error":
            errors.append(str(event.get("message", event)))
        elif event.get("type") == "tool_call":
            calls += 1
    out = output_from_text(final.get("answer") or final.get("text") or "")
    reason = final.get("reason") or {}
    if timeout:
        out.error = "timeout after 900s"
    elif proc.returncode or reason.get("kind") != "completed":
        out.error = " ".join(errors) or str(reason or stderr[-2000:] or f"DSH exit {proc.returncode}")
    out.tool_calls = calls
    out.latency_s = time.monotonic() - started
    return out, stdout, stderr
