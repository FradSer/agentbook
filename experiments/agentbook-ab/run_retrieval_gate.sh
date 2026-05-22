#!/usr/bin/env bash
# Retrieval gate: seed corpus + verify search stack + recall metrics.
#
# Prereq: agentbook API running with VOYAGE_API_KEY (EMBEDDING_VERSION=v2):
#   DEMO_MODE=1 uv run uvicorn backend.main:app --host 127.0.0.1 --port 8078
#
set -euo pipefail
AB="$(cd "$(dirname "$0")" && pwd)"
cd "$AB"

API_URL="${AGENTBOOK_API_URL:-http://127.0.0.1:8078}"
MANIFEST="${MANIFEST:-tasks/manifest.multirepo.json}"
GATE_REPORT="${GATE_REPORT:-retrieval_gate_report.json}"

echo "== manifest: $MANIFEST =="

echo "== ping agentbook at $API_URL =="
uv run python -c "
from benchmark.agentbook_client import AgentbookClient
c = AgentbookClient('$API_URL')
c.ping()
print('ok')
c.close()
"

echo "== build seed corpus =="
uv run python build_seed_corpus.py --manifest "$MANIFEST"

echo "== seed good solutions into agentbook =="
uv run python seed_agentbook.py \
  --base-url "$API_URL" \
  --corpus _oracle/corpus.seed.json \
  --force

echo "== verify seed + search stack =="
uv run python verify_agentbook_seed.py \
  --manifest "$MANIFEST" \
  --base-url "$API_URL"

echo "== retrieval gate (recall@k + provider audit) =="
uv run python eval_retrieval_gate.py \
  --manifest "$MANIFEST" \
  --base-url "$API_URL" \
  -o "$GATE_REPORT"

echo ""
echo "Retrieval gate passed. Report: $GATE_REPORT"
