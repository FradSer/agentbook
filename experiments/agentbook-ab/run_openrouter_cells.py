#!/usr/bin/env python
"""Run A/B cells via OpenRouter (weaker OSS model, not Cursor agents).

Reads prepared prompts from prompts.api.json (or prompt.md under runs/),
loads key source files, asks the model for a unified diff, applies it, and
commits ``agent fix``.

  export OPENROUTER_API_KEY=sk-or-v1-...
  uv run python run_openrouter_cells.py --cells cells_api.json
  uv run python run_openrouter_cells.py --instance sympy__sympy-14976 --arm control
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).parent
TASKS = ROOT / "tasks"
RUNS = ROOT / "runs"
MANIFEST = TASKS / "manifest.json"
REPO_ROOT = ROOT.parent.parent

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODELS = (
    "openai/gpt-oss-20b:free",
    "openai/gpt-oss-20b",
)
MAX_TOKENS = 16384
TIMEOUT_SECONDS = 300
DELAY_SECONDS = 20
MAX_RETRIES = 6
RETRY_BACKOFF_SECONDS = 30

OUTPUT_FORMAT = """

## Output format (required)

Do NOT edit test files. For each source file you change, output one block:

FILE: sympy/path/to/file.py
<<<<<<< SEARCH
(paste exact consecutive lines from the source above — must match verbatim)
=======
(the replacement lines)
>>>>>>> REPLACE

You may output multiple FILE/SEARCH/REPLACE blocks. No explanation text outside these blocks.

Example:
FILE: sympy/printing/pycode.py
<<<<<<< SEARCH
    def _print_Float(self, e):
=======
    def _print_Float(self, e):
        # fix here
>>>>>>> REPLACE
"""


def apply_search_replace(run_repo: Path, response: str) -> bool:
    pattern = re.compile(
        r"FILE:\s*(?P<path>[\w./-]+\.py)\s*\n"
        r"<<<<<<< SEARCH\n"
        r"(?P<search>.*?)"
        r"=======\n"
        r"(?P<replace>.*?)"
        r">>>>>>> REPLACE",
        re.DOTALL,
    )
    applied = False
    for m in pattern.finditer(response):
        rel = m.group("path").strip().lstrip("/")
        if rel.startswith("a/") or rel.startswith("b/"):
            rel = rel[2:]
        fpath = run_repo / rel
        if not fpath.is_file():
            continue
        search = m.group("search").replace("\r\n", "\n")
        replace = m.group("replace").replace("\r\n", "\n")
        if search.endswith("\n"):
            search = search[:-1]
        if replace.endswith("\n"):
            replace = replace[:-1]
        original = fpath.read_text(errors="replace")
        if search not in original:
            continue
        fpath.write_text(original.replace(search, replace, 1))
        applied = True
    return applied


def load_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key:
        return key
    env_file = REPO_ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("OPENROUTER_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                if key:
                    return key
    raise RuntimeError(
        "OPENROUTER_API_KEY not set. Export it or add to repo root .env"
    )


def load_source_context(iid: str, repo: Path, max_chars: int = 18000) -> str:
    meta_path = TASKS / iid / "META.json"
    if not meta_path.is_file():
        return ""
    meta = json.loads(meta_path.read_text())
    loaded: list[str] = []
    total = 0
    seen: set[str] = set()

    def add_file(rel: str) -> None:
        nonlocal total
        if rel in seen or total >= max_chars:
            return
        fpath = repo / rel
        if not fpath.is_file():
            return
        content = fpath.read_text(errors="replace")
        if len(content) > 8000:
            content = content[:8000] + "\n# ... truncated ...\n"
        loaded.append(f"### {rel}\n```python\n{content}\n```")
        seen.add(rel)
        total += len(content)

    for gf in meta.get("gold_files", []):
        add_file(gf)
    bug = (TASKS / iid / "BUG.md").read_text()
    for match in re.finditer(r"([\w/.]+\.py)", bug):
        add_file(match.group(1))
    return "\n\n".join(loaded)


def call_openrouter_messages(
    api_key: str,
    messages: list[dict[str, str]],
    models: tuple[str, ...],
) -> tuple[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/agentbook",
        "X-Title": "agentbook-ab-openrouter",
    }
    body_base = {
        "max_tokens": MAX_TOKENS,
        "temperature": 0.0,
        "messages": messages,
    }
    last_err: Exception | None = None
    with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
        for model in models:
            body = {**body_base, "model": model}
            for attempt in range(MAX_RETRIES):
                try:
                    resp = client.post(OPENROUTER_URL, headers=headers, json=body)
                    if resp.status_code == 429:
                        wait = RETRY_BACKOFF_SECONDS * (attempt + 1)
                        print(
                            f"  {model}: rate limited, wait {wait}s "
                            f"(attempt {attempt + 1}/{MAX_RETRIES})",
                            flush=True,
                        )
                        time.sleep(wait)
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    msg = data["choices"][0]["message"]
                    content = msg.get("content") or msg.get("reasoning") or ""
                    if not content and msg.get("refusal"):
                        content = str(msg["refusal"])
                    if not str(content).strip():
                        raise ValueError("empty model content")
                    return str(content), model
                except httpx.HTTPStatusError as exc:
                    last_err = exc
                    if exc.response.status_code in (429, 502, 503) and attempt < MAX_RETRIES - 1:
                        wait = RETRY_BACKOFF_SECONDS * (attempt + 1)
                        print(f"  {model}: HTTP {exc.response.status_code}, wait {wait}s", flush=True)
                        time.sleep(wait)
                        continue
                    print(f"  model {model} failed: {exc}", flush=True)
                    break
                except Exception as exc:  # noqa: BLE001
                    last_err = exc
                    print(f"  model {model} failed: {exc}", flush=True)
                    break
    raise RuntimeError(f"All models failed: {last_err}") from last_err


def response_has_patch(response: str) -> bool:
    return "FILE:" in response and "<<<<<<< SEARCH" in response


def extract_diff_text(response: str) -> str:
    blocks = re.findall(r"```diff\n(.*?)```", response, re.DOTALL | re.IGNORECASE)
    if blocks:
        return "\n".join(blocks)
    if "--- a/" in response or "--- " in response:
        return response
    return ""


def apply_diff(run_repo: Path, diff_text: str) -> bool:
    if not diff_text.strip():
        return False
    diff_file = run_repo / "_model_diff.patch"
    diff_file.write_text(diff_text)
    for args in (
        ["git", "apply", "--whitespace=nowarn", "_model_diff.patch"],
        ["git", "apply", "-3", "--whitespace=nowarn", "_model_diff.patch"],
        ["patch", "-p1", "--forward", "-i", "_model_diff.patch"],
    ):
        r = subprocess.run(
            args, cwd=run_repo, capture_output=True, text=True, timeout=60
        )
        if r.returncode == 0:
            diff_file.unlink(missing_ok=True)
            return True
    diff_file.unlink(missing_ok=True)
    return False


def commit_agent_fix(run_repo: Path) -> bool:
    stat = subprocess.run(
        ["git", "diff", "--stat", "HEAD"],
        cwd=run_repo,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if not stat.stdout.strip():
        return False
    subprocess.run(["git", "add", "-A"], cwd=run_repo, capture_output=True, timeout=60)
    r = subprocess.run(
        ["git", "commit", "-m", "agent fix"],
        cwd=run_repo,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return r.returncode == 0


def load_cell_prompt(iid: str, arm: str, prompts_path: Path) -> str:
    if prompts_path.is_file():
        prompts = json.loads(prompts_path.read_text())
        spec = prompts.get(f"{iid}__{arm}")
        if spec and spec.get("prompt"):
            return spec["prompt"]
    prompt_md = RUNS / f"{iid}__{arm}" / "prompt.md"
    if prompt_md.is_file():
        return prompt_md.read_text()
    raise FileNotFoundError(f"No prompt for {iid}__{arm}")


def run_cell(
    iid: str,
    arm: str,
    api_key: str,
    models: tuple[str, ...],
    prompts_path: Path,
    *,
    skip_done: bool,
) -> dict:
    run_dir = RUNS / f"{iid}__{arm}"
    run_repo = run_dir / "repo"

    if skip_done and run_repo.is_dir():
        from cell_workspace import has_agent_fix

        if has_agent_fix(run_repo):
            return {
                "instance_id": iid,
                "arm": arm,
                "status": "skipped",
                "fix_applied": True,
            }

    if not run_repo.is_dir():
        sys.path.insert(0, str(ROOT))
        from cell_workspace import prepare_run_dir

        prepare_run_dir(iid, arm)
        base_prompt = load_cell_prompt(iid, arm, prompts_path)
        (run_dir / "prompt.md").write_text(base_prompt)

    base_prompt = load_cell_prompt(iid, arm, prompts_path)
    source_ctx = load_source_context(iid, run_repo)
    prompt = (
        base_prompt
        + "\n\n## Relevant source (read-only context)\n\n"
        + (source_ctx or "(no extra files loaded)")
        + OUTPUT_FORMAT
    )
    (run_dir / "prompt_used.md").write_text(prompt)

    messages = [
        {
            "role": "system",
            "content": (
                "You fix Python bugs by emitting FILE/SEARCH/REPLACE blocks only. "
                "Never reply with analysis-only text. Copy SEARCH text exactly from "
                "the provided source."
            ),
        },
        {"role": "user", "content": prompt},
    ]
    try:
        response, model_used = call_openrouter_messages(api_key, messages, models)
        if not response_has_patch(response):
            messages.append({"role": "assistant", "content": response})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your last reply was not a valid patch. Output ONLY one or more "
                        "FILE/SEARCH/REPLACE blocks now. Copy SEARCH lines verbatim from "
                        "the source files above."
                    ),
                }
            )
            follow, model_used = call_openrouter_messages(api_key, messages, models)
            response = follow if response_has_patch(follow) else response + "\n\n" + follow
    except Exception as exc:  # noqa: BLE001
        return {
            "instance_id": iid,
            "arm": arm,
            "status": "api_error",
            "error": str(exc),
        }

    (run_dir / "model_response.md").write_text(response)
    applied = apply_search_replace(run_repo, response)
    if not applied:
        diff_text = extract_diff_text(response)
        applied = apply_diff(run_repo, diff_text)
    committed = commit_agent_fix(run_repo) if applied else False

    return {
        "instance_id": iid,
        "arm": arm,
        "status": "completed",
        "model": model_used,
        "fix_applied": committed,
        "response_length": len(response),
    }


def dedupe_cells(cells: list[list[str]]) -> list[list[str]]:
    seen: set[tuple[str, str]] = set()
    out: list[list[str]] = []
    for iid, arm in cells:
        key = (iid, arm)
        if key in seen:
            continue
        seen.add(key)
        out.append([iid, arm])
    return sorted(out, key=lambda x: (x[0], x[1]))


def iter_cells(
    cells_path: Path | None,
    manifest_path: Path,
    instance: str | None,
    arm_filter: str | None,
) -> list[tuple[str, str]]:
    if instance:
        arms = [arm_filter] if arm_filter else ["control", "good"]
        return [(instance, a) for a in arms]
    if cells_path and cells_path.is_file():
        raw = json.loads(cells_path.read_text())
        return [(c[0], c[1]) for c in raw]
    manifest = json.loads(manifest_path.read_text())
    arms = [arm_filter] if arm_filter else ["control", "good"]
    out: list[tuple[str, str]] = []
    for entry in manifest:
        iid = entry["instance_id"]
        for arm in arms:
            out.append((iid, arm))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Run A/B cells via OpenRouter OSS model")
    ap.add_argument("--cells", type=Path, default=ROOT / "cells_api.json")
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--prompts", type=Path, default=ROOT / "prompts.api.json")
    ap.add_argument("--instance", help="Single instance_id")
    ap.add_argument("--arm", choices=("control", "good"))
    ap.add_argument("--model", action="append", help="OpenRouter model id (repeatable)")
    ap.add_argument("--skip-done", action="store_true")
    ap.add_argument("--delay", type=float, default=DELAY_SECONDS)
    ap.add_argument("-o", "--results", type=Path, default=ROOT / "openrouter_run_results.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    models = tuple(args.model) if args.model else DEFAULT_MODELS
    api_key = load_api_key()
    cells = iter_cells(args.cells, args.manifest, args.instance, args.arm)

    print(f"OpenRouter run: {len(cells)} cells, models={models}")
    if args.dry_run:
        for iid, arm in cells[:10]:
            print(f"  {iid}__{arm}")
        if len(cells) > 10:
            print(f"  ... +{len(cells) - 10} more")
        return

    results: list[dict] = []
    for i, (iid, arm) in enumerate(cells):
        print(f"[{i + 1}/{len(cells)}] {iid} [{arm}] ...", flush=True)
        result = run_cell(
            iid,
            arm,
            api_key,
            models,
            args.prompts,
            skip_done=args.skip_done,
        )
        results.append(result)
        print(
            f"  -> {result['status']} fix={result.get('fix_applied')}",
            flush=True,
        )
        if i < len(cells) - 1 and args.delay > 0:
            time.sleep(args.delay)

    args.results.write_text(json.dumps(results, indent=2) + "\n")
    applied = sum(1 for r in results if r.get("fix_applied"))
    errors = [r for r in results if r.get("status") == "api_error"]
    if errors:
        err_path = ROOT / "cells_api_errors.json"
        err_cells = dedupe_cells([[r["instance_id"], r["arm"]] for r in errors])
        if err_path.is_file():
            existing = json.loads(err_path.read_text())
            err_cells = dedupe_cells(existing + err_cells)
        err_path.write_text(json.dumps(err_cells, indent=2) + "\n")
        print(f"  api_error cells saved -> {err_path.name} ({len(err_cells)} total)")
    print(f"\nWrote {args.results} — fixes committed: {applied}/{len(results)}")


if __name__ == "__main__":
    main()
