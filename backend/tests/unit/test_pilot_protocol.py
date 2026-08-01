"""Contract tests for the private Codex dogfood pilot protocol."""

from __future__ import annotations

import json
import stat
import sys
import urllib.error
import urllib.parse
from pathlib import Path

import pytest

_SCRIPTS = (
    Path(__file__).resolve().parents[3] / "skills" / "using-agentbook" / "scripts"
)
_REPO = Path(__file__).resolve().parents[3]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from pilot import (  # noqa: E402
    PilotLedger,
    assign_arm,
    recall_public,
    sanitize_error,
    summarize,
)


def test_sanitize_error_keeps_only_public_debugging_context():
    raw = """Traceback (most recent call last):
  File "/Users/alice/Developer/acme-payments/api.py", line 42, in charge
    raise RuntimeError(customer_email)
RuntimeError: request to https://billing.acme.internal/v1 failed for alice@acme.io
"""

    result = sanitize_error(raw, ["python=3.11.9", "fastapi=0.136.1"])

    assert result.eligible is True
    assert result.public_query.startswith("RuntimeError:")
    assert "Traceback" not in result.public_query
    assert "/Users/" not in result.public_query
    assert "acme" not in result.public_query
    assert "alice@" not in result.public_query
    assert "<url>" in result.public_query
    assert "<email>" in result.public_query
    assert "env: fastapi=0.136.1, python=3.11.9" in result.public_query
    assert set(result.redactions) >= {"email", "url"}


@pytest.mark.parametrize(
    "secret",
    [
        "ak_" + "a" * 32,
        "sk-proj-" + "b" * 32,
        "ghp_" + "c" * 36,
        "AKIA" + "D" * 16,
        "Bearer " + "e" * 32,
        "password=" + "f" * 32,
    ],
)
def test_sanitize_error_never_emits_known_secret_shapes(secret: str):
    result = sanitize_error(f"RuntimeError: upstream rejected {secret}")

    assert result.eligible is True
    assert secret not in result.public_query
    assert "<secret>" in result.public_query
    assert "secret" in result.redactions


def test_sanitize_error_rejects_invalid_dependency_metadata():
    result = sanitize_error(
        "TypeError: unsupported operand",
        ["private-package=https://token@example.internal/wheel"],
    )

    assert result.eligible is False
    assert "invalid_dependency" in result.block_reasons
    assert "example.internal" not in result.public_query


def test_sanitize_error_redacts_operator_supplied_private_terms():
    result = sanitize_error(
        "RuntimeError: tenant AcmeHealth failed in ProjectFalcon",
        private_terms=["AcmeHealth", "ProjectFalcon"],
    )

    assert result.eligible is True
    assert "AcmeHealth" not in result.public_query
    assert "ProjectFalcon" not in result.public_query
    assert result.public_query.count("<private>") == 2
    assert "private_term" in result.redactions


def test_sanitize_error_redacts_quoted_values_relative_paths_and_long_ids():
    result = sanitize_error(
        "RuntimeError: customer 'Northwind Health' failed loading "
        "src/northwind/order.py for account_id=123456789"
    )

    assert result.eligible is True
    assert "Northwind" not in result.public_query
    assert "src/" not in result.public_query
    assert "123456789" not in result.public_query
    assert "<value>" in result.public_query
    assert "<path>" in result.public_query
    assert "<private>" in result.public_query


@pytest.mark.parametrize(
    "payload",
    [
        "DatabaseError: SELECT email FROM customers WHERE tenant_id = 42",
        'RuntimeError: response={"customer":"northwind","token":"value"}',
    ],
)
def test_sanitize_error_blocks_code_or_structured_business_payloads(payload: str):
    result = sanitize_error(payload)

    assert result.eligible is False
    assert result.public_query == ""
    assert "code_like_payload" in result.block_reasons


def test_assignment_is_stable_and_balanced_without_storing_repo_name():
    assignments = [assign_arm(f"incident-{index}", "pilot-v1") for index in range(40)]

    assert assignments == [
        assign_arm(f"incident-{index}", "pilot-v1") for index in range(40)
    ]
    assert set(assignments) == {"control", "treatment"}


def test_ledger_appends_private_events_and_rejects_duplicate_finish(tmp_path: Path):
    path = tmp_path / "private" / "pilot.jsonl"
    ledger = PilotLedger(path, experiment_seed="pilot-v1")

    started = ledger.start(
        error="ValueError: private-product returned an invalid literal for int()",
        repository="/Users/alice/Developer/private-product",
        dependencies=["python=3.11.9"],
        incident_id="incident-1",
    )
    finished = ledger.finish(
        incident_id="incident-1",
        first_attempt_passed=True,
        pre_attempt_recall="hit",
        match_quality="exact",
        solution_id="solution-1",
        verification="uv run pytest tests/unit/test_parser.py",
    )

    assert started["event"] == "start"
    assert started["repository_id"] != "private-product"
    assert "private-product" not in path.read_text()
    assert finished["event"] == "finish"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    events = [json.loads(line) for line in path.read_text().splitlines()]
    assert [event["event"] for event in events] == ["start", "finish"]

    with pytest.raises(ValueError, match="already finished"):
        ledger.finish(
            incident_id="incident-1",
            first_attempt_passed=False,
            pre_attempt_recall="miss",
            verification="pytest",
        )


def test_ledger_records_unavailable_recall_without_blocking_work(tmp_path: Path):
    ledger = PilotLedger(tmp_path / "pilot.jsonl")
    ledger.start(
        error="BuildError: compiler unavailable",
        repository="/repo",
        incident_id="incident-unavailable",
    )

    event = ledger.finish(
        incident_id="incident-unavailable",
        first_attempt_passed=False,
        pre_attempt_recall="unavailable",
        verification="make test",
    )

    assert event["pre_attempt_recall"] == "unavailable"
    assert event["first_attempt_passed"] is False


def test_ledger_only_releases_treatment_query_before_first_attempt(tmp_path: Path):
    ledger = PilotLedger(tmp_path / "pilot.jsonl")
    treatment = ledger.start(
        error="RuntimeError: treatment failure",
        repository="/repo",
        incident_id="treatment",
        arm="treatment",
    )
    ledger.start(
        error="RuntimeError: control failure",
        repository="/repo",
        incident_id="control",
        arm="control",
    )

    assert ledger.query_for_recall("treatment") == treatment["public_query"]
    with pytest.raises(ValueError, match="control arm cannot recall"):
        ledger.query_for_recall("control")

    ledger.finish(
        incident_id="control",
        first_attempt_passed=False,
        pre_attempt_recall="not_called",
        verification="make fast",
    )
    assert ledger.query_for_recall("control", crossover=True)


def test_anonymous_rest_recall_never_sends_authorization():
    payload = {
        "no_good_match": False,
        "results": [
            {
                "problem_id": "problem-1",
                "match_quality": "exact",
                "best_solution": {
                    "solution_id": "solution-1",
                    "content": "Use the validated fix.",
                    "steps": ["apply fix", "run tests"],
                    "confidence": 0.8,
                    "verification": [{"command": "make fast", "expected": "pass"}],
                },
            }
        ],
    }
    seen = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(payload).encode()

    def opener(request, *, timeout):
        seen["request"] = request
        seen["timeout"] = timeout
        return Response()

    result = recall_public("RuntimeError: safe query", opener=opener)

    request = seen["request"]
    query = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)
    assert request.get_header("Authorization") is None
    assert query["q"] == ["RuntimeError: safe query"]
    assert result["status"] == "hit"
    assert result["solution_id"] == "solution-1"


def test_anonymous_rest_recall_degrades_to_unavailable():
    def opener(_request, *, timeout):
        raise urllib.error.URLError("offline")

    result = recall_public("RuntimeError: safe query", opener=opener)

    assert result == {"status": "unavailable", "reason": "network_error"}


def test_summary_passes_only_the_precommitted_live_and_paired_gates(tmp_path: Path):
    ledger = PilotLedger(tmp_path / "pilot.jsonl", experiment_seed="pilot-v1")

    for index in range(20):
        incident_id = f"live-{index}"
        ledger.start(
            error=f"RuntimeError: live failure {index}",
            repository="/repo",
            incident_id=incident_id,
            arm="treatment" if index % 2 else "control",
        )
        ledger.finish(
            incident_id=incident_id,
            first_attempt_passed=index % 3 != 0,
            pre_attempt_recall="hit" if index % 2 else "not_called",
            verification="make fast",
        )

    for index in range(20):
        pair_id = f"replay-{index}"
        for arm in ("control", "treatment"):
            incident_id = f"{pair_id}-{arm}"
            ledger.start(
                error=f"TypeError: replay failure {index}",
                repository="/repo",
                incident_id=incident_id,
                cohort="replay",
                pair_id=pair_id,
                arm=arm,
            )
            # Five treatment-only wins: +25pp, 5 net wins, zero harm.
            passed = index >= 5 if arm == "control" else True
            ledger.finish(
                incident_id=incident_id,
                first_attempt_passed=passed,
                pre_attempt_recall="hit" if arm == "treatment" else "not_called",
                verification="make fast",
            )

    report = summarize(ledger.path)

    assert report["status"] == "pass"
    assert report["live"]["completed"] == 20
    assert report["live"]["completion_rate"] == 1.0
    assert report["replay"]["paired_n"] == 20
    assert report["replay"]["pass_rate_delta"] == 0.25
    assert report["replay"]["paired_lift"] == 5
    assert report["replay"]["paired_harm"] == 0


def test_summary_stops_on_harm_even_when_average_lift_is_positive(tmp_path: Path):
    ledger = PilotLedger(tmp_path / "pilot.jsonl")
    for index in range(20):
        incident_id = f"live-{index}"
        ledger.start(
            error=f"RuntimeError: live failure {index}",
            repository="/repo",
            incident_id=incident_id,
        )
        ledger.finish(
            incident_id=incident_id,
            first_attempt_passed=True,
            pre_attempt_recall="not_called",
            verification="make fast",
        )

    for index in range(20):
        pair_id = f"pair-{index}"
        control_passed = index >= 5
        treatment_passed = index != 5
        for arm, passed in (
            ("control", control_passed),
            ("treatment", treatment_passed),
        ):
            incident_id = f"{pair_id}-{arm}"
            ledger.start(
                error=f"TypeError: replay failure {index}",
                repository="/repo",
                incident_id=incident_id,
                cohort="replay",
                pair_id=pair_id,
                arm=arm,
            )
            ledger.finish(
                incident_id=incident_id,
                first_attempt_passed=passed,
                pre_attempt_recall="hit" if arm == "treatment" else "not_called",
                verification="make fast",
            )

    report = summarize(ledger.path)

    assert report["replay"]["paired_lift"] == 5
    assert report["replay"]["paired_harm"] == 1
    assert report["status"] == "fail_harm"


def test_summary_remains_collecting_before_sample_floor(tmp_path: Path):
    ledger = PilotLedger(tmp_path / "pilot.jsonl")
    ledger.start(
        error="RuntimeError: one event",
        repository="/repo",
        incident_id="one",
    )

    report = summarize(ledger.path)

    assert report["status"] == "collecting"
    assert "live_completed<20" in report["unmet_gates"]
    assert "replay_pairs<20" in report["unmet_gates"]


def test_skill_enforces_the_randomized_privacy_preserving_protocol():
    skill = (_REPO / "skills/using-agentbook/SKILL.md").read_text()

    assert "disable-model-invocation: true" not in skill
    assert "pilot.py start" in skill
    assert "pilot.py recall" in skill
    assert "pilot.py finish" in skill
    assert "public_query" in skill
    assert "Control arm" in skill
    assert "anonymous REST" in skill
    assert "Do not run `pilot.py recall` before" in skill
    assert "recall_unavailable" in skill
    assert "AGENTBOOK_API_KEY" not in skill
    assert "Keychain" not in skill
    assert "MCP alternative" not in skill


def test_dogfood_playbook_pins_sample_floor_and_stop_gates():
    playbook = (_REPO / "docs/codex-dogfood-pilot.md").read_text()

    assert "20 completed live incidents" in playbook
    assert "20 completed replay pairs" in playbook
    assert "at least +15 percentage points" in playbook
    assert "at least 3 net paired wins" in playbook
    assert "zero paired harm" in playbook
    assert "90% ledger completion" in playbook
    assert "skill-only" in playbook
    assert "[mcp_servers.agentbook]" not in playbook
    assert "Keychain" not in playbook
    assert "LaunchAgent" not in playbook
