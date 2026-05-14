"""Local conftest for blog generation tests.

Overrides autouse fixtures from root conftest that require
a real database connection. Blog tests use pure mocks instead.
"""

import pytest


@pytest.fixture(autouse=True)
def patch_global_db_engine():
    """No-op override: blog tests use their own mock sessions."""
    yield
