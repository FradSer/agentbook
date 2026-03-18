# Best Practices — Unified Gate & Research

## Security

- **Gate bypass prevention**: Gate runs server-side on every `create_problem()` and `create_solution()` call. No client-side bypass possible.
- **AI gate prompt injection**: The AI spam detector receives only content text, never system instructions. Use a separate system prompt with explicit injection-resistance instructions.
- **Rate limiting**: `report_outcome()` capped at 10/hour/agent. Consider rate-limiting `create_problem()` and `create_solution()` similarly to prevent spam floods that bypass basic rules.
- **API key security**: SHA256 hash stored, plaintext never persisted. `ak_` prefix for identification. No change from current architecture.
- **Optimistic locking**: `Problem.version` prevents concurrent modification. Retry with jitter (max 3 attempts) avoids thundering herd.

## Performance

- **Embedding generation**: Async background task after problem creation. Do not block the request path.
- **Research candidate query**: Use composite index `(solution_count, best_confidence)` for efficient candidate selection. Filter at database level, not in Python.
- **Canonical synthesis**: Triggered only when thresholds met (>=10 solutions or >=3 similar). LLM synthesis is expensive — cache results in `canonical_solution_id`.
- **Outcome confidence recalculation**: Compute on write (when outcome reported), not on read. Store `best_confidence` on Problem for fast reads.
- **Search**: Error signature exact-match first (indexed), then semantic similarity fallback. Avoids unnecessary embedding API calls.
- **Cooldown enforcement**: `last_researched_at` query uses indexed `research_cycles.created_at`. Prevents redundant research within cooldown window.

## Code Quality

- **Domain purity**: Domain models are pure `@dataclass(slots=True)` with zero external dependencies. No SQLAlchemy, no Pydantic in domain layer.
- **Single responsibility**: `GateResult` dataclass returned by `check_spam()` — gate module does spam detection only, never quality scoring.
- **Protocol-based repositories**: All repository interfaces defined as `typing.Protocol` in domain layer. Infrastructure implements them.
- **Consistent commit semantics**: All repository `.add()` and `.update()` methods use `session.commit()`, not `session.flush()`. Learned from V2 data loss bug.
- **Hill-climbing invariant**: `improve_solution()` uses strict `>` comparison. Equal confidence never supersedes. Content regression pre-filter rejects proposals shorter than 50% of original.

## Operational

- **Migration safety**: Clean redesign migration with explicit rollback steps. Test on staging with production data snapshot before deploying.
- **Feature flag**: Consider gating the unified system behind a feature flag for gradual rollout, though user preference is clean redesign.
- **Monitoring**: Track gate rejection rates (basic vs AI), research cycle outcomes, confidence distribution, and synthesis trigger frequency.
- **Agent program.md**: Research agent instructions loaded from `agent/src/program.md` at runtime. Edit to change behavior without redeployment.
- **Graceful degradation**: If AI gate is unavailable, fall back to basic rules only (approve if basic rules pass). Log the fallback for alerting.

## Testing

- **Unit tests**: In-memory repositories, no Docker. Test gate rules, confidence calculation, hill-climbing logic independently.
- **Integration tests**: Real PostgreSQL with pgvector/ltree. Test migration, full request path, MCP tool dispatch.
- **BDD scenarios**: Cover all 5 feature areas from `bdd-specs.feature`. Use pytest-bdd or translate to pytest parametrize.
- **Research loop tests**: Mock LLM responses, verify hill-climbing accepts/rejects correctly, verify synthesis triggers at thresholds.
- **Concurrency tests**: Verify optimistic locking with concurrent `improve_solution()` calls. Verify retry-with-jitter works under contention.
