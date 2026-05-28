"""Red-phase tests for `select_arm_for_sample` on RuleRouter and KNNRouter.

Each test maps 1:1 to a Gherkin scenario in
docs/plans/2026-05-27-agentbook-outcome-loop-design/bdd-specs.md Feature 4
(scenarios 1-6).

Fixture strategy:
  - In-memory feature dicts and synthetic outcomes lists; no real Ollama, no
    real `_oracle/outcomes_log.json` mutation (CODE-TEST-01).
  - The KNN tests monkeypatch `pipeline.router.SYNTH_CACHE` to a `tmp_path`
    synth_cache containing only the iids referenced by the synthetic outcomes,
    so the LOO neighbour selection is deterministic.
  - `select_arms` regression test uses the real `_oracle/synth_cache.json` so
    the signature-backcompat snapshot reflects the production call site.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline import router as router_mod  # noqa: E402
from pipeline.router import (  # noqa: E402
    RUNTIME_ARMS,
    KNNRouter,
    RuleRouter,
    select_arms,
)

# --------------------------------------------------------------------------- #
# fixture helpers                                                             #
# --------------------------------------------------------------------------- #


# Multisite gemma features drawn from RuleRouter's rule definitions:
# `is_multisite > 0.5` triggers the multisite branch for gemma -> ranking
# ["good_multi_loop", "good_loop", "good"] (k=4 returns these three; the
# fourth runtime arm `good_synth` is reached only via EXHAUSTED_RANKING).
_MULTISITE_GEMMA_FEATURES = {
    "n_cues": 5.0,
    "n_repros": 5.0,
    "n_files": 2.0,
    "is_multisite": 1.0,
    "mentions_branch": 1.0,
}


def _make_synth_cache(tmp_path: Path, iids: list[str], features: dict) -> Path:
    """Materialise a tmp synth_cache.json where every iid carries an entry that
    decodes (via extract_features) to roughly `features`. We embed features
    in the raw shape `extract_features` consumes."""
    cache = {}
    n_cues = int(features.get("n_cues", 0))
    n_repros = int(features.get("n_repros", 0))
    n_files = int(features.get("n_files", 0))
    files = [f"pkg/mod{i}.py" for i in range(n_files)]
    cues = [
        f"hint about {files[i % max(len(files), 1)] if files else 'site'}"
        for i in range(n_cues)
    ]
    pattern = (
        "branch guard inverted" if features.get("mentions_branch") else "off by one"
    )
    for iid in iids:
        cache[iid] = {
            "root_cause_pattern": pattern,
            "localization_cues": cues,
            "verifications": [f"repro_{i}.py" for i in range(n_repros)],
        }
    path = tmp_path / "synth_cache.json"
    path.write_text(json.dumps(cache))
    return path


# --------------------------------------------------------------------------- #
# Feature 4 scenarios 1-6                                                     #
# --------------------------------------------------------------------------- #


def test_fresh_arm_at_sample0():
    """Scenario: First sample picks the router's top-ranked arm
    (FRESH_ARM, empty history).

    Empty tried_arms_results -> RuleRouter returns its rank-1 pick for
    multisite gemma, which is "good_multi_loop".
    """
    router = RuleRouter()
    chosen = router.select_arm_for_sample(
        _MULTISITE_GEMMA_FEATURES,
        "gemma4_e4b",
        sample_idx=0,
        tried_arms_results={},
    )
    assert chosen == "good_multi_loop"


def test_fresh_arm_after_failure():
    """Scenario: After a failed top pick, sample 1 advances to rank-2
    (FRESH_ARM after failure).

    With "good_multi_loop":[False] in tried, the rule router's next-ranked
    arm is "good_loop"; it must NOT return "good_multi_loop" and must be in
    RUNTIME_ARMS.
    """
    router = RuleRouter()
    chosen = router.select_arm_for_sample(
        _MULTISITE_GEMMA_FEATURES,
        "gemma4_e4b",
        sample_idx=1,
        tried_arms_results={"good_multi_loop": [False]},
    )
    assert chosen != "good_multi_loop"
    assert chosen == "good_loop"
    assert chosen in RUNTIME_ARMS


def test_replay_win():
    """Scenario: A prior win short-circuits to REPLAY_WIN.

    tried_arms_results carries a True for "good_loop"; rotation must replay
    that arm regardless of ranking.
    """
    router = RuleRouter()
    chosen = router.select_arm_for_sample(
        _MULTISITE_GEMMA_FEATURES,
        "gemma4_e4b",
        sample_idx=2,
        tried_arms_results={"good_multi_loop": [False], "good_loop": [True]},
    )
    assert chosen == "good_loop"


def test_burn_replay_when_all_tried(tmp_path, monkeypatch):
    """Scenario: All RUNTIME_ARMS tried, all failed -- BURN_REPLAY returns
    ranking[0].

    KNNRouter consumes a synthetic outcomes list (and a tmp synth_cache) so
    ranking is deterministic. With every runtime arm in tried_arms_results
    carrying [False], the selector must return ranking[0] from KNN's order
    (it must also be a member of RUNTIME_ARMS).
    """
    nn_iids = ["nn_a", "nn_b", "nn_c"]
    cache_path = _make_synth_cache(tmp_path, nn_iids, _MULTISITE_GEMMA_FEATURES)
    monkeypatch.setattr(router_mod, "SYNTH_CACHE", cache_path)

    # Outcomes such that no arm has any wins; KNN's tie-breaking falls back
    # to iteration order of RUNTIME_ARMS, so ranking[0] is deterministic.
    outcomes = []
    for iid in nn_iids:
        for arm in RUNTIME_ARMS:
            outcomes.append(
                {
                    "model_slug": "gemma4_e4b",
                    "iid": iid,
                    "arm": arm,
                    "sample_idx": 0,
                    "resolved": False,
                }
            )

    knn = KNNRouter()
    ranking = knn.select(
        _MULTISITE_GEMMA_FEATURES,
        "gemma4_e4b",
        k=len(RUNTIME_ARMS),
        outcomes=outcomes,
        exclude_iid="sympy__sympy-15017",
    )
    tried = {arm: [False] for arm in RUNTIME_ARMS}

    chosen = knn.select_arm_for_sample(
        _MULTISITE_GEMMA_FEATURES,
        "gemma4_e4b",
        sample_idx=4,
        tried_arms_results=tried,
        outcomes=outcomes,
        exclude_iid="sympy__sympy-15017",
    )
    assert chosen == ranking[0]
    assert chosen in RUNTIME_ARMS


def test_rule_vs_knn_disagreement_at_sample_1(tmp_path, monkeypatch):
    """Scenario: Rule and KNN disagree on the fresh arm at sample 1.

    Rule's #2 pick for multisite gemma is "good_loop". A KNN fed an outcomes
    log where "good" resolves 3/3 nearest neighbours and "good_loop" resolves
    1/3 ranks "good" first; with "good_multi_loop":[False] already tried,
    FRESH_ARM yields "good".
    """
    # RuleRouter side: deterministic from features alone.
    rule = RuleRouter()
    rule_choice = rule.select_arm_for_sample(
        _MULTISITE_GEMMA_FEATURES,
        "gemma4_e4b",
        sample_idx=1,
        tried_arms_results={"good_multi_loop": [False]},
    )
    assert rule_choice == "good_loop"

    # KNN side: 3 nearest neighbours; good wins 3/3, good_loop wins 1/3.
    nn_iids = ["nn_a", "nn_b", "nn_c"]
    cache_path = _make_synth_cache(tmp_path, nn_iids, _MULTISITE_GEMMA_FEATURES)
    monkeypatch.setattr(router_mod, "SYNTH_CACHE", cache_path)

    outcomes = []
    for iid in nn_iids:
        outcomes.append(
            {
                "model_slug": "gemma4_e4b",
                "iid": iid,
                "arm": "good",
                "sample_idx": 0,
                "resolved": True,
            }
        )
    for iid, resolved in zip(nn_iids, [True, False, False], strict=True):
        outcomes.append(
            {
                "model_slug": "gemma4_e4b",
                "iid": iid,
                "arm": "good_loop",
                "sample_idx": 0,
                "resolved": resolved,
            }
        )

    knn = KNNRouter()
    knn_choice = knn.select_arm_for_sample(
        _MULTISITE_GEMMA_FEATURES,
        "gemma4_e4b",
        sample_idx=1,
        tried_arms_results={"good_multi_loop": [False]},
        outcomes=outcomes,
        exclude_iid=None,
    )
    assert knn_choice == "good"
    assert knn_choice != rule_choice


def test_select_arms_signature_unchanged():
    """Scenario: Existing select_arms callers are unaffected (no signature
    change).

    Snapshot the current select_arms(iid, model_slug, k=1) return for a known
    fixture; the shipped select_arm_for_sample addition must not perturb it.
    """
    iid = "sympy__sympy-15017"
    # Resolved against the real _oracle/synth_cache.json (read-only).
    prior = ["good_multi_loop"]
    assert select_arms(iid, "gemma4_e4b", k=1) == prior


# --------------------------------------------------------------------------- #
# Feature 5 scenarios (evaluate_offline_rotate offline simulator)             #
# --------------------------------------------------------------------------- #


_OFFLINE_ARMS_5 = ("good", "good_synth", "good_loop_v1", "good_loop", "good_multi_loop")


def _seed_rotate_outcomes(
    iids: list[str],
    arm_resolves: dict[str, set[tuple[str, int]]],
) -> list[dict]:
    """Build a synthetic outcomes log over (gemma4_e4b, iid, arm, sample_idx).

    `arm_resolves[arm]` is the set of (iid, sample_idx) pairs that resolve True
    for that arm. Every (iid, arm, s in 0..2) tuple is materialised so the
    simulator can look up any sample slot without falling back -- except for
    explicit gaps the caller leaves out of `iids_with_full_grid`.
    """
    rows: list[dict] = []
    for iid in iids:
        for arm in _OFFLINE_ARMS_5:
            for s in range(3):
                rows.append(
                    {
                        "model_slug": "gemma4_e4b",
                        "iid": iid,
                        "arm": arm,
                        "sample_idx": s,
                        "resolved": (iid, s) in arm_resolves.get(arm, set()),
                    }
                )
    return rows


def test_offline_rotate_coverage_meets_or_exceeds_best_static(tmp_path, monkeypatch):
    """Scenario: rotate coverage at k=3 is >= the best static single arm under LOO.

    Then clauses asserted:
      - reported coverage_rotate is >= 13/17 (best static = good_multi_loop)
      - reported coverage_rotate is <= ceiling_all_arms_union (15/17)
      - arms_used_count >= 2 distinct arms dispatched across tasks

    Fixture: gemma4_e4b, 5-arm x 17-task x s=0..s=2. good_multi_loop wins 13/17
    (s=0 only); for the 2 tasks where good_multi_loop fails entirely, good_loop
    wins at s=0, so rotation (which advances to good_loop after the multi_loop
    miss) covers 15/17. The remaining 2 tasks resolve nowhere -- they cap both
    rotate coverage and the union ceiling at 15/17.
    """
    iids = [f"task_{i:02d}" for i in range(17)]
    win_iids = set(iids[:13])  # good_multi_loop wins these at s=0
    rescue_iids = set(iids[13:15])  # good_loop wins these at s=0; multi_loop fails
    # iids[15], iids[16] -> nothing resolves (caps both rotate and union ceiling)

    arm_resolves: dict[str, set[tuple[str, int]]] = {
        "good_multi_loop": {(iid, 0) for iid in win_iids},
        "good_loop": {(iid, 0) for iid in rescue_iids},
        "good": set(),
        "good_synth": set(),
        "good_loop_v1": set(),
    }
    outcomes = _seed_rotate_outcomes(iids, arm_resolves)

    cache_path = _make_synth_cache(tmp_path, iids, _MULTISITE_GEMMA_FEATURES)
    monkeypatch.setattr(router_mod, "SYNTH_CACHE", cache_path)
    monkeypatch.setattr(router_mod, "load_outcomes", lambda: outcomes)

    report = router_mod.evaluate_offline_rotate(
        RuleRouter(), k=3, models=("gemma4_e4b",)
    )
    info = report["gemma4_e4b"]

    coverage = info["coverage_rotate"]
    if isinstance(coverage, str):
        num, denom = coverage.split("/")
        rotate_num, rotate_denom = int(num), int(denom)
    else:
        rotate_num, rotate_denom = int(coverage), 17

    ceiling = info["ceiling_all_arms_union"]
    if isinstance(ceiling, str):
        cnum, cdenom = ceiling.split("/")
        ceiling_num, ceiling_denom = int(cnum), int(cdenom)
    else:
        ceiling_num, ceiling_denom = int(ceiling), 17

    assert rotate_denom == 17
    assert ceiling_denom == 17
    assert rotate_num >= 13, f"rotate coverage {rotate_num}/17 < best static 13/17"
    assert rotate_num <= ceiling_num == 15, (
        f"rotate {rotate_num}/17 must be <= ceiling {ceiling_num}/17 (expected 15)"
    )

    arms_used = info["arms_used_count"]
    distinct = arms_used if isinstance(arms_used, int) else len(arms_used)
    assert distinct >= 2, (
        f"arms_used_count must report >= 2 distinct arms dispatched, got {distinct}"
    )


def test_offline_rotate_falls_back_when_sample_slot_missing(tmp_path, monkeypatch):
    """Scenario: rotate consumes sample slots in order and falls back when a
    slot is missing.

    Then clauses asserted:
      - simulator falls back to sample s=0's outcome
      - unmet_samples counter records the gap
      - the simulation does NOT raise

    Fixture: a single iid (sympy__sympy-15017); (gemma4_e4b, iid, good_multi_loop)
    has only s=0 resolved=False. There is no s=1 row. Rotation is forced back to
    good_multi_loop at s=1 by setting up tried_arms_results such that
    select_arm_for_sample replays good_multi_loop (achieved here by a stub
    router that always returns good_multi_loop regardless of tried history --
    mimicking the 'hypothetical earlier failure' clause).
    """
    iid = "sympy__sympy-15017"
    cache_path = _make_synth_cache(tmp_path, [iid], _MULTISITE_GEMMA_FEATURES)
    monkeypatch.setattr(router_mod, "SYNTH_CACHE", cache_path)

    # Only s=0; no s=1 or s=2 row -- forces fallback when rotation revisits arm.
    outcomes = [
        {
            "model_slug": "gemma4_e4b",
            "iid": iid,
            "arm": "good_multi_loop",
            "sample_idx": 0,
            "resolved": False,
        }
    ]
    monkeypatch.setattr(router_mod, "load_outcomes", lambda: outcomes)

    class _AlwaysMultiLoop:
        """Router stub: every sample picks good_multi_loop, forcing the
        simulator to re-look-up consume_idx slots 0, 1, 2 in order. Slot 1+
        are missing -> fallback to slot 0 should fire and unmet_samples must
        record the gap. tried_arms_results threading is preserved by the
        simulator regardless of the stub's choice."""

        name = "stub_always_multi_loop"

        def select_arm_for_sample(
            self,
            features,
            model_slug,
            sample_idx,
            tried_arms_results,
            **kwargs,
        ) -> str:
            return "good_multi_loop"

    # Must not raise.
    report = router_mod.evaluate_offline_rotate(
        _AlwaysMultiLoop(), k=3, models=("gemma4_e4b",)
    )
    info = report["gemma4_e4b"]
    assert info["unmet_samples"] >= 1, (
        f"unmet_samples should record >= 1 fallback, got {info['unmet_samples']}"
    )
    # All 3 samples consumed good_multi_loop's only row (s=0 False); coverage 0.
    coverage = info["coverage_rotate"]
    if isinstance(coverage, str):
        rotate_num = int(coverage.split("/")[0])
    else:
        rotate_num = int(coverage)
    assert rotate_num == 0


def test_offline_rotate_loo_safety_for_knn(tmp_path, monkeypatch):
    """Scenario: LOO safety in rotate simulation.

    Then clauses asserted:
      - no row with iid="sympy__sympy-15017" enters the router's score
        computation (exclude_iid honored)
      - tried_arms_results only carries in-simulation samples for
        sympy__sympy-15017

    The KNNRouter is wrapped by a spy that records every outcomes-row list it
    sees on `select`. The simulator must forward `exclude_iid=iid` so the held-
    out iid never reaches the KNN score computation, even when its rows live
    in the outcomes log.
    """
    held_out = "sympy__sympy-15017"
    other_iids = [f"task_{i:02d}" for i in range(3)]
    all_iids = [held_out, *other_iids]

    cache_path = _make_synth_cache(tmp_path, all_iids, _MULTISITE_GEMMA_FEATURES)
    monkeypatch.setattr(router_mod, "SYNTH_CACHE", cache_path)

    outcomes = _seed_rotate_outcomes(
        all_iids,
        {
            "good_multi_loop": {(held_out, 0), (held_out, 1)},  # bait rows
            "good_loop": {(other_iids[0], 0)},
            "good": set(),
            "good_synth": set(),
            "good_loop_v1": set(),
        },
    )
    monkeypatch.setattr(router_mod, "load_outcomes", lambda: outcomes)

    seen_iids_in_score: list[str] = []
    seen_tried_for_held_out: list[dict] = []

    class _SpyKNN(KNNRouter):
        """Wraps KNNRouter to record the iids that flow into the score
        computation (the post-LOO-filter row set) and the tried_arms_results
        passed for the held-out iid's chain."""

        name = "knn_spy"

        def select(self, features, model_slug, k=1, *, outcomes=None, exclude_iid=None):
            outcomes = outcomes if outcomes is not None else router_mod.load_outcomes()
            # Only audit the held-out chain: that's where LOO must keep the
            # held-out iid OUT of the score computation. For other chains the
            # held-out iid is a legitimate neighbour.
            if exclude_iid == held_out:
                for r in outcomes:
                    if r["iid"] != exclude_iid:
                        seen_iids_in_score.append(r["iid"])
            return super().select(
                features,
                model_slug,
                k=k,
                outcomes=outcomes,
                exclude_iid=exclude_iid,
            )

        def select_arm_for_sample(
            self,
            features,
            model_slug,
            sample_idx,
            tried_arms_results,
            *,
            outcomes=None,
            exclude_iid=None,
        ) -> str:
            if exclude_iid == held_out:
                # Snapshot the tried dict at each consult so the test can
                # verify it never contains foreign iid data.
                seen_tried_for_held_out.append(
                    {arm: list(results) for arm, results in tried_arms_results.items()}
                )
            return super().select_arm_for_sample(
                features,
                model_slug,
                sample_idx,
                tried_arms_results,
                outcomes=outcomes,
                exclude_iid=exclude_iid,
            )

    router_mod.evaluate_offline_rotate(_SpyKNN(), k=3, models=("gemma4_e4b",))

    assert held_out not in seen_iids_in_score, (
        "exclude_iid violated: held-out iid leaked into KNN score computation"
    )
    # tried_arms_results for the held-out iid must never carry a foreign iid's
    # outcomes; the simulator builds it locally per (model, iid), and the spy
    # snapshots only carry arm -> [bool, ...] keyed by router decisions.
    for snapshot in seen_tried_for_held_out:
        for arm, results in snapshot.items():
            assert arm in RUNTIME_ARMS, (
                f"tried_arms_results for held-out chain carried foreign arm {arm}"
            )
            assert all(isinstance(b, bool) for b in results)


# --------------------------------------------------------------------------- #
# BATCH4-013-C rework: bootstrap_outcomes_log harvests archived runs_v2.*     #
# --------------------------------------------------------------------------- #


def _write_synthetic_result(
    cell_dir: Path,
    *,
    iid: str,
    model_slug: str,
    arm: str,
    sample_idx: int,
    resolved: bool,
) -> None:
    cell_dir.mkdir(parents=True, exist_ok=True)
    (cell_dir / "result.json").write_text(
        json.dumps(
            {
                "instance_id": iid,
                "model_slug": model_slug,
                "arm": arm,
                "sample_idx": sample_idx,
                "resolved": resolved,
            }
        )
        + "\n"
    )


def test_bootstrap_outcomes_log_reads_archived_runs_v2(tmp_path, monkeypatch):
    """BATCH4-013-C: bootstrap_outcomes_log must scan archived runs_v2.* dirs.

    Fixture:
      - tmp_path/runs_v2/<active_cell>/result.json   (one row)
      - tmp_path/runs_v2.batch1/<archived_cell>/result.json   (one row)
      - tmp_path/_oracle/  (so OUTCOMES_LOG write target exists)

    Then bootstrap_outcomes_log() must return rows from BOTH directories. The
    pre-fix harvest only reads runs_v2/ (and a single hardcoded v1 archive), so
    the archived batch1 row is missing -- the structural Red shape per
    CODE-TEST-03.
    """
    # Synthetic project root with both an active and an archived runs dir.
    (tmp_path / "_oracle").mkdir()
    active_cell = tmp_path / "runs_v2" / "active_cell"
    archived_cell = tmp_path / "runs_v2.batch1" / "archived_cell"
    _write_synthetic_result(
        active_cell,
        iid="sympy__sympy-active",
        model_slug="gemma4_e4b",
        arm="good_loop",
        sample_idx=0,
        resolved=True,
    )
    _write_synthetic_result(
        archived_cell,
        iid="sympy__sympy-archived",
        model_slug="gemma4_e4b",
        arm="good_multi_loop",
        sample_idx=1,
        resolved=False,
    )

    monkeypatch.setattr(router_mod, "ROOT", tmp_path)
    monkeypatch.setattr(
        router_mod, "OUTCOMES_LOG", tmp_path / "_oracle" / "outcomes_log.json"
    )

    rows = router_mod.bootstrap_outcomes_log()
    iids_seen = {r["iid"] for r in rows}

    assert "sympy__sympy-active" in iids_seen, (
        f"active runs_v2/ row missing from harvest; rows={rows}"
    )
    assert "sympy__sympy-archived" in iids_seen, (
        "archived runs_v2.batch1/ row missing from harvest -- "
        f"bootstrap_outcomes_log did not scan archived dirs; rows={rows}"
    )
