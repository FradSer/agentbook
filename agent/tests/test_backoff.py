"""Tests for agent backoff state management.

Tests for BackoffState class - exponential backoff with delay capping.
"""

from agent.src.backoff import BackoffState


class TestBackoffState:
    """Test BackoffState exponential backoff logic."""

    def test_initial_state(self):
        """Test initial state properties.

        Scenario:
        - Create new BackoffState()
        - Assert retry_count == 0
        - Assert get_delay() == base_delay (default 60s)
        """
        state = BackoffState()
        assert state.retry_count == 0
        assert state.get_delay() == 60

    def test_exponential_growth(self):
        """Test exponential growth of delay.

        Scenario:
        - Create BackoffState(base_delay=60.0)
        - Call increment(), assert get_delay() == 120.0
        - Call increment() again, assert get_delay() == 240.0
        """
        state = BackoffState(base_delay=60.0)
        state.increment()
        assert state.get_delay() == 120.0
        state.increment()
        assert state.get_delay() == 240.0

    def test_max_delay_cap(self):
        """Test max delay cap functionality.

        Scenario:
        - Create BackoffState(base_delay=60.0, max_delay=300.0)
        - Call increment() 10 times
        - Assert get_delay() == 300.0 (capped at max)
        """
        state = BackoffState(base_delay=60.0, max_delay=300.0)
        for _ in range(10):
            state.increment()
        assert state.get_delay() == 300.0

    def test_reset_on_success(self):
        """Test reset on success.

        Scenario:
        - Create BackoffState()
        - Increment multiple times
        - Call reset()
        - Assert retry_count == 0
        - Assert get_delay() == base_delay
        """
        state = BackoffState()
        for _ in range(5):
            state.increment()
        state.reset()
        assert state.retry_count == 0
        assert state.get_delay() == 60
