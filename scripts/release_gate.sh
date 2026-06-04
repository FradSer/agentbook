#!/usr/bin/env bash
# Pre-release gate: run the widest test surface available on this machine.
set -euo pipefail
cd "$(dirname "$0")/.."

# Optional: reclaim disk from local experiment runs (gitignored, safe to re-run)
if [ "${RELEASE_GATE_CLEAN_EXPERIMENTS:-0}" = "1" ]; then
  uv run python experiments/agentbook-ab/cleanup_experiment.py
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'
FAIL=0

run_step() {
  local name="$1"
  shift
  echo ""
  echo "========== $name =========="
  if "$@"; then
    echo -e "${GREEN}PASS${NC}: $name"
  else
    echo -e "${RED}FAIL${NC}: $name"
    FAIL=1
  fi
}

run_step "Backend unit + features (make fast)" make fast
run_step "Retrieval eval (make eval)" make eval
run_step "Agent simulation (in-memory)" \
  uv run pytest backend/tests/simulation -m simulation -q --tb=line

if docker info >/dev/null 2>&1; then
  run_step "Integration smoke (Docker)" make smoke
  run_step "E2E matrix (Docker)" make e2e
else
  echo ""
  echo "SKIP: Docker not available — integration/e2e Postgres tests not run"
fi

run_step "Frontend lint" make frontend-lint
run_step "Frontend build" make frontend-build

if [ -n "${VOYAGE_API_KEY:-}" ]; then
  run_step "Real-mode retrieval eval" make eval-real
else
  echo "SKIP: VOYAGE_API_KEY unset — real-mode retrieval eval"
fi

# Live product path (DEMO_MODE)
PORT="${RELEASE_GATE_PORT:-8765}"
BASE="http://127.0.0.1:${PORT}"
if ! curl -sf "${BASE}/v1/dashboard/metrics" >/dev/null 2>&1; then
  echo "Starting DEMO_MODE backend on :${PORT}..."
  DEMO_MODE=1 DATABASE_URL= uv run uvicorn backend.main:app --host 127.0.0.1 --port "${PORT}" &
  SRV_PID=$!
  trap 'kill "$SRV_PID" 2>/dev/null || true' EXIT
  for _ in $(seq 1 30); do
    curl -sf "${BASE}/v1/dashboard/metrics" >/dev/null 2>&1 && break
    sleep 0.5
  done
fi

run_step "Live E2E (recall/contribute/report/flywheel)" \
  uv run python scripts/e2e_verify_live.py --base "$BASE"

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo -e "${GREEN}RELEASE GATE: GO${NC} — all executed checks passed."
  exit 0
else
  echo -e "${RED}RELEASE GATE: NO-GO${NC} — fix failures above before shipping."
  exit 1
fi
