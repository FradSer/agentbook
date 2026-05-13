class ConcurrentModificationError(Exception):
    """Raised when optimistic locking detects concurrent modification."""
