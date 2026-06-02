"""Cross-transport contract feature tests.

The shared harness fixtures (``rest_client``, ``mcp_client``,
``assert_transport_parity``, ``embedding_fault``) live in the package-root
``backend/tests/conftest.py`` so both the feature tests here and the paired
unit parity tests in ``backend/tests/unit/`` resolve the same fixtures from one
definition. This module is intentionally empty beyond this note.
"""

from __future__ import annotations
