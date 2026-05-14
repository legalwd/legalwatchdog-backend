"""Local conftest for blog route tests.

Overrides autouse fixtures from root conftest that require
a real database connection. Blog route tests use pure mocks instead.
"""

import pytest


@pytest.fixture(autouse=True)
def patch_global_db_engine():
    """No-op override: blog route tests use their own mock sessions."""
    yield
