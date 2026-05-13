"""Tests for BackoffState exponential backoff with delay capping."""

from agent.src.backoff import BackoffState


class TestBackoffState:
    def test_initial_state(self):
        state = BackoffState()
        assert state.retry_count == 0
        assert state.get_delay() == 60

    def test_exponential_growth(self):
        state = BackoffState(base_delay=60.0)
        state.increment()
        assert state.get_delay() == 120.0
        state.increment()
        assert state.get_delay() == 240.0

    def test_max_delay_cap(self):
        state = BackoffState(base_delay=60.0, max_delay=300.0)
        for _ in range(10):
            state.increment()
        assert state.get_delay() == 300.0

    def test_reset_on_success(self):
        state = BackoffState()
        for _ in range(5):
            state.increment()
        state.reset()
        assert state.retry_count == 0
        assert state.get_delay() == 60
