#!/usr/bin/env bash
# Two-arm A/B via OpenRouter (openai/gpt-oss-20b) — prep, run, score, retry api_error.
#
# Prereqs: OPENROUTER_API_KEY in env or repo root .env; agentbook API on :8078
#
#   ./run_openrouter_benchmark.sh              # prep + 108 cells + score
#   ./run_openrouter_benchmark.sh prep-only
#   ./run_openrouter_benchmark.sh run-only
#   ./run_openrouter_benchmark.sh retry-errors  # only cells_api_errors.json
#
set -euo pipefail
AB="$(cd "$(dirname "$0")" && pwd)"
cd "$AB"

MODE="${1:-full}"
MODEL_PRIMARY="${OPENROUTER_MODEL:-openai/gpt-oss-20b:free}"
MODEL_FALLBACK="${OPENROUTER_MODEL_FALLBACK:-openai/gpt-oss-20b}"
RESULTS="${RESULTS:-results.openrouter.json}"
ENV_FILE="${AB}/../../.env"

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

run_prep() {
  ./run_api_benchmark.sh
}

run_cells() {
  local cells_file="${1:-cells_api.json}"
  echo "== OpenRouter cells (${cells_file}, model ${MODEL_PRIMARY}) =="
  uv run python run_openrouter_cells.py \
    --cells "$cells_file" \
    --model "$MODEL_PRIMARY" \
    --model "$MODEL_FALLBACK" \
    --delay "${OPENROUTER_DELAY:-45}" \
    -o openrouter_run_results.json
}

run_score() {
  echo "== score =="
  uv run python score.py control good --manifest tasks/manifest.json -o "$RESULTS"
}

case "$MODE" in
  prep-only) run_prep ;;
  run-only) run_cells; run_score ;;
  retry-errors)
    uv run python collect_openrouter_errors.py --merge
    run_cells cells_api_errors.json
    run_score
    ;;
  full)
    run_prep
    run_cells
    run_score
    ;;
  *)
    echo "Usage: $0 [full|prep-only|run-only|retry-errors]" >&2
    exit 1
    ;;
esac

echo "Done. Results: $RESULTS"
