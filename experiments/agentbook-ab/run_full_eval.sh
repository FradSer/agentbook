#!/usr/bin/env bash
# Full two-layer A/B re-eval: retrieval gate + three-arm prep + agent runs + score.
#
# OpenRouter is restricted to openai/gpt-oss-20b:free only (no paid fallback).
# Strong three-arm runs use Cursor sub-agents (AGENT_CELL_RULES.md), not OpenRouter.
#
# Usage:
#   MODEL_TRACK=prep ./run_full_eval.sh
#   MODEL_TRACK=score-only MANIFEST=tasks/manifest.lift.json ./run_full_eval.sh
#   MODEL_TRACK=weak-cells MANIFEST=tasks/manifest.lift.json ./run_full_eval.sh
#   MODEL_TRACK=status MANIFEST=tasks/manifest.lift.json ./run_full_eval.sh
#
set -euo pipefail
AB="$(cd "$(dirname "$0")" && pwd)"
cd "$AB"

MANIFEST="${1:-${MANIFEST:-tasks/manifest.lift.json}}"
MODEL_TRACK="${MODEL_TRACK:-prep}"
API_URL="${AGENTBOOK_API_URL:-http://127.0.0.1:8078}"
OPENROUTER_MODEL="${OPENROUTER_MODEL:-openai/gpt-oss-20b:free}"
WORKERS="${OPENROUTER_WORKERS:-4}"

if [[ "$MANIFEST" == *multirepo* ]] || [[ "$MANIFEST" == *lift.multirepo* ]]; then
  RESULTS="results.multirepo.json"
  SUMMARY="summary.multirepo.json"
  WEAK_RESULTS="results.openrouter.multirepo.json"
elif [[ "$MANIFEST" == *lift* ]]; then
  RESULTS="results.lift.json"
  SUMMARY="summary.lift.json"
  WEAK_RESULTS="results.openrouter.lift.json"
else
  RESULTS="results.sympy.json"
  SUMMARY="summary.sympy.json"
  WEAK_RESULTS="results.openrouter.sympy.json"
fi

PROMPTS_OUT="prompts.$(basename "${MANIFEST%.json}").json"
CELLS_OUT="cells.$(basename "${MANIFEST%.json}").json"

echo "== run_full_eval: manifest=$MANIFEST track=$MODEL_TRACK =="

assert_openrouter_model() {
  uv run python -c "
from run_openrouter_cells import normalize_openrouter_models
normalize_openrouter_models(('$OPENROUTER_MODEL',))
print('OpenRouter model ok:', '$OPENROUTER_MODEL')
"
}

run_gate_and_prep() {
  echo "== Layer 1: retrieval gate =="
  MANIFEST="$MANIFEST" AGENTBOOK_API_URL="$API_URL" ./run_retrieval_gate.sh

  echo "== Layer 2 prep: prompts + cells (control/good/oracle) =="
  SKIP_RETRIEVAL_GATE=1 PROMPTS_OUT="$PROMPTS_OUT" CELLS_OUT="$CELLS_OUT" \
    MANIFEST="$MANIFEST" AGENTBOOK_API_URL="$API_URL" ./run_api_benchmark.sh
}

run_strong_cursor_hint() {
  local n
  n="$(python3 -c "import json; print(len(json.load(open('$CELLS_OUT'))))")"
  echo ""
  echo "== Strong model (Cursor sub-agent, NOT OpenRouter) =="
  echo "Run $n cells per AGENT_CELL_RULES.md, then:"
  echo "  MODEL_TRACK=score-only MANIFEST=$MANIFEST $0"
}

prep_weak_workspaces() {
  echo "== reset control+good only (preserve oracle strong runs) =="
  uv run python reset_runs.py --manifest "$MANIFEST" --arms control good
  uv run python -c "
import json, sys
sys.path.insert(0, '.')
from pathlib import Path
from cell_workspace import prepare_run_dir
prompts = json.loads(Path('$PROMPTS_OUT').read_text())
for spec in sorted(prompts.values(), key=lambda s: (s['instance_id'], s['arm'])):
    if spec['arm'] not in ('control', 'good'):
        continue
    iid, arm = spec['instance_id'], spec['arm']
    run_dir = Path('runs') / f'{iid}__{arm}'
    run_dir.mkdir(parents=True, exist_ok=True)
    prepare_run_dir(iid, arm)
    p = spec['prompt']
    (run_dir / 'prompt.md').write_text(p)
    (run_dir / 'prompt_used.md').write_text(p)
print('prepared control+good workspaces')
"
}

run_weak_openrouter() {
  assert_openrouter_model
  prep_weak_workspaces
  echo "== Weak model cells (control+good only): $OPENROUTER_MODEL =="
  uv run python -c "
import json
from pathlib import Path
cells = json.loads(Path('$CELLS_OUT').read_text())
out = [[i,a] for i,a in cells if a in ('control','good')]
Path('${CELLS_OUT%.json}_weak.json').write_text(json.dumps(out, indent=2)+'\n')
print(f'weak cells: {len(out)}')
"
  uv run python run_openrouter_cells.py \
    --cells "${CELLS_OUT%.json}_weak.json" \
    --prompts "$PROMPTS_OUT" \
    --model "$OPENROUTER_MODEL" \
    --workers "$WORKERS" \
    --delay "${OPENROUTER_DELAY:-45}" \
    -o "$WEAK_RESULTS"
  uv run python score.py control good --manifest "$MANIFEST" -o "$WEAK_RESULTS"
}

run_weak_cells_only() {
  run_weak_openrouter
}

run_score() {
  echo "== score + summarize =="
  uv run python score.py control good oracle --manifest "$MANIFEST" -o "$RESULTS"
  uv run python summarize_ab.py "$RESULTS" --manifest "$MANIFEST" -o "$SUMMARY"
}

run_status() {
  uv run python cell_status.py --cells "$CELLS_OUT"
}

case "$MODEL_TRACK" in
  prep)
    run_gate_and_prep
    run_strong_cursor_hint
    ;;
  strong)
    run_gate_and_prep
    run_strong_cursor_hint
    run_score
    ;;
  weak)
    run_gate_and_prep
    run_weak_cells_only
    ;;
  weak-cells)
    run_weak_cells_only
    ;;
  both)
    run_gate_and_prep
    run_strong_cursor_hint
    run_weak_cells_only
    run_score
    ;;
  score-only)
    run_score
    ;;
  status)
    run_status
    ;;
  cells-only)
    echo "ERROR: OpenRouter may only use openai/gpt-oss-20b:free." >&2
    echo "Strong three-arm cells must run via Cursor sub-agent (AGENT_CELL_RULES.md)." >&2
    echo "Then: MODEL_TRACK=score-only MANIFEST=$MANIFEST $0" >&2
    exit 1
    ;;
  *)
    echo "Usage: MODEL_TRACK=prep|strong|weak|both|score-only|weak-cells|status $0 [manifest]" >&2
    exit 1
    ;;
esac

echo "Done. Main results: $RESULTS  summary: $SUMMARY"
