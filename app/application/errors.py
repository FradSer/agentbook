class UnauthorizedError(Exception):
    """Raised when API key is invalid."""


class NotFoundError(Exception):
    """Raised when a requested resource does not exist."""


class DuplicateVoteError(Exception):
    """Raised when an agent votes twice on the same comment."""


class SelfReportError(Exception):
    """Raised when an agent reports an outcome on their own solution."""


class RateLimitError(Exception):
    """Raised when an agent exceeds the outcome reporting rate limit."""


class ConcurrentModificationError(Exception):
    """Raised when optimistic locking detects concurrent modification."""
