#!/usr/bin/env bash
# Validate root .env against .env.example required variables.
# Usage:
#   bash scripts/validate-env.sh              # validate all sections
#   bash scripts/validate-env.sh --section=backend  # validate shared + backend only
set -euo pipefail

ROOT_DIR="$(unset CDPATH; cd "$(dirname "$0")/.." && pwd)"
ROOT_ENV="$ROOT_DIR/.env"
EXAMPLE_ENV="$ROOT_DIR/.env.example"
FILTER="${1:---all}"

if [ ! -f "$ROOT_ENV" ]; then
  echo "ERROR: .env not found. Run: cp .env.example .env" >&2
  exit 1
fi

if [ ! -f "$EXAMPLE_ENV" ]; then
  echo "ERROR: .env.example not found" >&2
  exit 1
fi

current_section=""
missing=0

while IFS= read -r line; do
  # Detect section markers
  if [[ "$line" =~ ^#\ @section:(.+)$ ]]; then
    current_section="${BASH_REMATCH[1]}"
    continue
  fi

  # Skip blank lines and comments (including commented-out optional vars)
  [[ -z "$line" || "$line" =~ ^# ]] && continue

  # Extract KEY from KEY=value
  key="${line%%=*}"
  [[ -z "$key" ]] && continue

  # Filter by section if requested
  if [[ "$FILTER" != "--all" ]]; then
    target="${FILTER#--section=}"
    [[ "$current_section" != "shared" && "$current_section" != "$target" ]] && continue
  fi

  # Check key exists in .env (uncommented)
  if ! grep -qE "^${key}=" "$ROOT_ENV"; then
    echo "  MISSING [$current_section] $key" >&2
    missing=$((missing + 1))
  fi
done < "$EXAMPLE_ENV"

if [ "$missing" -gt 0 ]; then
  echo "ERROR: $missing required variable(s) missing from .env" >&2
  exit 1
fi

echo "env: all required variables present"
