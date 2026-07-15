#!/usr/bin/env bash
# Poll PR #51 for new review activity and print actionable deltas as JSON lines.
# State file tracks already-seen ids so repeated polls are idempotent.
set -euo pipefail

REPO="${REPO:-FradSer/agentbook}"
PR="${PR:-51}"
STATE_DIR="${STATE_DIR:-/tmp/cursor/pr51-monitor}"
STATE_FILE="${STATE_DIR}/state.json"
LOG_FILE="${STATE_DIR}/monitor.log"

mkdir -p "$STATE_DIR"
if [[ ! -f "$STATE_FILE" ]]; then
  echo '{"lastSeenReviewCommentIds":[],"lastSeenIssueCommentIds":[],"lastSeenReviewIds":[],"processedFingerprints":[]}' >"$STATE_FILE"
fi

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

log() { echo "[$(ts)] $*" | tee -a "$LOG_FILE" >&2; }

python3 - "$REPO" "$PR" "$STATE_FILE" <<'PY'
import json, subprocess, sys
from pathlib import Path

repo, pr, state_path = sys.argv[1], sys.argv[2], Path(sys.argv[3])
state = json.loads(state_path.read_text())

def gh_json(args):
    out = subprocess.check_output(["gh", "api", *args], text=True)
    return json.loads(out)

review_comments = gh_json([f"repos/{repo}/pulls/{pr}/comments", "--paginate"])
issue_comments = gh_json([f"repos/{repo}/issues/{pr}/comments", "--paginate"])
reviews = gh_json([f"repos/{repo}/pulls/{pr}/reviews", "--paginate"])

seen_rc = set(state.get("lastSeenReviewCommentIds") or [])
seen_ic = set(state.get("lastSeenIssueCommentIds") or [])
seen_rv = set(state.get("lastSeenReviewIds") or [])
processed = set(state.get("processedFingerprints") or [])

new_events = []

# Skip bot noise that is not actionable code feedback
NOISE_SUBSTRINGS = (
    "Bugbot is not enabled",
    "Codex usage limits",
    "consumer version of Gemini Code Assist",
)

def is_noise(body: str) -> bool:
    return any(s in (body or "") for s in NOISE_SUBSTRINGS)

for c in review_comments:
    cid = c["id"]
    if cid in seen_rc:
        continue
    body = c.get("body") or ""
    if is_noise(body):
        seen_rc.add(cid)
        continue
    fp = f"rc-{cid}"
    event = {
        "type": "review_comment",
        "fingerprint": fp,
        "id": cid,
        "user": (c.get("user") or {}).get("login"),
        "path": c.get("path"),
        "line": c.get("line") or c.get("original_line"),
        "body": body,
        "html_url": c.get("html_url"),
        "already_processed": fp in processed,
    }
    new_events.append(event)
    seen_rc.add(cid)

for c in issue_comments:
    cid = c["id"]
    if cid in seen_ic:
        continue
    body = c.get("body") or ""
    if is_noise(body):
        seen_ic.add(cid)
        continue
    # Ignore empty / purely procedural PR comments from humans unless they
    # look like review feedback (contain file refs or fix requests).
    fp = f"ic-{cid}"
    event = {
        "type": "issue_comment",
        "fingerprint": fp,
        "id": cid,
        "user": (c.get("user") or {}).get("login"),
        "body": body,
        "html_url": c.get("html_url"),
        "already_processed": fp in processed,
    }
    new_events.append(event)
    seen_ic.add(cid)

for r in reviews:
    rid = r["id"]
    if rid in seen_rv:
        continue
    body = r.get("body") or ""
    state_name = r.get("state")
    if is_noise(body) and state_name == "COMMENTED" and not body.strip():
        seen_rv.add(rid)
        continue
    # Summary reviews often duplicate inline comments; still surface if they
    # carry CHANGES_REQUESTED / actionable text.
    if state_name in ("CHANGES_REQUESTED", "APPROVED") or (
        body and not is_noise(body) and len(body) > 40
    ):
        fp = f"rv-{rid}"
        new_events.append({
            "type": "review",
            "fingerprint": fp,
            "id": rid,
            "user": (r.get("user") or {}).get("login"),
            "state": state_name,
            "body": body,
            "html_url": r.get("html_url"),
            "already_processed": fp in processed,
        })
    seen_rv.add(rid)

state["lastSeenReviewCommentIds"] = sorted(seen_rc)
state["lastSeenIssueCommentIds"] = sorted(seen_ic)
state["lastSeenReviewIds"] = sorted(seen_rv)
state_path.write_text(json.dumps(state, indent=2) + "\n")

# Also dump unresolved review threads for context
try:
    gql = subprocess.check_output([
        "gh", "api", "graphql", "-f", "query="
        "query { repository(owner:\"%s\", name:\"%s\") { pullRequest(number:%s) { reviewThreads(first:50) { nodes { isResolved isOutdated comments(first:3) { nodes { author { login } body path createdAt } } } } } } }"
        % (repo.split("/")[0], repo.split("/")[1], pr)
    ], text=True)
    threads = json.loads(gql)["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]
    unresolved = [t for t in threads if not t.get("isResolved")]
except Exception as e:
    unresolved = [{"error": str(e)}]

print(json.dumps({
    "new_events": new_events,
    "unresolved_thread_count": len(unresolved) if isinstance(unresolved, list) else None,
    "unresolved_threads": unresolved if isinstance(unresolved, list) else unresolved,
}, indent=2))
PY
