"""OpenRouter benchmark may only use openai/gpt-oss-20b:free."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "experiments" / "agentbook-ab" / "run_openrouter_cells.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_openrouter_cells", RUNNER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["run_openrouter_cells"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_allowed_openrouter_model_passes() -> None:
    mod = _load_runner()
    models = mod.normalize_openrouter_models(mod.DEFAULT_MODELS)
    assert models == ("openai/gpt-oss-20b:free",)


def test_paid_openrouter_model_rejected() -> None:
    mod = _load_runner()
    with pytest.raises(SystemExit, match="not allowed"):
        mod.normalize_openrouter_models(("openai/gpt-oss-20b",))


def test_disallowed_openrouter_model_rejected() -> None:
    mod = _load_runner()
    with pytest.raises(SystemExit, match="not allowed"):
        mod.normalize_openrouter_models(("anthropic/claude-sonnet-4",))
