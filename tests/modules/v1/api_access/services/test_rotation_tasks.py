from types import SimpleNamespace

import pytest

import app.api.modules.v1.api_access.service.rotation_tasks as rotation_tasks


class DummyCtx:
    def __init__(self, obj=None):
        self.obj = obj

    async def __aenter__(self):
        return self.obj

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_rotate_due_keys_triggers_rotation(monkeypatch):
    fake_key = SimpleNamespace(id="fake-id-1", key_name="k1")

    monkeypatch.setattr(rotation_tasks, "AsyncSessionLocal", lambda: DummyCtx(None))

    called = []

    class FakeService:
        def __init__(self, crud):
            pass

        async def find_keys_for_rotation(self, db):
            return [fake_key]

        async def api_key_rotation(self, db, key_id):
            called.append(key_id)
            return "new-key"

    monkeypatch.setattr(rotation_tasks, "APIKeyService", FakeService)
    monkeypatch.setattr(rotation_tasks, "APIKeyCRUD", lambda: None)

    await rotation_tasks._rotate_due_keys()

    assert called == [fake_key.id]
