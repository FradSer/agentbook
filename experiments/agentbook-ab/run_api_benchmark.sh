#!/usr/bin/env bash
# Two-arm A/B via live agentbook API (control + good with RAG recall). No bad arm.
#
# Prereq: agentbook API running, e.g. from repo root:
#   DEMO_MODE=1 uv run uvicorn backend.main:app --host 127.0.0.1 --port 8078
#
set -euo pipefail
AB="$(cd "$(dirname "$0")" && pwd)"
cd "$AB"

API_URL="${AGENTBOOK_API_URL:-http://127.0.0.1:8078}"

echo "== ping agentbook at $API_URL =="
uv run python -c "
from benchmark.agentbook_client import AgentbookClient
c = AgentbookClient('$API_URL')
c.ping()
print('ok')
c.close()
"

echo "== simulate corpus =="
uv run python simulate_corpus.py

echo "== seed good solutions into agentbook =="
uv run python seed_agentbook.py --base-url "$API_URL"

echo "== build prompts (good arm uses GET /v1/search RAG) =="
uv run python build_prompts.py --use-api --api-url "$API_URL" -o prompts.api.json

echo "== prepare cells (control + good only) =="
uv run python reset_runs.py --arms control good
uv run python prepare_cells.py --prompts prompts.api.json -o cells_api.json

echo ""
echo "Ready: $(python3 -c "import json; print(len(json.load(open('cells_api.json'))))") cells"
echo "Run agents per AGENT_CELL_RULES.md, then:"
echo "  uv run python score.py control good -o results.api.json"
