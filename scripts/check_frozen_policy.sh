#!/usr/bin/env bash
# CI guard: fail the build if `calculate_confidence.__frozen_policy_version__`
# is bumped without a matching entry in docs/confidence-changelog.md.
set -euo pipefail

VERSION=$(uv run --quiet python -c "from backend.application.confidence import calculate_confidence; print(calculate_confidence.__frozen_policy_version__)")

if ! grep -qE "^## ${VERSION}( |$)" docs/confidence-changelog.md; then
    echo "ERROR: frozen_policy version ${VERSION} missing from docs/confidence-changelog.md" >&2
    echo "       Bump requires a changelog entry documenting the math change." >&2
    exit 1
fi

echo "frozen_policy ${VERSION} is documented."
