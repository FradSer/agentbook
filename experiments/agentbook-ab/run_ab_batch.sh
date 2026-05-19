#!/usr/bin/env bash
# Print pending cells and completion stats for the API two-arm benchmark.
#
#   ./run_ab_batch.sh              # summary
#   ./run_ab_batch.sh control      # list pending control
#   ./run_ab_batch.sh good         # list pending good
#
set -euo pipefail
AB="$(cd "$(dirname "$0")" && pwd)"
cd "$AB"
ARM="${1:-all}"
uv run python cell_status.py --arm "$ARM" --pending-only 2>/dev/null | python3 -c "
import json,sys
pending=json.load(sys.stdin)
print(f'pending {len(pending)} cells (arm={sys.argv[1] if len(sys.argv)>1 else \"all\"})')
for iid,arm in pending[:20]:
    print(f'  {iid}__{arm}')
if len(pending)>20:
    print(f'  ... +{len(pending)-20} more')
" "$ARM"
uv run python cell_status.py --arm control 2>&1 | tail -1
uv run python cell_status.py --arm good 2>&1 | tail -1
