#!/usr/bin/env bash
# Two-arm A/B via live agentbook API (control + good with RAG recall). No bad arm.
#
# Prereq: agentbook API running, e.g. from repo root:
#   DEMO_MODE=1 uv run uvicorn backend.main:app --host 127.0.0.1 --port 8078
# Set VOYAGE_API_KEY and/or OPENROUTER_API_KEY so /v1/search uses server embeddings
# (not deterministic Fallback). External fix models use a separate API key.
#
set -euo pipefail
AB="$(cd "$(dirname "$0")" && pwd)"
cd "$AB"

API_URL="${AGENTBOOK_API_URL:-http://127.0.0.1:8078}"
MANIFEST="${MANIFEST:-tasks/manifest.json}"
PROMPTS_OUT="${PROMPTS_OUT:-prompts.api.json}"
CELLS_OUT="${CELLS_OUT:-cells_api.json}"

echo "== manifest: $MANIFEST =="

echo "== ping agentbook at $API_URL =="
uv run python -c "
from benchmark.agentbook_client import AgentbookClient
c = AgentbookClient('$API_URL')
c.ping()
print('ok')
c.close()
"

echo "== build seed corpus (for API POST) =="
uv run python build_seed_corpus.py --manifest "$MANIFEST"

echo "== seed good solutions into agentbook (required before good-arm test) =="
uv run python seed_agentbook.py \
  --base-url "$API_URL" \
  --corpus _oracle/corpus.seed.json \
  --force

echo "== verify agentbook has seeded data =="
uv run python verify_agentbook_seed.py --manifest "$MANIFEST" --base-url "$API_URL"

echo "== build prompts (good arm: live GET /v1/search only) =="
uv run python build_prompts.py --use-api --api-url "$API_URL" --manifest "$MANIFEST" -o "$PROMPTS_OUT"

echo "== prepare cells (control + good only) =="
uv run python reset_runs.py --manifest "$MANIFEST" --arms control good
uv run python prepare_cells.py --prompts "$PROMPTS_OUT" -o "$CELLS_OUT"

echo ""
echo "Ready: $(python3 -c "import json; print(len(json.load(open('$CELLS_OUT'))))") cells"
echo "Run agents per AGENT_CELL_RULES.md, then:"
echo "  uv run python score.py control good --manifest $MANIFEST -o results.api.json"
