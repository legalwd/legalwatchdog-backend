from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.core.custom_exceptions.exceptions import PasswordReuseError
from app.api.modules.v1.auth.service import reset_password as rp_mod
from app.api.utils.password import hash_password


class FakeClient:
    def __init__(self, user_id: str | None):
        self.user_id = user_id
        self.deleted_keys = []

    async def get(self, key: str):
        return self.user_id

    async def delete(self, key: str):
        self.deleted_keys.append(key)


class FakeDB:
    def __init__(self, user: SimpleNamespace):
        self._user = user
        self.added = []
        self.committed = False

    async def get(self, cls, id):
        return self._user if str(id) == str(self._user.id) else None

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True

    async def rollback(self):
        return None


@pytest.mark.asyncio
async def test_reset_password_rejects_old_password(monkeypatch):
    """Reset should raise PasswordReuseError when new password equals the old one."""
    user_id = str(uuid4())
    old_password = "old-secret"
    user = SimpleNamespace(
        id=user_id, email="u@example.com", hashed_password=hash_password(old_password)
    )

    fake_db = FakeDB(user)
    fake_client = FakeClient(user_id)

    async def _fake_get_redis():
        return fake_client

    monkeypatch.setattr(rp_mod, "get_redis_client", _fake_get_redis)

    with pytest.raises(PasswordReuseError):
        await rp_mod.reset_password(fake_db, reset_token="token-1", new_password=old_password)


@pytest.mark.asyncio
async def test_reset_password_success_changes_password(monkeypatch):
    """When new password differs, reset_password should update the user's hashed_password."""
    user_id = str(uuid4())
    old_password = "old-secret"
    new_password = "new-secret"
    user = SimpleNamespace(
        id=user_id, email="u@example.com", hashed_password=hash_password(old_password)
    )

    fake_db = FakeDB(user)
    fake_client = FakeClient(user_id)

    async def _fake_get_redis():
        return fake_client

    monkeypatch.setattr(rp_mod, "get_redis_client", _fake_get_redis)

    result = await rp_mod.reset_password(fake_db, reset_token="token-2", new_password=new_password)

    assert result is True
    assert user.hashed_password != hash_password(old_password)
