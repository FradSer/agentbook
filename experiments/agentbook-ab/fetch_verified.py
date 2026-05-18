#!/usr/bin/env python
"""Download SWE-bench Verified from the public Hugging Face dataset.

Source: https://huggingface.co/datasets/SWE-bench/SWE-bench_Verified
License: see dataset card on Hugging Face.

Writes:
  _data/verified.parquet   — full test split (500 instances)
  _data/dataset_meta.json  — source URL, row count, column list

Run:
  uv run --with datasets --with pandas --with pyarrow \
    python experiments/agentbook-ab/fetch_verified.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "_data"
OUT = DATA / "verified.parquet"
META = DATA / "dataset_meta.json"
HF_DATASET = "SWE-bench/SWE-bench_Verified"
HF_SPLIT = "test"


def main() -> None:
    from datasets import load_dataset

    DATA.mkdir(parents=True, exist_ok=True)
    print(f"Loading {HF_DATASET} split={HF_SPLIT} from Hugging Face ...", flush=True)
    ds = load_dataset(HF_DATASET, split=HF_SPLIT)
    df = ds.to_pandas()
    df.to_parquet(OUT, index=False)
    meta = {
        "dataset_id": HF_DATASET,
        "split": HF_SPLIT,
        "url": f"https://huggingface.co/datasets/{HF_DATASET}",
        "rows": len(df),
        "columns": list(df.columns),
        "repos": df["repo"].value_counts().to_dict(),
    }
    META.write_text(json.dumps(meta, indent=2) + "\n")
    print(f"Wrote {len(df)} rows -> {OUT}")
    print(f"Metadata -> {META}")
    print("\nInstances per repo:")
    for repo, n in sorted(meta["repos"].items(), key=lambda x: -x[1]):
        print(f"  {repo:30s} {n}")


if __name__ == "__main__":
    main()
