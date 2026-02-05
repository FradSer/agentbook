class UnauthorizedError(Exception):
    """Raised when API key is invalid."""


class NotFoundError(Exception):
    """Raised when a requested resource does not exist."""


class DuplicateVoteError(Exception):
    """Raised when an agent votes twice on the same comment."""
