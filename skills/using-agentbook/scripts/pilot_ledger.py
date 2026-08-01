"""Append-only storage and precommitted metrics for the Agentbook pilot."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pilot_privacy import sanitize_error

SCHEMA_VERSION = 1
DEFAULT_LEDGER = Path("~/.local/share/agentbook/pilot.jsonl").expanduser()
DEFAULT_EXPERIMENT_SEED = "agentbook-codex-pilot-v1"
VALID_ARMS = {"control", "treatment"}
VALID_COHORTS = {"live", "replay"}
VALID_RECALL_STATES = {"not_called", "hit", "miss", "unavailable"}


def assign_arm(incident_id: str, experiment_seed: str) -> str:
    """Assign one incident deterministically to a 50/50 experimental arm."""

    digest = hashlib.blake2b(
        f"{experiment_seed}:{incident_id}".encode(), digest_size=8
    ).digest()
    return "treatment" if int.from_bytes(digest, "big") % 2 else "control"


def _hash_private(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _validate_recall_state(name: str, value: str) -> None:
    if value not in VALID_RECALL_STATES:
        raise ValueError(f"{name} must be one of {sorted(VALID_RECALL_STATES)}")


class PilotLedger:
    """Append-only local experiment ledger; public payloads are already redacted."""

    def __init__(
        self,
        path: Path = DEFAULT_LEDGER,
        *,
        experiment_seed: str = DEFAULT_EXPERIMENT_SEED,
    ) -> None:
        self.path = Path(path).expanduser()
        self.experiment_seed = experiment_seed

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        events = []
        for line_number, line in enumerate(self.path.read_text().splitlines(), 1):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid ledger JSON on line {line_number}") from exc
        return events

    def _append(self, event: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = (
            json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
        descriptor = os.open(
            self.path,
            os.O_APPEND | os.O_CREAT | os.O_WRONLY,
            0o600,
        )
        try:
            os.write(descriptor, payload)
        finally:
            os.close(descriptor)
        self.path.chmod(0o600)

    def start(
        self,
        *,
        error: str,
        repository: str,
        dependencies: Sequence[str] = (),
        private_terms: Sequence[str] = (),
        incident_id: str | None = None,
        cohort: str = "live",
        pair_id: str | None = None,
        arm: str | None = None,
    ) -> dict[str, Any]:
        """Start an incident before the first substantive fix attempt."""

        if cohort not in VALID_COHORTS:
            raise ValueError(f"cohort must be one of {sorted(VALID_COHORTS)}")
        if arm is not None and arm not in VALID_ARMS:
            raise ValueError(f"arm must be one of {sorted(VALID_ARMS)}")
        if cohort == "replay" and (pair_id is None or arm is None):
            raise ValueError("replay incidents require pair_id and an explicit arm")
        incident_id = incident_id or str(uuid.uuid4())
        if any(
            event.get("event") == "start" and event.get("incident_id") == incident_id
            for event in self._read()
        ):
            raise ValueError(f"incident {incident_id} already started")
        repository_path = Path(repository).expanduser().resolve()
        sanitized = sanitize_error(
            error,
            dependencies,
            private_terms=[repository_path.name, *private_terms],
        )
        assigned_arm = arm or assign_arm(incident_id, self.experiment_seed)
        event = {
            "schema_version": SCHEMA_VERSION,
            "event": "start",
            "timestamp": _timestamp(),
            "incident_id": incident_id,
            "cohort": cohort,
            "pair_id": pair_id,
            "arm": assigned_arm if sanitized.eligible else "excluded",
            "repository_id": _hash_private(str(repository_path)),
            "public_query": sanitized.public_query,
            "query_hash": _hash_private(sanitized.public_query),
            "eligible": sanitized.eligible,
            "redactions": list(sanitized.redactions),
            "block_reasons": list(sanitized.block_reasons),
        }
        self._append(event)
        return event

    def finish(
        self,
        *,
        incident_id: str,
        first_attempt_passed: bool,
        pre_attempt_recall: str,
        verification: str,
        match_quality: str | None = None,
        solution_id: str | None = None,
        crossover_recall: str = "not_called",
    ) -> dict[str, Any]:
        """Finish an incident after its predeclared first verification run."""

        _validate_recall_state("pre_attempt_recall", pre_attempt_recall)
        _validate_recall_state("crossover_recall", crossover_recall)
        events = self._read()
        start = next(
            (
                event
                for event in events
                if event.get("event") == "start"
                and event.get("incident_id") == incident_id
            ),
            None,
        )
        if start is None:
            raise ValueError(f"incident {incident_id} was not started")
        if any(
            event.get("event") == "finish" and event.get("incident_id") == incident_id
            for event in events
        ):
            raise ValueError(f"incident {incident_id} already finished")
        event = {
            "schema_version": SCHEMA_VERSION,
            "event": "finish",
            "timestamp": _timestamp(),
            "incident_id": incident_id,
            "first_attempt_passed": first_attempt_passed,
            "pre_attempt_recall": pre_attempt_recall,
            "crossover_recall": crossover_recall,
            "match_quality": match_quality,
            "solution_id": solution_id,
            "verification": verification,
        }
        self._append(event)
        return event

    def query_for_recall(self, incident_id: str, *, crossover: bool = False) -> str:
        """Release only an eligible query at the arm-appropriate time."""

        events = self._read()
        start = next(
            (
                event
                for event in events
                if event.get("event") == "start"
                and event.get("incident_id") == incident_id
            ),
            None,
        )
        if start is None:
            raise ValueError(f"incident {incident_id} was not started")
        if not start.get("eligible") or not start.get("public_query"):
            raise ValueError(f"incident {incident_id} is not eligible for recall")
        if start["arm"] == "treatment":
            return start["public_query"]
        finish = next(
            (
                event
                for event in events
                if event.get("event") == "finish"
                and event.get("incident_id") == incident_id
            ),
            None,
        )
        if not crossover or finish is None or finish["first_attempt_passed"]:
            raise ValueError("control arm cannot recall before a failed first attempt")
        return start["public_query"]


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _arm_metrics(
    starts: Sequence[dict[str, Any]], finishes: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for arm in sorted(VALID_ARMS):
        incident_ids = [item["incident_id"] for item in starts if item["arm"] == arm]
        completed = [finishes[item] for item in incident_ids if item in finishes]
        passed = sum(item["first_attempt_passed"] for item in completed)
        metrics[arm] = {
            "started": len(incident_ids),
            "completed": len(completed),
            "passed": passed,
            "pass_rate": _rate(passed, len(completed)),
        }
    return metrics


def _replay_metrics(
    starts: Sequence[dict[str, Any]], finishes: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    pairs: dict[str, dict[str, bool]] = {}
    for start in starts:
        pair_id = start.get("pair_id")
        finish = finishes.get(start["incident_id"])
        if pair_id and finish:
            pairs.setdefault(pair_id, {})[start["arm"]] = finish["first_attempt_passed"]
    completed_pairs = [pair for pair in pairs.values() if set(pair) == VALID_ARMS]
    control_passed = sum(pair["control"] for pair in completed_pairs)
    treatment_passed = sum(pair["treatment"] for pair in completed_pairs)
    paired_lift = sum(
        not pair["control"] and pair["treatment"] for pair in completed_pairs
    )
    paired_harm = sum(
        pair["control"] and not pair["treatment"] for pair in completed_pairs
    )
    paired_n = len(completed_pairs)
    return {
        "paired_n": paired_n,
        "control_passed": control_passed,
        "treatment_passed": treatment_passed,
        "control_pass_rate": _rate(control_passed, paired_n),
        "treatment_pass_rate": _rate(treatment_passed, paired_n),
        "pass_rate_delta": round(
            _rate(treatment_passed, paired_n) - _rate(control_passed, paired_n),
            4,
        ),
        "paired_lift": paired_lift,
        "paired_harm": paired_harm,
        "net_paired_lift": paired_lift - paired_harm,
    }


def _live_metrics(
    starts: Sequence[dict[str, Any]], finishes: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    completed = sum(item["incident_id"] in finishes for item in starts)
    treatment_finishes = [
        finishes[item["incident_id"]]
        for item in starts
        if item["arm"] == "treatment" and item["incident_id"] in finishes
    ]
    treatment_hits = sum(
        item["pre_attempt_recall"] == "hit" for item in treatment_finishes
    )
    return {
        "started": len(starts),
        "completed": completed,
        "completion_rate": _rate(completed, len(starts)),
        "treatment_recall_hits": treatment_hits,
        "treatment_recall_hit_rate": _rate(treatment_hits, len(treatment_finishes)),
        "arms": _arm_metrics(starts, finishes),
    }


def _gate_result(live: dict[str, Any], replay: dict[str, Any]) -> tuple[str, list[str]]:
    checks = (
        (live["completed"] < 20, "live_completed<20"),
        (live["completion_rate"] < 0.9, "live_completion_rate<0.90"),
        (replay["paired_n"] < 20, "replay_pairs<20"),
        (replay["pass_rate_delta"] < 0.15, "replay_delta<0.15"),
        (replay["net_paired_lift"] < 3, "paired_net_lift<3"),
        (replay["paired_harm"] > 0, "paired_harm>0"),
    )
    unmet = [label for failed, label in checks if failed]
    if live["completed"] < 20 or replay["paired_n"] < 20:
        return "collecting", unmet
    if replay["paired_harm"]:
        return "fail_harm", unmet
    return ("fail_no_lift" if unmet else "pass"), unmet


def summarize(path: Path = DEFAULT_LEDGER) -> dict[str, Any]:
    """Calculate the precommitted two-week pilot gates from one ledger."""

    ledger = PilotLedger(path)
    events = ledger._read()
    starts = {
        event["incident_id"]: event
        for event in events
        if event.get("event") == "start" and event.get("eligible")
    }
    finishes = {
        event["incident_id"]: event
        for event in events
        if event.get("event") == "finish"
    }
    live_starts = [event for event in starts.values() if event["cohort"] == "live"]
    live = _live_metrics(live_starts, finishes)
    replay_starts = [event for event in starts.values() if event["cohort"] == "replay"]
    replay = _replay_metrics(replay_starts, finishes)
    status, unmet = _gate_result(live, replay)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "unmet_gates": unmet,
        "live": live,
        "replay": replay,
    }
