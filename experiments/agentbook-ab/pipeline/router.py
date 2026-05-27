"""arm-router: pick (and optionally ensemble) the agentbook recall arm(s) most
likely to land a fix for a given (task, model) pair, and improve over time as
outcomes accumulate -- the production-shaped form of the multi-arm result.

Three policies share one API:

    select_arms(iid, model_slug, k=1) -> list[arm]

  - RuleRouter   : deterministic hand-coded rules from the observed
                   per-model+per-feature win patterns. No training data.
  - KNNRouter    : K-nearest-neighbour over task feature vectors using the
                   accumulated outcomes log. Leave-one-out safe for evaluation.
  - TopKEnsemble : returns the K arms with highest predicted P(resolve), so the
                   runtime can run them in parallel and union the wins.

Outcomes are persisted to `_oracle/outcomes_log.json` as
`{model_slug, iid, arm, resolved}` rows -- agentbook's `report` MCP tool would
feed this in production. The router refits the KNN at every `select_arms` call
so the policy improves incrementally without an explicit retrain step.

Runtime arms (what good_router can actually dispatch to in the orchestrator):
`good`, `good_synth`, `good_loop` (= v2 multi-repro), `good_multi_loop`. The v1
single-repro and good_apply (same-task cache, non-target) are archived data
sources, used for offline-evaluation upper bounds but not dispatched at runtime.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from benchmark.paths import ORACLE  # noqa: E402

SYNTH_CACHE = ORACLE / "synth_cache.json"
OUTCOMES_LOG = ORACLE / "outcomes_log.json"

# Arms a runtime good_router may actually dispatch to (no patch cache).
RUNTIME_ARMS: tuple[str, ...] = ("good", "good_synth", "good_loop", "good_multi_loop")
# Arms the offline evaluator may consider (incl. the v1 archive as a historical
# data point; v1 isn't a runtime arm but its outcomes inform feature->arm fit).
OFFLINE_ARMS: tuple[str, ...] = (
    "good",
    "good_synth",
    "good_loop_v1",
    "good_loop",
    "good_multi_loop",
)

_FILE_RE = re.compile(r"[\w/]+\.py")


# ----------------------------- features ------------------------------------


def extract_features(entry: dict) -> dict[str, float]:
    """Per-task features from a synth_cache entry. All numeric so feat_dist is
    well-defined. Kept tiny (n=17) and interpretable so a hand-rule and KNN both
    work on the same vector without overfitting."""
    cues = entry.get("localization_cues") or []
    repros = entry.get("verifications") or []
    cue_text = " ".join(cues)
    pattern = entry.get("root_cause_pattern", "") or ""
    files = set(_FILE_RE.findall(cue_text))
    return {
        "n_cues": float(len(cues)),
        "n_repros": float(len(repros)),
        "n_files": float(len(files)),
        "is_multisite": 1.0 if (len(files) >= 2 or len(repros) >= 4) else 0.0,
        "mentions_branch": 1.0
        if any(k in pattern.lower() for k in (" if ", "branch", "elif", "guard"))
        else 0.0,
    }


_FEATURE_KEYS = ("n_cues", "n_repros", "n_files", "is_multisite", "mentions_branch")
# Scales chosen so each feature contributes O(1) to the distance.
_FEATURE_SCALE = {"n_cues": 2.0, "n_repros": 2.0, "n_files": 1.5}


def feat_dist(a: dict[str, float], b: dict[str, float]) -> float:
    """Weighted L2 over the small feature set."""
    s = 0.0
    for k in _FEATURE_KEYS:
        s += ((a.get(k, 0.0) - b.get(k, 0.0)) / _FEATURE_SCALE.get(k, 1.0)) ** 2
    return math.sqrt(s)


# ----------------------------- outcomes ------------------------------------


def _harvest_runs(runs_dir: Path, arm_label: str | None = None) -> list[dict]:
    """Scan a runs dir for result.json files and emit outcome rows.

    `arm_label` overrides the result's arm field (used to label the v1 archive
    as `good_loop_v1` since its on-disk arm name was `good_loop` at the time)."""
    rows: list[dict] = []
    for f in sorted(runs_dir.glob("*/result.json")):
        try:
            r = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        if not r.get("model_slug") or not r.get("instance_id"):
            continue
        # Keep every attempted cell (incl. parse_failures / unsubmitted) -- an
        # arm that didn't produce an edit is still useful negative signal for
        # the router's per-(model, features) -> arm fit.
        rows.append(
            {
                "model_slug": r.get("model_slug"),
                "iid": r.get("instance_id"),
                "arm": arm_label or r.get("arm"),
                "sample_idx": int(r.get("sample_idx", 0)),
                "resolved": bool(r.get("resolved")),
            }
        )
    return rows


def bootstrap_outcomes_log() -> list[dict]:
    """Build the initial outcomes log from local runs (so the router has data
    before any production outcome reports land). Writes _oracle/outcomes_log.json."""
    rows = _harvest_runs(ROOT / "runs_v2")
    rows += _harvest_runs(
        ROOT / "runs_v2.good_loop_v1_single_repro", arm_label="good_loop_v1"
    )
    # de-dup by (model, iid, arm, sample_idx) so k>1 sampling is preserved and
    # the router can learn from pass-rate, not just pass@1.
    by_key = {
        (r["model_slug"], r["iid"], r["arm"], r.get("sample_idx", 0)): r for r in rows
    }
    out = sorted(
        by_key.values(),
        key=lambda r: (
            r["model_slug"] or "",
            r["iid"] or "",
            r["arm"] or "",
            r.get("sample_idx", 0),
        ),
    )
    OUTCOMES_LOG.write_text(json.dumps(out, indent=2) + "\n")
    return out


def load_outcomes() -> list[dict]:
    if OUTCOMES_LOG.exists():
        return json.loads(OUTCOMES_LOG.read_text())
    return bootstrap_outcomes_log()


def update_from_outcome(
    model_slug: str,
    iid: str,
    arm: str,
    resolved: bool,
    *,
    sample_idx: int = 0,
) -> None:
    """Production hook: append/update one (model, task, arm, sample) outcome
    row. Triggers the next select_arms() to refit on the larger sample.
    Idempotent on (model, iid, arm, sample_idx)."""
    rows = load_outcomes()
    by_key = {
        (r["model_slug"], r["iid"], r["arm"], r.get("sample_idx", 0)): r for r in rows
    }
    by_key[(model_slug, iid, arm, sample_idx)] = {
        "model_slug": model_slug,
        "iid": iid,
        "arm": arm,
        "sample_idx": int(sample_idx),
        "resolved": bool(resolved),
    }
    out = sorted(
        by_key.values(),
        key=lambda r: (
            r["model_slug"] or "",
            r["iid"] or "",
            r["arm"] or "",
            r.get("sample_idx", 0),
        ),
    )
    OUTCOMES_LOG.write_text(json.dumps(out, indent=2) + "\n")


# ----------------------------- policies ------------------------------------


class RuleRouter:
    """Deterministic rules derived from observed per-model patterns. No fit."""

    name = "rule"

    @staticmethod
    def select(features: dict, model_slug: str, k: int = 1) -> list[str]:
        is_gpt_oss = "gpt-oss" in (model_slug or "")
        multisite = features.get("is_multisite", 0.0) > 0.5
        ranked: list[str]
        if is_gpt_oss:
            # gpt-oss (reasoning, parse-failure-prone): single-repro v1 is the
            # most robust runtime production arm is good_loop (=v2); pair with
            # good_multi_loop when multi-site (it unlocked 14976/15809 there).
            ranked = (
                ["good_multi_loop", "good_loop", "good"]
                if multisite
                else ["good_loop", "good", "good_synth"]
            )
        else:
            # gemma (instruct, reliable): multi-repro and dual-view help when
            # the task is multi-site; prose `good` is a strong default otherwise.
            ranked = (
                ["good_multi_loop", "good_loop", "good"]
                if multisite
                else ["good", "good_loop", "good_synth"]
            )
        return ranked[:k]


class KNNRouter:
    """K-NN over task features using the accumulated outcomes log. For each
    candidate arm, the predicted P(resolve | model, features) is the resolution
    rate of that arm on the N nearest neighbour tasks (same model). Returns the
    top-K arms by this score."""

    name = "knn"

    def __init__(self, *, neighbours: int = 3, runtime_only: bool = True) -> None:
        self.neighbours = neighbours
        self.runtime_only = runtime_only

    def _candidate_arms(self) -> tuple[str, ...]:
        return RUNTIME_ARMS if self.runtime_only else OFFLINE_ARMS

    def _features_by_iid(self) -> dict[str, dict]:
        cache = json.loads(SYNTH_CACHE.read_text())
        return {iid: extract_features(e) for iid, e in cache.items()}

    def select(
        self,
        features: dict,
        model_slug: str,
        k: int = 1,
        *,
        outcomes: list[dict] | None = None,
        exclude_iid: str | None = None,
    ) -> list[str]:
        outcomes = outcomes or load_outcomes()
        features_by_iid = self._features_by_iid()
        # Same model + same-arm-pool only; exclude held-out iid for LOO eval.
        rows = [
            r
            for r in outcomes
            if r["model_slug"] == model_slug
            and r["arm"] in self._candidate_arms()
            and r["iid"] != exclude_iid
            and r["iid"] in features_by_iid
        ]
        # Distance from target features to every other task's features.
        iid_dist = sorted(
            {r["iid"] for r in rows},
            key=lambda iid: feat_dist(features, features_by_iid[iid]),
        )
        nearest = set(iid_dist[: self.neighbours])
        # Per-arm resolution rate over neighbour rows.
        score: dict[str, list[int]] = defaultdict(list)
        for r in rows:
            if r["iid"] in nearest:
                score[r["arm"]].append(int(r["resolved"]))
        # Fall back to global per-arm rate when an arm has no neighbour data.
        global_rate = defaultdict(list)
        for r in rows:
            global_rate[r["arm"]].append(int(r["resolved"]))
        ranked = sorted(
            self._candidate_arms(),
            key=lambda a: (
                -sum(score.get(a, [])) / max(len(score.get(a, [])), 1),
                -sum(global_rate.get(a, [])) / max(len(global_rate.get(a, [])), 1),
            ),
        )
        return ranked[:k]


# --------------------------- offline evaluation ----------------------------


def evaluate_offline(
    router,
    *,
    arms_pool: tuple[str, ...] = RUNTIME_ARMS,
    models: tuple[str, ...] = ("gpt-oss_20b", "gemma4_e4b"),
    k: int = 1,
) -> dict:
    """Leave-one-out CV on the outcomes log: for each (model, task), the router
    chooses k arms with that task EXCLUDED from training data; coverage = task
    counts as resolved if ANY chosen arm resolved it. Pure simulation, no runs."""
    outcomes = load_outcomes()
    cache = json.loads(SYNTH_CACHE.read_text())
    # pass@k semantics: (model, iid, arm) counts as resolved if ANY sample did.
    by_key: dict[tuple[str, str, str], bool] = {}
    for r in outcomes:
        key = (r["model_slug"], r["iid"], r["arm"])
        by_key[key] = by_key.get(key, False) or bool(r["resolved"])

    out: dict = {"policy": router.name, "k": k, "models": {}}
    for model in models:
        iids = sorted({r["iid"] for r in outcomes if r["model_slug"] == model})
        resolved = 0
        per_arm_used: Counter = Counter()
        misses: list[str] = []
        for iid in iids:
            if iid not in cache:
                continue
            features = extract_features(cache[iid])
            kwargs = {}
            if hasattr(router, "_features_by_iid"):
                kwargs = {"exclude_iid": iid}
            chosen = router.select(features, model, k=k, **kwargs)
            for a in chosen:
                per_arm_used[a] += 1
            hit = any(by_key.get((model, iid, a), False) for a in chosen)
            if hit:
                resolved += 1
            else:
                misses.append(iid.replace("sympy__sympy-", ""))
        # Reference points: best single static arm + all-arms union (ceiling).
        all_arms_union = sum(
            1
            for iid in iids
            if any(by_key.get((model, iid, a), False) for a in arms_pool)
        )
        per_arm_total = {
            a: sum(by_key.get((model, iid, a), False) for iid in iids)
            for a in arms_pool
        }
        best_static_arm = (
            max(per_arm_total, key=per_arm_total.get) if per_arm_total else None
        )
        best_static_count = (
            per_arm_total.get(best_static_arm, 0) if best_static_arm else 0
        )
        out["models"][model] = {
            "tasks": len(iids),
            "resolved": resolved,
            "coverage": f"{resolved}/{len(iids)}",
            "best_static_arm": best_static_arm,
            "best_static_coverage": f"{best_static_count}/{len(iids)}",
            "ceiling_all_arms_union": f"{all_arms_union}/{len(iids)}",
            "arms_used_count": dict(per_arm_used),
            "misses": sorted(misses),
        }
    return out


# --------------------------- runtime entry ---------------------------------

_ACTIVE_ROUTER = RuleRouter()


def set_router(router) -> None:
    """Swap the in-process router (e.g. to KNN once enough outcomes exist)."""
    global _ACTIVE_ROUTER
    _ACTIVE_ROUTER = router


def select_arms(iid: str, model_slug: str, k: int = 1) -> list[str]:
    """Production entry: pick k arm(s) for this (task, model). Refits on
    whatever's in the outcomes log at call time -- the self-improvement loop."""
    cache = json.loads(SYNTH_CACHE.read_text())
    if iid not in cache:
        return ["good"]
    features = extract_features(cache[iid])
    return _ACTIVE_ROUTER.select(features, model_slug, k=k)


def main() -> None:
    """CLI: offline-evaluate every policy at k=1,2 and dump a comparison table."""
    if not OUTCOMES_LOG.exists():
        bootstrap_outcomes_log()
    routers = [RuleRouter(), KNNRouter(neighbours=3)]
    print("=" * 78)
    for r in routers:
        for k in (1, 2):
            res = evaluate_offline(r, k=k)
            print(f"\npolicy={res['policy']}  k={k}")
            for m, info in res["models"].items():
                print(
                    f"  {m:14s} coverage={info['coverage']:>5s}  "
                    f"best_static={info['best_static_arm']}({info['best_static_coverage']})  "
                    f"ceiling(all_arms)={info['ceiling_all_arms_union']}  "
                    f"arms_used={info['arms_used_count']}"
                )
    print("=" * 78)


if __name__ == "__main__":
    main()
