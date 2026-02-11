"""Exponential backoff state management for the agent.

This module provides a BackoffState dataclass that implements exponential
backoff with configurable base delay and maximum delay ceiling.

Usage:
    state = BackoffState(base_delay=60, max_delay=3600)
    delay = state.get_delay()  # Get current delay
    state.increment()          # Increment retry count on failure
    state.reset()              # Reset on success
"""

from dataclasses import dataclass


@dataclass(slots=True)
class BackoffState:
    """Stateful exponential backoff with configurable parameters.

    Attributes:
        retry_count: Number of consecutive failures recorded.
        base_delay: Initial delay in seconds (default: 60.0).
        max_delay: Maximum delay ceiling in seconds (default: 3600.0).
    """

    retry_count: int = 0
    base_delay: float = 60.0
    max_delay: float = 3600.0

    def get_delay(self) -> float:
        """Calculate the current backoff delay.

        Returns:
            The delay in seconds, calculated as base_delay * (2 ** retry_count),
            capped at max_delay.

        Examples:
            >>> state = BackoffState(base_delay=60, max_delay=3600)
            >>> state.get_delay()
            60.0
            >>> state.increment()
            >>> state.get_delay()
            120.0
        """
        delay = self.base_delay * (2**self.retry_count)
        return min(delay, self.max_delay)

    def increment(self) -> None:
        """Record a failure and increment the retry count.

        The next call to get_delay() will return a longer delay.
        """
        self.retry_count += 1

    def reset(self) -> None:
        """Reset the backoff state to initial conditions.

        Called on successful operation to reset retry count and delay.
        """
        self.retry_count = 0
