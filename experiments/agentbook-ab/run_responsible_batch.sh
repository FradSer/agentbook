#!/usr/bin/env bash
# Full responsible benchmark: simulate corpus -> prompts -> prepare -> (agents) -> score
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AB="$ROOT/experiments/agentbook-ab"
MANIFEST="$AB/tasks/manifest.json"

cd "$ROOT"

echo "== simulate corpus =="
uv run python "$AB/simulate_corpus.py" --manifest "$MANIFEST"

echo "== responsible manifest (full verified set) =="
uv run python "$AB/filter_manifest.py" responsible -o "$AB/tasks/manifest.responsible.json"

echo "== build prompts =="
uv run python "$AB/build_prompts.py" \
  --manifest "$MANIFEST" \
  --corpus "$AB/_oracle/corpus.simulated.json" \
  -o "$AB/prompts.responsible.json"

echo "== reset + prepare cells =="
uv run python "$AB/reset_runs.py" --manifest "$MANIFEST"
uv run python "$AB/prepare_cells.py" \
  --prompts "$AB/prompts.responsible.json" \
  -o "$AB/cells_responsible.json"

echo "Prepared $(python3 -c "import json; print(len(json.load(open('$AB/cells_responsible.json'))))") cells."
echo "Launch Cursor sub-agents per AGENT_CELL_RULES.md, then:"
echo "  uv run python $AB/score.py control good bad --manifest $MANIFEST -o $AB/results.responsible.json"
