import time

from app.application.quality_gate import check_problem_quality, check_solution_quality

# ---------------------------------------------------------------------------
# check_problem_quality
# ---------------------------------------------------------------------------


def test_problem_too_short() -> None:
    passed, reason = check_problem_quality("short", None)
    assert not passed
    assert reason is not None


def test_problem_whitespace_only() -> None:
    passed, reason = check_problem_quality("   ", None)
    assert not passed
    assert reason is not None


def test_problem_gibberish_repeated_chars() -> None:
    passed, reason = check_problem_quality("aaa aaa aaa aaa aaa aaa", None)
    assert not passed
    assert reason is not None


def test_problem_spam_detected() -> None:
    passed, reason = check_problem_quality(
        "buy cheap pills http://spam.com/buy", None
    )
    assert not passed
    assert reason is not None


def test_problem_valid_description() -> None:
    passed, reason = check_problem_quality(
        "How do I configure PostgreSQL to use pgvector extension?", None
    )
    assert passed
    assert reason is None


def test_problem_valid_with_stack_trace_error_signature() -> None:
    passed, reason = check_problem_quality(
        "Connection timeout after 30s when running pgvector query",
        "Traceback (most recent call last):\n  File 'test.py'",
    )
    assert passed
    assert reason is None


# ---------------------------------------------------------------------------
# check_solution_quality
# ---------------------------------------------------------------------------


def test_solution_empty() -> None:
    passed, reason = check_solution_quality("", None)
    assert not passed
    assert reason is not None


def test_solution_too_short() -> None:
    passed, reason = check_solution_quality("short", None)
    assert not passed
    assert reason is not None


def test_solution_url_only_no_explanation() -> None:
    passed, reason = check_solution_quality("http://example.com/solution", None)
    assert not passed
    assert reason is not None


def test_solution_spam_detected() -> None:
    passed, reason = check_solution_quality(
        "Click here to buy now http://spam.com", None
    )
    assert not passed
    assert reason is not None


def test_solution_valid() -> None:
    passed, reason = check_solution_quality(
        "Install pgvector extension using: CREATE EXTENSION vector; "
        "then run VACUUM ANALYZE on your table to rebuild indexes.",
        None,
    )
    assert passed
    assert reason is None


def test_solution_short_content_compensated_by_steps() -> None:
    passed, reason = check_solution_quality(
        "Run this command:",
        ["pip install pgvector", "python setup.py"],
    )
    assert passed
    assert reason is None


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------


def test_check_problem_quality_performance() -> None:
    long_input = "x " * 5000  # 10,000 chars
    start = time.perf_counter()
    check_problem_quality(long_input, None)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.05


def test_check_solution_quality_performance() -> None:
    long_input = "x " * 5000  # 10,000 chars
    start = time.perf_counter()
    check_solution_quality(long_input, None)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.05
