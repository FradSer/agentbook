"""Enumerate cell-samples: (instance_id, arm, model, sample_idx)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.panel import model_slug  # noqa: E402
from harness.sandbox import RUNS_V2, cell_dirname  # noqa: E402


@dataclass(frozen=True)
class Cell:
    iid: str
    arm: str
    model: str
    sample_idx: int

    @property
    def model_slug(self) -> str:
        return model_slug(self.model)

    @property
    def dirname(self) -> str:
        return cell_dirname(self.iid, self.arm, self.model_slug, self.sample_idx)

    @property
    def run_dir(self) -> Path:
        return RUNS_V2 / self.dirname

    @property
    def result_path(self) -> Path:
        return self.run_dir / "result.json"

    def is_fresh(self) -> bool:
        return self.result_path.is_file()


def enumerate_cells(
    instance_ids: list[str], arms: list[str], models: list[str], k: int
) -> list[Cell]:
    cells: list[Cell] = []
    for iid in instance_ids:
        for arm in arms:
            for model in models:
                for s in range(k):
                    cells.append(Cell(iid=iid, arm=arm, model=model, sample_idx=s))
    return cells
