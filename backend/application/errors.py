from enum import StrEnum

from backend.domain.errors import ConcurrentModificationError

__all__ = [
    "AgentToolError",
    "ConcurrentModificationError",
    "ErrorType",
    "NotFoundError",
    "RateLimitError",
    "UnauthorizedError",
]


class UnauthorizedError(Exception):
    """Raised when API key is invalid."""


class NotFoundError(Exception):
    """Raised when a requested resource does not exist."""


class RateLimitError(Exception):
    """Raised when an agent exceeds the outcome reporting rate limit.

    ``retry_after_seconds`` carries an explicit hint the presentation
    layer can put in the ``Retry-After`` HTTP header. When unset the
    handler falls back to a conservative default — but call sites with
    a real window (e.g. "10 reports per hour") should pass the seconds
    so the agent doesn't have to guess.
    """

    def __init__(self, message: str = "", retry_after_seconds: int | None = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class ErrorType(StrEnum):
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"
    NOT_FOUND = "NOT_FOUND"
    INTERNAL = "INTERNAL"
    UNAUTHORIZED = "UNAUTHORIZED"
    RATE_LIMITED = "RATE_LIMITED"


class AgentToolError(Exception):
    """Standardized error envelope for agent-facing tool failures.

    Lets agents distinguish between transient failures they should retry
    and terminal failures they should surface to the user, instead of
    inferring "no results" from an opaque 500.
    """

    def __init__(
        self,
        error_type: ErrorType,
        message: str,
        is_retryable: bool,
    ) -> None:
        self.error_type = error_type
        self.message = message
        self.is_retryable = is_retryable
        super().__init__(message)
