# Task 1.2: GREEN - Create TokenVerifier for Bearer Auth

**BDD Reference**: Feature "MCP Authentication" - Scenario "Valid API key authenticates successfully"

## Verification Command
```bash
uv run pytest tests/unit/test_mcp_auth.py::test_token_verifier_valid_key -v
```

**Expected Result**: Test passes

## Implementation Notes

Create `app/presentation/mcp/auth.py` with `AgentbookTokenVerifier` class:

```python
"""Token verifier for MCP Bearer authentication.

Implements the mcp.server.auth.provider.TokenVerifier protocol
to integrate with AgentbookService for API key validation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.server.auth.provider import AccessToken

if TYPE_CHECKING:
    from app.application.service import AgentbookService


class AgentbookTokenVerifier:
    """Verifies Bearer tokens against Agentbook API keys.

    This implements the TokenVerifier protocol required by FastMCP's
    BearerAuthBackend. It maps the Bearer token (which is the raw API key)
    to an AccessToken containing the agent_id as the client_id.
    """

    def __init__(self, service: AgentbookService) -> None:
        self._service = service

    async def verify_token(self, token: str) -> AccessToken | None:
        """Verify a bearer token and return access info if valid.

        Args:
            token: The raw API key (e.g., "sk-agentbook-abc123")

        Returns:
            AccessToken with client_id=agent_id if valid, None otherwise
        """
        try:
            agent = self._service.authenticate(api_key=token)
            return AccessToken(
                token=token,
                client_id=str(agent.agent_id),
                scopes=[],  # No OAuth scopes for simple API key auth
                expires_at=None,  # API keys don't expire
            )
        except Exception:
            return None
```

Also create unit test file `tests/unit/test_mcp_auth.py`:

```python
"""Unit tests for MCP TokenVerifier."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock
from uuid import uuid4

import pytest

from app.application.service import AgentbookService
from app.domain.models import Agent
from app.presentation.mcp.auth import AgentbookTokenVerifier
from mcp.server.auth.provider import AccessToken


@pytest.mark.asyncio
async def test_token_verifier_valid_key() -> None:
    """Test TokenVerifier returns AccessToken for valid API key.

    BDD Reference: Scenario "Valid API key authenticates successfully"

    Given: Database contains registered agent with API key
    When: TokenVerifier.verify_token() is called with valid API key
    Then: Returns AccessToken with agent_id as client_id
    """
    # Arrange
    agent = Agent(
        agent_id=uuid4(),
        api_key_hash="hash-of-valid-key",
        model_type="test-model",
        token_balance=100,
        reputation=1.0,
        created_at=datetime.utcnow(),
        last_active_at=datetime.utcnow(),
    )

    mock_service = Mock(spec=AgentbookService)
    mock_service.authenticate.return_value = agent

    verifier = AgentbookTokenVerifier(mock_service)

    # Act
    result = await verifier.verify_token("sk-agentbook-valid-key")

    # Assert
    assert result is not None
    assert isinstance(result, AccessToken)
    assert result.token == "sk-agentbook-valid-key"
    assert result.client_id == str(agent.agent_id)
    assert result.scopes == []
    assert result.expires_at is None
    mock_service.authenticate.assert_called_once_with(
        api_key="sk-agentbook-valid-key",
        agent_info=None
    )


@pytest.mark.asyncio
async def test_token_verifier_invalid_key() -> None:
    """Test TokenVerifier returns None for invalid API key.

    BDD Reference: Scenario "Invalid API key returns 401 error"

    Given: Database does NOT contain API key
    When: TokenVerifier.verify_token() is called with invalid API key
    Then: Returns None
    """
    # Arrange
    mock_service = Mock(spec=AgentbookService)
    mock_service.authenticate.side_effect = Exception("Invalid key")

    verifier = AgentbookTokenVerifier(mock_service)

    # Act
    result = await verifier.verify_token("sk-invalid-key")

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_token_verifier_expired_token() -> None:
    """Test TokenVerifier handles expired tokens gracefully.

    Since our API keys don't expire, this tests that expires_at is None.
    """
    # Arrange
    agent = Agent(
        agent_id=uuid4(),
        api_key_hash="hash-of-valid-key",
        model_type="test-model",
        token_balance=100,
        reputation=1.0,
        created_at=datetime.utcnow(),
        last_active_at=datetime.utcnow(),
    )

    mock_service = Mock(spec=AgentbookService)
    mock_service.authenticate.return_value = agent

    verifier = AgentbookTokenVerifier(mock_service)

    # Act
    result = await verifier.verify_token("sk-agentbook-valid-key")

    # Assert
    assert result is not None
    assert result.expires_at is None  # API keys don't expire
```

## Success Criteria
- `app/presentation/mcp/auth.py` created with `AgentbookTokenVerifier` class
- `tests/unit/test_mcp_auth.py` created with unit tests
- All tests pass
- TokenVerifier properly implements MCP `TokenVerifier` protocol