#!/usr/bin/env bash
# After Cursor sub-agents finish the complex manifest runs:
set -euo pipefail
cd "$(dirname "$0")/../.."
uv run python experiments/agentbook-ab/score.py control good bad \
  --manifest experiments/agentbook-ab/tasks/manifest.complex.json \
  -o experiments/agentbook-ab/results.complex.json
uv run python experiments/agentbook-ab/filter_manifest.py complex --dry-run
