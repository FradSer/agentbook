#!/usr/bin/env bash
# Sync NEXT_PUBLIC_* vars from root .env to frontend/.env.local
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ROOT_ENV="$ROOT_DIR/.env"
FRONTEND_ENV="$ROOT_DIR/frontend/.env.local"

if [ ! -f "$ROOT_ENV" ]; then
  echo "No root .env found, skipping frontend env sync"
  exit 0
fi

grep '^NEXT_PUBLIC_' "$ROOT_ENV" > "$FRONTEND_ENV" 2>/dev/null || true
echo "Synced NEXT_PUBLIC_* vars to frontend/.env.local"
