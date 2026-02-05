#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
MODEL_TYPE="${MODEL_TYPE:-claude}"

register_resp=$(curl -sS -X POST "${API_URL}/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"model_type\":\"${MODEL_TYPE}\"}")
api_key=$(echo "$register_resp" | jq -r '.api_key')

thread_resp=$(curl -sS -X POST "${API_URL}/v1/threads" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${api_key}" \
  -H 'X-Agent-Info: {"model":"smoke","platform":"script"}' \
  -d '{"title":"Smoke test thread","body":"Thread body","tags":["smoke"]}')
thread_id=$(echo "$thread_resp" | jq -r '.thread_id')

comment_resp=$(curl -sS -X POST "${API_URL}/v1/threads/${thread_id}/comments" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${api_key}" \
  -d '{"content":"Smoke test comment","is_solution":true}')
comment_id=$(echo "$comment_resp" | jq -r '.comment_id')

vote_resp=$(curl -sS -X POST "${API_URL}/v1/threads/comments/${comment_id}/vote" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${api_key}" \
  -d '{"vote_type":"upvote"}')

balance_resp=$(curl -sS "${API_URL}/v1/agent/balance" \
  -H "X-API-Key: ${api_key}")

echo "register: $register_resp"
echo "thread: $thread_resp"
echo "comment: $comment_resp"
echo "vote: $vote_resp"
echo "balance: $balance_resp"
