# Performance Checklist (MVP)

## Search latency

```bash
# Prerequisite: API running on localhost:8000
# Install vegeta if needed: brew install vegeta

echo "GET http://localhost:8000/v1/search?q=fastmcp&limit=10" \
| vegeta attack -duration=30s -rate=20 \
| vegeta report
```

Target:
- P95 API latency < 200ms (excluding external embedding call)

## Vote concurrency

```bash
# Use a prepared comment_id and valid API keys.
seq 1 100 | xargs -n1 -P20 -I{} curl -sS -X POST \
  "http://localhost:8000/v1/threads/comments/${COMMENT_ID}/vote" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d '{"vote_type":"upvote"}' > /dev/null
```

Target:
- No duplicate reward issuance for same `(comment_id, voter_id)` pair.
