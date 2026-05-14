import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.api.core.config import settings
from app.api.db.database import get_db
from main import app

# Ensure relationship attributes expected by APIKey model exist on Organization/User
# This avoids SQLAlchemy mapper initialization errors when tests import models in
# a different order than the application does. Keep this scoped to the test file.
try:
    from sqlmodel import Relationship

    from app.api.modules.v1.organization.models.organization_model import Organization
    from app.api.modules.v1.users.models.users_model import User

    if not hasattr(Organization, "api_keys"):
        Organization.api_keys = Relationship(
            back_populates="organization",
            sa_relationship_kwargs={"cascade": "all, delete-orphan"},
        )

    if not hasattr(User, "owned_api_keys"):
        User.owned_api_keys = Relationship(
            back_populates="owner_user",
            sa_relationship_kwargs={"foreign_keys": "api_keys.user_id"},
        )

    if not hasattr(User, "generated_api_keys"):
        User.generated_api_keys = Relationship(
            back_populates="generated_by_user",
            sa_relationship_kwargs={"foreign_keys": "api_keys.generated_by"},
        )
except Exception:
    pass

try:
    from app.api.modules.v1.api_access.models.api_key_model import APIKey

    api_tbl = getattr(APIKey, "__table__", None)
    if api_tbl is not None:
        if not hasattr(api_tbl, "user_id"):
            setattr(api_tbl, "user_id", api_tbl.c.user_id)
        if not hasattr(api_tbl, "generated_by"):
            setattr(api_tbl, "generated_by", api_tbl.c.generated_by)
        if not hasattr(api_tbl, "organization_id"):
            setattr(api_tbl, "organization_id", api_tbl.c.organization_id)
except Exception:
    pass


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_webhook_onboard_creates_key(client, pg_async_session):
    async def override_get_db():
        yield pg_async_session

    app.dependency_overrides[get_db] = override_get_db

    from app.api.modules.v1.organization.models.organization_model import Organization

    org = Organization(name="Webhook Test Org", is_active=True)
    pg_async_session.add(org)
    await pg_async_session.commit()
    await pg_async_session.refresh(org)

    from app.api.modules.v1.users.models.users_model import User

    user = User(email="webhook@example.com", name="Webhook User", is_active=True, is_approved=True)
    pg_async_session.add(user)
    await pg_async_session.commit()
    await pg_async_session.refresh(user)

    import importlib
    from datetime import datetime as _real_datetime

    _ak_mod = importlib.import_module("app.api.modules.v1.api_access.models.api_key_model")

    class _FakeDateTime:
        @classmethod
        def now(cls, tz=None):
            return _real_datetime.now()

    setattr(_ak_mod, "datetime", _FakeDateTime)
    # Patch the service module that generates created_at/expires_at too
    _svc_mod = importlib.import_module("app.api.modules.v1.api_access.service.api_key_service")
    setattr(_svc_mod, "datetime", _FakeDateTime)

    payload = {
        "organization_id": str(org.id),
        "key_name": "webhook-key",
        "scopes": ["read:project"],
        # use the actual user id we created above
        "generated_by": str(user.id),
    }

    headers = {"X-WEBHOOK-SECRET": settings.WEB_SECRET_KEY}

    resp = await client.post("/api/v1/webhooks/onboard", json=payload, headers=headers)
    assert resp.status_code == status.HTTP_201_CREATED
    body = resp.json()
    assert "api_key" in body
    assert "id" in body
