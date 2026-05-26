"""Tests for the fuzzy SEARCH/REPLACE structured-edit path and good_synth arm."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from harness.prompts import extract_edits  # noqa: E402
from harness.sandbox import apply_search_replace  # noqa: E402


def _write(tmp_path: Path, body: str) -> Path:
    f = tmp_path / "mod.py"
    f.write_text(body)
    return f


def test_extract_edits_parses_path_and_pair():
    text = (
        "Here is the fix:\n\n"
        "```edit\n"
        "sympy/foo.py\n"
        "<<<<<<< SEARCH\n"
        "    return 0\n"
        "=======\n"
        "    return 1\n"
        ">>>>>>> REPLACE\n"
        "```\n"
    )
    edits = extract_edits(text)
    assert edits == [("sympy/foo.py", "    return 0", "    return 1")]


def test_exact_match_replace(tmp_path):
    _write(tmp_path, "def f():\n    return 0\n")
    edits = [("mod.py", "    return 0", "    return 1")]
    ok, msg = apply_search_replace(tmp_path, edits)
    assert ok, msg
    assert (tmp_path / "mod.py").read_text() == "def f():\n    return 1\n"


def test_whitespace_tolerant_match_reindents(tmp_path):
    # File indents with 4 spaces; model's SEARCH used 2 -- must still match and
    # the replacement must be re-indented to the file's actual indentation.
    _write(
        tmp_path, "def f():\n    x = reduce(op, shape) if shape else 0\n    return x\n"
    )
    edits = [
        (
            "mod.py",
            "x = reduce(op, shape) if shape else 0",  # no leading indent at all
            "x = reduce(op, shape) if shape else 1",
        )
    ]
    ok, msg = apply_search_replace(tmp_path, edits)
    assert ok, msg
    assert (
        (tmp_path / "mod.py").read_text()
        == "def f():\n    x = reduce(op, shape) if shape else 1\n    return x\n"
    )


def test_multiline_block_reindent(tmp_path):
    _write(tmp_path, "class C:\n    def m(self):\n        a = 1\n        b = 2\n")
    edits = [("mod.py", "a = 1\nb = 2", "a = 10\nb = 20\nc = 30")]
    ok, msg = apply_search_replace(tmp_path, edits)
    assert ok, msg
    assert (tmp_path / "mod.py").read_text() == (
        "class C:\n    def m(self):\n        a = 10\n        b = 20\n        c = 30\n"
    )


def test_missing_search_block_fails_safely(tmp_path):
    _write(tmp_path, "def f():\n    return 0\n")
    ok, msg = apply_search_replace(tmp_path, [("mod.py", "return 999", "return 1")])
    assert not ok
    assert "not found" in msg
    assert (tmp_path / "mod.py").read_text() == "def f():\n    return 0\n"


def test_refuses_test_file(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("assert True\n")
    ok, msg = apply_search_replace(
        tmp_path, [("tests/test_x.py", "assert True", "assert False")]
    )
    assert not ok
    assert "test file" in msg


def test_good_synth_arm_builds_structured_prompt():
    import json

    from pipeline.arm_context import SYNTH_CACHE, build_prompt

    if not SYNTH_CACHE.exists():
        return  # cache not built in this environment; nothing to assert
    iid = next(iter(json.loads(SYNTH_CACHE.read_text())))
    prompt, meta = build_prompt(iid, "good_synth")
    assert meta["hint"] == "good_synth"
    assert meta.get("synth") is True
    assert "Root-cause pattern" in prompt
    assert "How to verify your fix" in prompt
    # good_synth must NOT carry a ready-to-apply patch (no diff hunk, no relay
    # token); a ```diff *mention* in the how-to-apply instruction is fine.
    assert "--- a/" not in prompt
    assert "+++ b/" not in prompt
    assert "\n@@ " not in prompt
    assert "APPLY_PATCH" not in prompt


def test_run_verification_dual_condition(tmp_path):
    import subprocess

    from harness.sandbox import run_verification

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, capture_output=True)
    # expected present + buggy absent -> PASS
    ok, _ = run_verification(tmp_path, "echo right value", "right", "WRONG")
    assert ok
    # expected present but buggy ALSO present -> FAIL (the 16766 case)
    ok, _ = run_verification(
        tmp_path, "echo 'p[0] # Not supported'", "p[0]", "Not supported"
    )
    assert not ok
    # expected absent -> FAIL
    ok, _ = run_verification(tmp_path, "echo nothing", "right", None)
    assert not ok


def test_good_loop_arm_carries_repros():
    import json

    from pipeline.arm_context import SYNTH_CACHE, build_prompt

    if not SYNTH_CACHE.exists():
        return
    cache = json.loads(SYNTH_CACHE.read_text())
    iid = next((i for i, e in cache.items() if e.get("verifications")), None)
    if iid is None:
        return
    prompt, meta = build_prompt(iid, "good_loop")
    assert meta["hint"] == "good_loop"
    assert meta["verification"]["repros"]
    assert all(r.get("command") for r in meta["verification"]["repros"])
    # same knowledge block as good_synth (no patch)
    assert "Root-cause pattern" in prompt
    assert "--- a/" not in prompt


def test_good_multi_loop_arm_carries_both_views():
    import json

    from pipeline.arm_context import RECALL_CACHE, SYNTH_CACHE, build_prompt

    if not (SYNTH_CACHE.exists() and RECALL_CACHE.exists()):
        return
    synth = json.loads(SYNTH_CACHE.read_text())
    recall = json.loads(RECALL_CACHE.read_text())
    iid = next(
        (i for i in synth if i in recall and synth[i].get("verifications")), None
    )
    if iid is None:
        return
    prompt, meta = build_prompt(iid, "good_multi_loop")
    assert meta["hint"] == "good_multi_loop"
    assert meta["verification"]["repros"]
    # both views present, knowledge unchanged (no patch leaked)
    assert "View 1 -- Prose recall" in prompt
    assert "View 2 -- Synthesized analysis" in prompt
    assert "Root-cause pattern" in prompt
    assert "--- a/" not in prompt
    assert "APPLY_PATCH" not in prompt


def test_run_verifications_all_must_pass(tmp_path):
    import subprocess

    from harness.sandbox import run_verifications

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, capture_output=True)
    # Two repros, both pass -> overall PASS
    ok, _ = run_verifications(
        tmp_path,
        [
            {
                "label": "a",
                "command": "echo right",
                "expected": "right",
                "buggy": "WRONG",
            },
            {"label": "b", "command": "echo ok 1 1", "expected": "1 1", "buggy": None},
        ],
    )
    assert ok
    # One repro fails -> overall FAIL (multi-site detection)
    ok, _ = run_verifications(
        tmp_path,
        [
            {"label": "a", "command": "echo right", "expected": "right", "buggy": None},
            {
                "label": "b-missing-site",
                "command": "echo 0 1",
                "expected": "1 1",
                "buggy": None,
            },
        ],
    )
    assert not ok


def test_run_verification_accepts_alternative_expected(tmp_path):
    import subprocess

    from harness.sandbox import run_verification

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, capture_output=True)
    # any-of alternatives: command output matches one of them
    ok, _ = run_verification(
        tmp_path, "echo IS_OO: True", ["RESULT: oo", "IS_OO: True"], None
    )
    assert ok
    ok, _ = run_verification(
        tmp_path, "echo nothing", ["RESULT: oo", "IS_OO: True"], None
    )
    assert not ok
