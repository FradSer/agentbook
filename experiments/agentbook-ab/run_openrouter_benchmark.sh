#!/usr/bin/env bash
# Weak-model appendix via OpenRouter (openai/gpt-oss-20b:free only).
#
# Prefer: MODEL_TRACK=weak-cells MANIFEST=tasks/manifest.lift.json ./run_full_eval.sh
#
# Prereqs: OPENROUTER_API_KEY in env or repo root .env; agentbook API on :8078
#
#   ./run_openrouter_benchmark.sh retry-errors  # retry cells_api_errors.json
#
set -euo pipefail
AB="$(cd "$(dirname "$0")" && pwd)"
cd "$AB"

MODE="${1:-full}"
OPENROUTER_MODEL="${OPENROUTER_MODEL:-openai/gpt-oss-20b:free}"
MANIFEST="${MANIFEST:-tasks/manifest.lift.json}"
RESULTS="${RESULTS:-results.openrouter.lift.json}"
ENV_FILE="${AB}/../../.env"

uv run python -c "
from run_openrouter_cells import normalize_openrouter_models
normalize_openrouter_models(('$OPENROUTER_MODEL',))
"

if [[ -z "${OPENROUTER_API_KEY:-}" ]] && [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi
if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
  echo "ERROR: set OPENROUTER_API_KEY in env or repo root .env" >&2
  exit 1
fi

PROMPTS_OUT="prompts.$(basename "${MANIFEST%.json}").json"
CELLS_OUT="cells.$(basename "${MANIFEST%.json}").json"

run_cells() {
  local cells_file="${1:-${CELLS_OUT%.json}_weak.json}"
  echo "== OpenRouter cells (${cells_file}, model ${OPENROUTER_MODEL}, workers ${OPENROUTER_WORKERS:-4}) =="
  uv run python run_openrouter_cells.py \
    --cells "$cells_file" \
    --prompts "$PROMPTS_OUT" \
    --model "$OPENROUTER_MODEL" \
    --workers "${OPENROUTER_WORKERS:-4}" \
    --delay "${OPENROUTER_DELAY:-45}" \
    -o openrouter_run_results.json
}

run_score() {
  echo "== score (manifest: $MANIFEST) =="
  uv run python score.py control good --manifest "$MANIFEST" -o "$RESULTS"
}

case "$MODE" in
  run-only) run_cells "$2"; run_score ;;
  retry-errors)
    uv run python collect_openrouter_errors.py --merge
    run_cells cells_api_errors.json
    run_score
    ;;
  full)
    echo "Use: MODEL_TRACK=weak-cells MANIFEST=$MANIFEST ./run_full_eval.sh" >&2
    exit 1
    ;;
  *)
    echo "Usage: $0 [retry-errors|run-only [cells.json]]" >&2
    echo "Primary path: MODEL_TRACK=weak-cells ./run_full_eval.sh" >&2
    exit 1
    ;;
esac

echo "Done. Results: $RESULTS"
