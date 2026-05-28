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


def test_router_features_and_rule_policy():
    import json

    from pipeline.arm_context import SYNTH_CACHE
    from pipeline.router import RuleRouter, extract_features

    cache = json.loads(SYNTH_CACHE.read_text())
    e = cache["sympy__sympy-15017"]  # canonical multi-site case
    feats = extract_features(e)
    assert feats["n_repros"] >= 4
    assert feats["is_multisite"] == 1.0
    # multi-site + gemma -> rule picks good_multi_loop first
    r = RuleRouter()
    assert r.select(feats, "gemma4_e4b", k=1) == ["good_multi_loop"]
    assert r.select(feats, "gpt-oss_20b", k=2) == ["good_multi_loop", "good_loop"]


def test_router_outcome_update_round_trips(tmp_path, monkeypatch):
    import json

    from pipeline import router

    log = tmp_path / "outcomes.json"
    monkeypatch.setattr(router, "OUTCOMES_LOG", log)
    log.write_text("[]")
    router.update_from_outcome("gpt-oss_20b", "sympy__sympy-999", "good_loop", True)
    router.update_from_outcome(
        "gpt-oss_20b", "sympy__sympy-999", "good_loop", False
    )  # overwrite
    rows = json.loads(log.read_text())
    assert len(rows) == 1
    assert rows[0]["resolved"] is False


def test_good_router_delegates_to_sub_arm():

    from pipeline.arm_context import SYNTH_CACHE, build_prompt

    if not SYNTH_CACHE.exists():
        return
    # gemma multi-site task -> router picks good_multi_loop, prompt should
    # therefore contain both views.
    prompt, meta = build_prompt(
        "sympy__sympy-15017", "good_router", model_slug="gemma4_e4b"
    )
    assert meta["hint"] == "good_router"
    assert meta["routed_from"] == "good_router"
    assert meta["routed_to"] in (
        "good",
        "good_synth",
        "good_loop",
        "good_multi_loop",
    )


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


# ---------------------------------------------------------------------------
# Feature 2: extract_edits recovers truncated / off-fence SEARCH/REPLACE blocks
# ---------------------------------------------------------------------------


def test_lenient_closing_fence_missing():
    """Then it returns exactly one tuple ("path/x.py", "a = 1", "a = 2").

    Scenario: Closing fence missing because the model hit max_tokens.
    """
    text = (
        "```edit\npath/x.py\n<<<<<<< SEARCH\na = 1\n=======\na = 2\n>>>>>>> REPLACE\n"
    )
    edits = extract_edits(text)
    assert edits == [("path/x.py", "a = 1", "a = 2")]


def test_lenient_python_fence():
    """Then it returns exactly one tuple and the path comes from the first
    non-empty pre-SEARCH line inside the block.

    Scenario: Fence tagged ```python instead of ```edit is still parsed.
    """
    text = (
        "Here is a fix.\n\n"
        "```python\n"
        "sympy/foo.py\n"
        "<<<<<<< SEARCH\n"
        "x = 1\n"
        "=======\n"
        "x = 2\n"
        ">>>>>>> REPLACE\n"
        "```\n"
    )
    edits = extract_edits(text)
    assert edits == [("sympy/foo.py", "x = 1", "x = 2")]


def test_lenient_raw_markers_with_preceding_path():
    """Then it returns exactly one tuple ("path/x.py", "x = 1", "x = 2").

    Scenario: Raw SEARCH/REPLACE markers with no opening fence are recovered
    when a path precedes them.
    """
    text = (
        "Here is the fix.\n\n"
        "path/x.py\n"
        "<<<<<<< SEARCH\n"
        "x = 1\n"
        "=======\n"
        "x = 2\n"
        ">>>>>>> REPLACE\n"
    )
    edits = extract_edits(text)
    assert edits == [("path/x.py", "x = 1", "x = 2")]


def test_lenient_whitespace_tolerance():
    """Then it returns exactly one tuple and the search/replace bodies are
    stripped of leading/trailing whitespace correctly.

    Scenario: Carets-and-equals whitespace tolerance. Truncated (no closing
    fence) so the lenient SR regex must accept mixed caret counts and trailing
    whitespace on the separator.
    """
    text = (
        "```edit\n"
        "sympy/foo.py\n"
        "<<<<< SEARCH\n"
        "old\n"
        "=======   \n"  # trailing spaces on the separator
        "new\n"
        ">>>>>>>> REPLACE\n"
        # no closing fence -- lenient path required
    )
    edits = extract_edits(text)
    assert len(edits) == 1
    path, search, replace = edits[0]
    assert path == "sympy/foo.py"
    assert search.strip() == "old"
    assert replace.strip() == "new"


def test_lenient_path_on_fence_line():
    """Then it returns exactly one tuple ("path/x.py", "old", "new").

    Scenario: Path-on-fence-line ("```edit path/x.py").
    """
    text = (
        "```edit path/x.py\n<<<<<<< SEARCH\nold\n=======\nnew\n>>>>>>> REPLACE\n```\n"
    )
    edits = extract_edits(text)
    assert edits == [("path/x.py", "old", "new")]


def test_lenient_two_complete_pairs_unfenced():
    """Then it returns 2 tuples sharing the same path.

    Scenario: Two complete SEARCH/REPLACE pairs in one unfenced block both
    recover.
    """
    text = (
        "```edit\n"
        "sympy/foo.py\n"
        "<<<<<<< SEARCH\n"
        "a = 1\n"
        "=======\n"
        "a = 2\n"
        ">>>>>>> REPLACE\n"
        "<<<<<<< SEARCH\n"
        "b = 3\n"
        "=======\n"
        "b = 4\n"
        ">>>>>>> REPLACE\n"
        # no closing fence -- truncated
    )
    edits = extract_edits(text)
    assert len(edits) == 2
    assert {e[0] for e in edits} == {"sympy/foo.py"}
    assert ("sympy/foo.py", "a = 1", "a = 2") in edits
    assert ("sympy/foo.py", "b = 3", "b = 4") in edits


def test_lenient_truncated_final_pair_dropped():
    """Then it returns exactly 1 tuple (the complete pair) and the incomplete
    pair is silently discarded.

    Scenario: Truncated final pair is dropped, prior complete pairs kept.
    """
    text = (
        "```edit\n"
        "sympy/foo.py\n"
        "<<<<<<< SEARCH\n"
        "a = 1\n"
        "=======\n"
        "a = 2\n"
        ">>>>>>> REPLACE\n"
        "<<<<<<< SEARCH\n"
        "a = 1\n"
        "=====<truncated>"
    )
    edits = extract_edits(text)
    assert edits == [("sympy/foo.py", "a = 1", "a = 2")]


def test_lenient_truncated_recovers_and_applies(tmp_path):
    """Then mod.py is rewritten to "def f():\\n    return 1\\n", AND when the
    lenient recovery surfaces a tuple under tests/, apply_search_replace
    returns (False, msg) where msg contains "test file" and the working tree
    is unchanged.

    Scenarios: End-to-end -- truncated edit block parses AND applies to a real
    file; test-file edit refusal still fires for a recovered (unfenced) block.
    """
    _write(tmp_path, "def f():\n    return 0\n")
    text = (
        "```edit\n"
        "mod.py\n"
        "<<<<<<< SEARCH\n"
        "return 0\n"
        "=======\n"
        "return 1\n"
        ">>>>>>> REPLACE\n"
        # no closing fence -- truncated
    )
    edits = extract_edits(text)
    assert edits == [("mod.py", "return 0", "return 1")]
    ok, msg = apply_search_replace(tmp_path, edits)
    assert ok, msg
    assert (tmp_path / "mod.py").read_text() == "def f():\n    return 1\n"

    # Test-file refusal still fires for a tuple that the lenient parser would
    # also surface (path = tests/test_x.py). apply_search_replace is the gate.
    (tmp_path / "tests").mkdir()
    target = tmp_path / "tests" / "test_x.py"
    target.write_text("assert True\n")
    text_under_tests = (
        "```edit\n"
        "tests/test_x.py\n"
        "<<<<<<< SEARCH\n"
        "assert True\n"
        "=======\n"
        "assert False\n"
        ">>>>>>> REPLACE\n"
        # no closing fence -- lenient path must still surface this tuple
    )
    leak_edits = extract_edits(text_under_tests)
    assert leak_edits == [("tests/test_x.py", "assert True", "assert False")]
    ok2, msg2 = apply_search_replace(tmp_path, leak_edits)
    assert not ok2
    assert "test file" in msg2
    assert target.read_text() == "assert True\n"


# ---------------------------------------------------------------------------
# Feature 3: agent_loop breaks the doom-loop on unparseable edit intent
# ---------------------------------------------------------------------------


def test_looks_like_edit_intent_partial_markers():
    """Then looks_like_edit_intent returns true / true / false on the three
    inputs. Also covers the Feature 2 "neither SR markers nor ```edit returns
    empty list -- lenient fallback is NOT entered (no _INTENT_RE match)"
    contract: a bash-only reply produces no intent AND extract_edits returns [].

    Scenarios: looks_like_edit_intent detects partial markers; lenient
    fallback short-circuits on non-intent text.
    """
    from harness.prompts import looks_like_edit_intent

    assert looks_like_edit_intent("```edit\n...\n") is True
    assert looks_like_edit_intent("<<<<<<< SEARCH\nfoo\n") is True
    non_intent = "Let me think. I will grep next.\n\n```bash\nls\n```\n"
    assert looks_like_edit_intent(non_intent) is False
    # Lenient fallback is NOT entered for non-intent text.
    assert extract_edits(non_intent) == []


def test_diagnose_edit_block_classifies():
    """Then the returned string contains "closing triple-backtick" /
    "=======" or "separator" / "REPLACE" for the three scenarios.

    Scenarios: diagnose_edit_block classifies the missing closing fence /
    missing separator / truncated mid-block.
    """
    from harness.prompts import diagnose_edit_block

    # Missing closing fence.
    no_close = "```edit\nmod.py\n<<<<<<< SEARCH\nold\n=======\nnew\n>>>>>>> REPLACE\n"
    assert "closing triple-backtick" in diagnose_edit_block(no_close)

    # Missing ======= separator.
    no_sep = "```edit\nmod.py\n<<<<<<< SEARCH\nold\n>>>>>>> REPLACE\n```\n"
    diag = diagnose_edit_block(no_sep)
    assert ("=======" in diag) or ("separator" in diag)

    # Truncated mid-block -- never reaches the REPLACE marker.
    truncated = "```edit\nmod.py\n<<<<<<< SEARCH\nold\n=======\nnew\n"
    assert "REPLACE" in diagnose_edit_block(truncated)


def test_agent_loop_emits_edit_malformed_hint(tmp_path):
    """Then the next user message contains the diagnosis, does NOT contain
    "Respond with EXACTLY ONE ```bash", consecutive_parse_failures increments
    by 1, and the episode does NOT abort yet.

    Scenario: agent_loop emits _EDIT_MALFORMED_HINT instead of _NO_BLOCK_HINT.
    """
    import subprocess

    from harness.agent_loop import run_episode

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, capture_output=True)

    # The reply has SEARCH/REPLACE intent and an opening ```edit fence but no
    # path line precedes the SEARCH marker AND no closing fence -- the lenient
    # parser cannot recover a tuple, so extract_edits returns [] while
    # looks_like_edit_intent returns True. diagnose_edit_block classifies it as
    # "missing closing triple-backtick" because the equals separator and the
    # REPLACE marker are both present.
    truncated_edit_reply = (
        "Here is the fix.\n\n"
        "```edit\n"
        "<<<<<<< SEARCH\n"
        "old\n"
        "=======\n"
        "new\n"
        ">>>>>>> REPLACE\n"
        # no closing fence -- the doom-loop trigger
    )
    done_reply = "```bash\necho AGENT_DONE\n```\n"

    class _StubLLM:
        """In-memory LLM stub conforming to harness.llm_ollama.OllamaLLM.chat."""

        def __init__(self, replies):
            self.replies = list(replies)
            self.calls = []

        def chat(self, model, messages, *, temperature=0.7, seed=0):
            # Record the message list as seen by the model on this turn.
            self.calls.append([dict(m) for m in messages])
            if self.replies:
                return self.replies.pop(0)
            return ""

    stub = _StubLLM([truncated_edit_reply, done_reply])
    episode = run_episode(
        tmp_path,
        "fix the bug",
        stub,  # duck-typed; only `chat` is consumed
        "gemma4:e4b",
        step_budget=2,
        temperature=0.0,
        seed=0,
    )

    # 2 chat() calls were made (turn 1: truncated edit; turn 2: AGENT_DONE).
    assert len(stub.calls) == 2
    turn2_messages = stub.calls[1]
    # The user message appended after turn 1 is the last user-role message.
    user_msgs = [m for m in turn2_messages if m.get("role") == "user"]
    assert user_msgs, "no user message recorded for turn 2"
    last_user = user_msgs[-1]["content"]
    # The diagnosis substring must appear (closing-backtick was the case here).
    assert "closing triple-backtick" in last_user
    # And the generic no-block hint must NOT have leaked into this branch.
    assert "Respond with EXACTLY ONE ```bash" not in last_user
    # 6-strike abort did NOT fire on a single strike.
    assert episode.stop_reason != "parse_failures"
    # consecutive_parse_failures reached exactly 1 -- captured in the notes log
    # (one "unparseable-edit" note appended on turn 1).
    edit_notes = [n for n in episode.notes if "unparseable-edit" in n]
    assert len(edit_notes) == 1
