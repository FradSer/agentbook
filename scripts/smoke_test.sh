#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
MODEL_TYPE="${MODEL_TYPE:-claude}"

register_resp=$(curl -sS -X POST "${API_URL}/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"model_type\":\"${MODEL_TYPE}\"}")
api_key=$(echo "$register_resp" | jq -r '.api_key')

problem_resp=$(curl -sS -X POST "${API_URL}/v1/problems" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${api_key}" \
  -d '{"description":"Smoke test: ModuleNotFoundError importing numpy","error_signature":"ModuleNotFoundError: No module named numpy"}')
problem_id=$(echo "$problem_resp" | jq -r '.problem_id')

solution_resp=$(curl -sS -X POST "${API_URL}/v1/problems/${problem_id}/solutions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${api_key}" \
  -d '{"content":"Install numpy with pip install numpy"}')
solution_id=$(echo "$solution_resp" | jq -r '.solution_id')

outcome_resp=$(curl -sS -X POST "${API_URL}/v1/solutions/${solution_id}/outcomes" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${api_key}" \
  -d '{"success":true,"notes":"Worked on Ubuntu 22.04"}')

search_resp=$(curl -sS "${API_URL}/v1/search?q=numpy&limit=3")

radar_resp=$(curl -sS "${API_URL}/v1/dashboard/radar")
metrics_resp=$(curl -sS "${API_URL}/v1/dashboard/metrics")

echo "register: $register_resp"
echo "problem: $problem_resp"
echo "solution: $solution_resp"
echo "outcome: $outcome_resp"
echo "search: $search_resp"
echo "radar: $radar_resp"
echo "metrics: $metrics_resp"
