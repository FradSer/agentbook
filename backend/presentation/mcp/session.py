"""Session ID validation and generation for MCP Streamable HTTP transport.

This module provides cryptographic session ID generation and format validation
following the MCP specification requirements for Streamable HTTP transport.

Session IDs must:
- Be between 8 and 128 characters
- Contain only visible ASCII characters (0x21-0x7E)
- Be generated using cryptographically secure random sources
"""

import re
import secrets

# Session ID validation constants
MIN_SESSION_ID_LENGTH = 8
MAX_SESSION_ID_LENGTH = 128
DEFAULT_SESSION_ID_LENGTH = 32

# Pre-compiled pattern for visible ASCII characters (0x21-0x7E)
SESSION_ID_PATTERN = re.compile(r"^[\x21-\x7E]+$")

# Characters used for session ID generation (visible ASCII: 0x21-0x7E)
_SESSION_CHARS = "".join(chr(i) for i in range(0x21, 0x7F))


def validate_session_id(session_id: str | None) -> bool:
    """Validate session ID format.

    Args:
        session_id: The session ID to validate, or None for new connections.

    Returns:
        True if the session ID is valid, False otherwise.

    Notes:
        - None is considered valid (indicates new connection request)
        - Valid session IDs must be between MIN_SESSION_ID_LENGTH and
          MAX_SESSION_ID_LENGTH characters
        - Valid session IDs must contain only visible ASCII characters (0x21-0x7E)
    """
    if session_id is None:
        return True

    if not isinstance(session_id, str):
        return False

    length = len(session_id)
    if length < MIN_SESSION_ID_LENGTH or length > MAX_SESSION_ID_LENGTH:
        return False

    return bool(SESSION_ID_PATTERN.match(session_id))


def generate_session_id(length: int = DEFAULT_SESSION_ID_LENGTH) -> str:
    """Generate a cryptographically secure session ID.

    Args:
        length: The desired length of the session ID. Defaults to
            DEFAULT_SESSION_ID_LENGTH (32).

    Returns:
        A cryptographically secure random string of the specified length.

    Raises:
        ValueError: If length is less than MIN_SESSION_ID_LENGTH or greater
            than MAX_SESSION_ID_LENGTH.

    Notes:
        - Uses secrets.choice() for cryptographic security
        - Generated IDs contain only visible ASCII characters (0x21-0x7E)
    """
    if length < MIN_SESSION_ID_LENGTH:
        raise ValueError(
            f"Session ID length must be at least {MIN_SESSION_ID_LENGTH}"
        )
    if length > MAX_SESSION_ID_LENGTH:
        raise ValueError(
            f"Session ID length must be at most {MAX_SESSION_ID_LENGTH}"
        )

    return "".join(secrets.choice(_SESSION_CHARS) for _ in range(length))