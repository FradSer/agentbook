"""SWE-bench retrieval gate test (real-mode, requires running agentbook API).

Skipped unless RUN_REAL_EVAL=1 and AGENTBOOK_GATE_URL are set.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3] / "experiments" / "agentbook-ab"
GATE_SCRIPT = ROOT / "eval_retrieval_gate.py"
DEFAULT_MANIFEST = ROOT / "tasks" / "manifest.lift.json"


def _gate_enabled() -> bool:
    return bool(os.environ.get("RUN_REAL_EVAL")) and bool(
        os.environ.get("AGENTBOOK_GATE_URL")
    )


@pytest.mark.eval
def test_swebench_retrieval_gate() -> None:
    if not _gate_enabled():
        pytest.skip(
            "requires RUN_REAL_EVAL=1 and AGENTBOOK_GATE_URL "
            "(e.g. http://127.0.0.1:8078)"
        )

    manifest = os.environ.get("AGENTBOOK_GATE_MANIFEST", str(DEFAULT_MANIFEST))
    api_url = os.environ["AGENTBOOK_GATE_URL"]
    out = ROOT / "retrieval_gate_report.ci.json"

    cmd = [
        sys.executable,
        str(GATE_SCRIPT),
        "--manifest",
        manifest,
        "--base-url",
        api_url,
        "-o",
        str(out),
    ]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError(
            f"retrieval gate failed:\n{proc.stdout}\n{proc.stderr}"
        )

    report = json.loads(out.read_text())
    assert report["recall@3"] == 1.0, report.get("failures", [])
    assert report.get("content_sufficient@1", 0) == 1.0, report.get("failures", [])
    assert report.get("steps_present@1", 0) == 1.0, report.get("failures", [])
    if report.get("expected_embedding_provider") == "voyage":
        for row in report["per_task"]:
            assert row["embedding_provider"] == "voyage"
            assert row["rerank_provider"] == "voyage"
