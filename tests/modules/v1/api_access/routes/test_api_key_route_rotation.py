import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from starlette.responses import JSONResponse

from app.api.modules.v1.api_access.routes import api_key_route


class DummyDB:
    pass


@pytest.mark.asyncio
async def test_set_rotation_endpoint(monkeypatch):
    org_id = uuid4()
    api_key_id = uuid4()

    existing = SimpleNamespace(
        id=api_key_id,
        organization_id=org_id,
        key_name="k",
        organization=SimpleNamespace(name="org"),
        user=None,
        owner_user=None,
        receiver_email=None,
        hashed_key="h",
        scope="s",
        generated_by_user=None,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc),
        last_used_at=None,
    )

    monkeypatch.setattr(api_key_route, "crud", api_key_route.crud)

    async def fake_get(db, key_id):
        return existing

    async def fake_update(db, key_id, **kwargs):
        for k, v in kwargs.items():
            setattr(existing, k, v)
        return existing

    monkeypatch.setattr(api_key_route.crud, "get_key_by_id", fake_get)
    monkeypatch.setattr(api_key_route.crud, "update_key", fake_update)

    monkeypatch.setattr(api_key_route.service, "can_generate_key", lambda perms: True)

    payload = api_key_route.RotationToggleSchema(rotation_enabled=True, rotation_interval_days=2)

    result = await api_key_route.set_rotation(
        org_id, api_key_id, payload, db=DummyDB(), current_user_permissions={}
    )
    if isinstance(result, JSONResponse):
        body = json.loads(result.body)
        data = body.get("data", {})
        assert data["key_name"] == existing.key_name
        assert data["organization_name"] == existing.organization.name
        assert data["user_name"] is None
        assert data["api_key"] == existing.hashed_key
        assert data["rotation_enabled"] is True
        assert data["rotation_interval_days"] == 2
    else:
        assert result.key_name == existing.key_name
        assert result.organization_name == existing.organization.name
        assert result.user_name is None
        assert result.api_key == existing.hashed_key
        assert result.rotation_enabled is True
        assert result.rotation_interval_days == 2
