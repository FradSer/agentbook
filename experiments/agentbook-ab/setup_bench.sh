#!/usr/bin/env bash
# Bootstrap the public, reproducible SWE-bench Verified substrate for agentbook-ab.
set -euo pipefail
cd "$(dirname "$0")"

echo "==> 1. Download SWE-bench Verified from Hugging Face"
uv run --with datasets --with pandas --with pyarrow python fetch_verified.py

echo "==> 2. Create benchmark venv (Python 3.10) and install pinned deps"
if [[ ! -d .venv ]]; then
  uv venv .venv --python 3.10
fi
uv pip install --python .venv/bin/python -r bench_requirements.txt

echo "==> 3. Clone sympy (required for current no-Docker benchmark)"
uv run --with pandas python clone_repos.py --repo sympy/sympy

echo "==> 4. RED-verify sympy tasks into tasks/manifest.json"
uv run --with pandas --with pyarrow python build_benchmark.py --rebuild-unverified

echo ""
echo "Done. Run the two-arm eval:"
echo "  ./run_api_benchmark.sh && ./run_openrouter_benchmark.sh"
