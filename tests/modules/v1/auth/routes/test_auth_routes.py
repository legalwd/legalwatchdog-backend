import json

import jwt as pyjwt

from app.api.core.config import settings
from app.api.utils import jwt as jwt_utils
from app.api.utils.response_payloads import auth_response


def test_create_access_token_and_decode():
    token = jwt_utils.create_access_token("user-1", "org-1", "role-1")
    payload = pyjwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    assert payload["sub"] == "user-1"
    assert "jti" in payload


def test_auth_response_structure():
    token = "fake.jwt.token"
    resp = auth_response(
        status_code=201, message="ok", access_token=token, data={"email": "a@b.com"}
    )
    body = resp.body
    assert body is not None
    data = json.loads(body)
    assert data["status"] == "SUCCESS"
    assert data["status_code"] == 201
    assert data["data"]["access_token"] == token
    assert data["data"]["email"] == "a@b.com"
