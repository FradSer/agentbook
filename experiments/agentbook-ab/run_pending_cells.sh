#!/usr/bin/env bash
# List cells missing an "agent fix" commit (use before score.py).
set -euo pipefail
AB="$(cd "$(dirname "$0")" && pwd)"
cd "$AB"
echo "=== completion ==="
uv run python cell_status.py --arm control 2>&1 | tail -1
uv run python cell_status.py --arm good 2>&1 | tail -1
echo ""
echo "=== pending (first 30) ==="
uv run python cell_status.py --pending-only | python3 -c "
import json,sys
p=json.load(sys.stdin)
print(f'total pending: {len(p)}')
for iid,arm in p[:30]:
    print(f'  {iid}__{arm}')
if len(p)>30: print(f'  ... +{len(p)-30} more')
"
