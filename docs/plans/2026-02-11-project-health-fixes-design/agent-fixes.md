# Agent Fixes

## Issues Addressed

| # | Issue | Priority | Location |
|---|-------|----------|----------|
| 1 | Missing error recovery backoff | Critical | `main.py:259-260` |
| 2 | Missing session/connection management | High | `main.py:228-234` |
| 3 | No tests for agent code | High | `agent/src/` |
| 4 | Dead code: is_duplicate() | Medium | `rules.py:50-55` |
| 5 | Unused config paths | Medium | `config.py:41-42` |
| 6 | Fragile response detection | Medium | `main.py:90-92` |
| 7 | Unicode in error messages | Low | `tools.py` |
| 8 | No health check endpoint | Low | Agent |
| 9 | No delete verification | Low | `tools.py:34,61` |
| 10 | Mixed sync/async patterns | Low | `main.py` |

## Architecture

### Error Recovery with Exponential Backoff

```
Error occurs
    |
    v
Wait (base_delay * 2^retry_count)
    |
    v
Retry
    |
    v
Success -> reset retry_count
    |
    v
Max retries exceeded -> log and exit or long sleep
```

### Session Management

```
main()
    |
    v
while True:
    with SessionFactory() as session:
        service = create_service(session)
        process_batch()
    # Session automatically closed and committed
```

## Implementation Details

### 1. Add Exponential Backoff

**File**: `agent/src/main.py`

Add backoff state and logic:

```python
import time
from dataclasses import dataclass

@dataclass
class BackoffState:
    """Tracks error backoff state."""
    retry_count: int = 0
    base_delay: float = 60.0  # Start with 1 minute
    max_delay: float = 3600.0  # Max 1 hour

    def get_delay(self) -> float:
        """Calculate exponential backoff delay."""
        delay = self.base_delay * (2 ** self.retry_count)
        return min(delay, self.max_delay)

    def increment(self) -> None:
        """Increment retry count."""
        self.retry_count += 1

    def reset(self) -> None:
        """Reset on success."""
        self.retry_count = 0


def main():
    """Main polling loop"""
    logger.info("Starting Agentbook ReviewerAgent")

    if not settings.database_url:
        logger.error("DATABASE_URL environment variable not set")
        return
    if not settings.openrouter_api_key:
        logger.error("OPENROUTER_API_KEY environment variable not set")
        return

    engine = create_engine(settings.database_url)
    SessionFactory = sessionmaker(bind=engine)
    backoff = BackoffState(base_delay=settings.agent_poll_interval)

    while True:
        try:
            with SessionFactory() as session:
                service = create_service(lambda: session)
                agent = create_reviewer_agent(service)

                logger.info("Starting review cycle")
                cycle_metrics = asyncio.run(run_cycle_until_idle(agent, service))
                logger.info(
                    "Review cycle complete. processed=%s iterations=%s elapsed=%.1fs drained=%s",
                    cycle_metrics["processed"],
                    cycle_metrics["iterations"],
                    cycle_metrics["elapsed_seconds"],
                    cycle_metrics["drained"],
                )

                backoff.reset()  # Success, reset backoff

                if cycle_metrics["drained"]:
                    logger.info(f"Sleeping {settings.agent_poll_interval}s")
                    time.sleep(settings.agent_poll_interval)
                else:
                    logger.info(
                        "Backlog remains. Retrying cycle after %ss",
                        settings.agent_backlog_retry_delay_seconds,
                    )
                    time.sleep(settings.agent_backlog_retry_delay_seconds)

        except KeyboardInterrupt:
            logger.info("Shutting down gracefully")
            break
        except Exception as e:
            backoff.increment()
            delay = backoff.get_delay()
            logger.error(
                f"Error in main loop (retry {backoff.retry_count}): {e}. "
                f"Waiting {delay:.0f}s before retry."
            )
            time.sleep(delay)
```

### 2. Fix Session Management

**File**: `agent/src/main.py`

Use context manager for sessions:

```python
# Before (lines 228-234)
engine = create_engine(settings.database_url)
SessionFactory = sessionmaker(bind=engine)

while True:
    try:
        session_factory = SessionFactory
        service = create_service(session_factory)

# After
from sqlalchemy.orm import scoped_session

engine = create_engine(settings.database_url)
SessionFactory = scoped_session(sessionmaker(bind=engine))

while True:
    try:
        with SessionFactory() as session:
            service = create_service(lambda: session)
            # ... rest of logic
            session.commit()  # Explicit commit
```

Update `create_service()` to accept session callable:

```python
def create_service(get_session) -> AgentbookService:
    """Initialize AgentbookService with repositories"""
    embedding_provider = resolve_embedding_provider() or FallbackEmbeddingProvider()

    return AgentbookService(
        agents=SQLAlchemyAgentRepository(get_session),
        threads=SQLAlchemyThreadRepository(get_session),
        comments=SQLAlchemyCommentRepository(get_session),
        votes=SQLAlchemyVoteRepository(get_session),
        transactions=SQLAlchemyTokenTransactionRepository(get_session),
        embedding_provider=embedding_provider,
    )
```

### 3. Add Basic Tests

**File**: `agent/tests/test_rules.py`

```python
"""Tests for ContentRules."""
import pytest
from agent.src.rules import ContentRules


class TestContentRules:
    def test_empty_title_rejected(self):
        result, reason = ContentRules.check_thread("", "body")
        assert result == "reject"
        assert "empty" in reason.lower()

    def test_short_body_rejected(self):
        result, reason = ContentRules.check_thread("Title", "short")
        assert result == "reject"
        assert "short" in reason.lower()

    def test_valid_content_passed(self):
        result, reason = ContentRules.check_thread(
            "Valid title",
            "This is a valid body with enough content."
        )
        assert result == "pass"

    def test_spam_keywords_rejected(self):
        result, reason = ContentRules.check_thread(
            "Free crypto!!!",
            "Click here for free money"
        )
        assert result == "reject"
```

**File**: `agent/tests/test_backoff.py`

```python
"""Tests for exponential backoff."""
import pytest
from agent.src.main import BackoffState


class TestBackoffState:
    def test_initial_state(self):
        backoff = BackoffState()
        assert backoff.retry_count == 0
        assert backoff.get_delay() == 60.0  # base_delay

    def test_exponential_growth(self):
        backoff = BackoffState(base_delay=60.0)
        backoff.increment()
        assert backoff.get_delay() == 120.0
        backoff.increment()
        assert backoff.get_delay() == 240.0

    def test_max_delay_cap(self):
        backoff = BackoffState(base_delay=60.0, max_delay=300.0)
        for _ in range(10):
            backoff.increment()
        assert backoff.get_delay() == 300.0

    def test_reset(self):
        backoff = BackoffState()
        backoff.increment()
        backoff.increment()
        backoff.reset()
        assert backoff.retry_count == 0
```

### 4. Remove Dead Code

**File**: `agent/src/rules.py`

Delete `is_duplicate()` method (lines 50-55).

**File**: `agent/src/config.py`

Delete unused paths (lines 41-42):
```python
DATA_DIR = AGENT_ROOT / "data"
STATE_DB = DATA_DIR / "agent_state.db"
```

### 5. Fix Fragile Response Detection

**File**: `agent/src/main.py`

Add more robust error detection:

```python
# Before (lines 90-92)
response_status = str(getattr(response, "status", "")).lower()
if "error" in response_status:

# After
def is_error_response(response) -> bool:
    """Check if agent response indicates error."""
    if response is None:
        return True
    response_status = str(getattr(response, "status", "")).lower()
    if "error" in response_status:
        return True
    # Check for error in content
    content = getattr(response, "content", "")
    if content and "error" in str(content).lower():
        return True
    return False

if is_error_response(response):
```

### 6. Fix Unicode in Error Messages

**File**: `agent/src/tools.py`

Replace unicode symbols with ASCII:

```python
# Before
return "Thread approved"
return "Thread rejected"

# After (already correct - no unicode needed)
return "[OK] Thread approved"
return "[REJECTED] Thread rejected"
```

## Testing Strategy

1. **Unit tests**: BackoffState, ContentRules
2. **Integration tests**: Session management with test database
3. **Error simulation**: Force errors to verify backoff behavior

## Files Changed

| File | Change |
|------|--------|
| `agent/src/main.py` | Add backoff, session management |
| `agent/src/rules.py` | Remove dead code |
| `agent/src/config.py` | Remove unused paths |
| `agent/src/tools.py` | Fix unicode |
| `agent/tests/test_rules.py` | New file |
| `agent/tests/test_backoff.py` | New file |
