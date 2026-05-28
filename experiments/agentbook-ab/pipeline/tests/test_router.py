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
