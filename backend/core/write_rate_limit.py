"""In-process per-author throttle for the authenticated write path.

REST `/v1/search` has slowapi and MCP `recall` has its own limiter, but the
authenticated write verbs (create problem, create solution, improve) had no
bound — one valid `ak_` key could flood the public CC0 commons unbounded. This
caps contributions per author per hour. In-process and single-replica (same
caveat as the other limiters); operator-issued keys, the write content gate, and
the confidence math are the complementary layers.
"""

from __future__ import annotations

from backend.core.mcp_rate_limit import MCPRateLimiter

# Generous enough for a real debugging session that contributes several
# problems and refines them, tight enough that a flood loop is bounded.
WRITE_LIMIT_PER_HOUR = 120

write_limiter = MCPRateLimiter(max_calls=WRITE_LIMIT_PER_HOUR, window_seconds=3600)
