#!/usr/bin/env bash
# Bootstrap the public, reproducible SWE-bench Verified substrate for agentbook-ab.
set -euo pipefail
cd "$(dirname "$0")"

MULTIREPO=0
for arg in "$@"; do
  case "$arg" in
    --multirepo) MULTIREPO=1 ;;
  esac
done

echo "==> 1. Download SWE-bench Verified from Hugging Face"
uv run --with datasets --with pandas --with pyarrow python fetch_verified.py

echo "==> 2. Create benchmark venv (Python 3.10) and install pinned deps"
if [[ ! -d .venv ]]; then
  uv venv .venv --python 3.10
fi
uv pip install --python .venv/bin/python -r bench_requirements.txt

if [[ "$MULTIREPO" -eq 1 ]]; then
  echo "==> 3. Clone sympy + sklearn + pytest"
  uv run python clone_repos.py --multirepo
  echo "==> 4. RED-verify multi-repo pilot -> tasks/manifest.json (sympy keeps existing verified)"
  uv run --with pandas --with pyarrow python build_benchmark.py --multirepo --rebuild-unverified
  echo "==> 5. Build manifest.multirepo.json (sympy hard + pilot repos)"
  uv run python filter_manifest.py multirepo -o tasks/manifest.multirepo.json
  echo ""
  echo "Done. Run retrieval gate, then A/B:"
  echo "  MANIFEST=tasks/manifest.multirepo.json ./run_retrieval_gate.sh"
  echo "  MANIFEST=tasks/manifest.multirepo.json ./run_openrouter_benchmark.sh"
else
  echo "==> 3. Clone sympy (required for current no-Docker benchmark)"
  uv run --with pandas python clone_repos.py --repo sympy/sympy
  echo "==> 4. RED-verify sympy tasks into tasks/manifest.json"
  uv run --with pandas --with pyarrow python build_benchmark.py --rebuild-unverified
  echo ""
  echo "Done. Run the two-arm eval:"
  echo "  ./run_api_benchmark.sh && ./run_openrouter_benchmark.sh"
  echo ""
  echo "For multi-repo pilot: ./setup_bench.sh --multirepo"
fi
