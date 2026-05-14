import json
from uuid import uuid4

import pytest
from fastapi import HTTPException
from starlette.responses import JSONResponse

from app.api.modules.v1.api_access.enums.api_key_scope import Scopes
from app.api.modules.v1.api_access.routes import api_key_route


@pytest.mark.asyncio
async def test_get_api_key_scopes_authorized(monkeypatch):
    org_id = uuid4()

    monkeypatch.setattr(api_key_route.service, "can_generate_key", lambda perms: True)

    result = await api_key_route.get_api_key_scopes(org_id, current_user_permissions={})

    if isinstance(result, JSONResponse):
        body = json.loads(result.body)
        scopes_list = body.get("data", {}).get("scopes", [])
    else:
        scopes_list = result

    values = set()
    for r in scopes_list:
        if isinstance(r, dict):
            values.add(r.get("value"))
        else:
            values.add(r.value)
    expected = {s.value for s in Scopes}
    assert values == expected


@pytest.mark.asyncio
async def test_get_api_key_scopes_forbidden(monkeypatch):
    org_id = uuid4()

    monkeypatch.setattr(api_key_route.service, "can_generate_key", lambda perms: False)

    with pytest.raises(HTTPException) as excinfo:
        await api_key_route.get_api_key_scopes(org_id, current_user_permissions={})

    assert excinfo.value.status_code == 403
