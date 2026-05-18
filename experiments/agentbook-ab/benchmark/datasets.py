"""Catalog of external benchmark datasets (see DATASETS.md)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DatasetTier(str, Enum):
    RESOLUTION = "resolution"
    CONTEXT = "context"
    OTHER = "other"


@dataclass(frozen=True)
class DatasetSpec:
    id: str
    name: str
    tier: DatasetTier
    scale: str
    languages: str
    grading: str
    agentbook_fit: str
    access: str
    in_use: bool = False


REGISTRY: tuple[DatasetSpec, ...] = (
    DatasetSpec(
        "swe-bench-verified",
        "SWE-bench Verified",
        DatasetTier.RESOLUTION,
        "500",
        "mostly Python",
        "FAIL_TO_PASS pytest",
        "Primary fix substrate; sympy 54 RED-local",
        "HF: SWE-bench/SWE-bench_Verified",
        in_use=True,
    ),
    DatasetSpec(
        "swe-bench-full",
        "SWE-bench Full",
        DatasetTier.RESOLUTION,
        "2294",
        "Python",
        "Docker harness",
        "Same shape; needs Docker",
        "swebench + HF",
    ),
    DatasetSpec(
        "swe-bench-live",
        "SWE-bench-Live",
        DatasetTier.RESOLUTION,
        "+50/mo",
        "multi",
        "fresh issues",
        "Anti-contamination longitudinal eval",
        "github.com/microsoft/SWE-bench-Live",
    ),
    DatasetSpec(
        "swe-bench-pro",
        "SWE-Bench Pro",
        DatasetTier.RESOLUTION,
        "1865",
        "multi",
        "long-horizon",
        "Harder enterprise tasks",
        "separate release",
    ),
    DatasetSpec(
        "swe-rebench-v2",
        "SWE-rebench V2",
        DatasetTier.RESOLUTION,
        "32k+",
        "20 langs",
        "automated",
        "Scale + multilingual",
        "arxiv 2602.23866",
    ),
    DatasetSpec(
        "contextbench",
        "ContextBench",
        DatasetTier.CONTEXT,
        "1136",
        "8 langs",
        "context recall/precision",
        "Best for hint retrieval metrics",
        "contextbench.github.io",
    ),
    DatasetSpec(
        "swe-contextbench",
        "SWE-ContextBench",
        DatasetTier.CONTEXT,
        "1100+376",
        "9 langs",
        "related-issue reuse",
        "Sequential agentbook sessions",
        "arxiv 2602.08316",
    ),
    DatasetSpec(
        "swe-bench-cl",
        "SWE-Bench-CL",
        DatasetTier.CONTEXT,
        "Verified streams",
        "Python",
        "continual learning",
        "Memory stability over time",
        "arxiv 2507.00014",
    ),
    DatasetSpec(
        "swe-atlas",
        "SWE Atlas",
        DatasetTier.OTHER,
        "284",
        "multi",
        "Q&A / tests / refactor",
        "Out of scope for fix A/B",
        "arxiv 2605.08366",
    ),
)


def print_survey() -> None:
    print("Agentbook A/B — benchmark dataset survey\n")
    for tier in DatasetTier:
        rows = [d for d in REGISTRY if d.tier == tier]
        if not rows:
            continue
        print(f"## {tier.value}\n")
        for d in rows:
            mark = " [IN USE]" if d.in_use else ""
            print(f"  {d.id:22s} {d.name}{mark}")
            print(f"    scale={d.scale}  langs={d.languages}  fit={d.agentbook_fit}")
            print(f"    access: {d.access}\n")
    print("Full write-up: experiments/agentbook-ab/DATASETS.md")
