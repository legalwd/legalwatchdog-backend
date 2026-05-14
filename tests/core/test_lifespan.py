"""Tests covering FastAPI lifespan wiring for realtime features."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI

import main


class _AsyncContextManager:
    """Minimal async context manager stub."""

    def __init__(self, enter_result):
        self._enter_result = enter_result

    async def __aenter__(self):
        return self._enter_result

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.fixture
def lifespan_dependencies(monkeypatch):
    """Provide patched engine, session factory, and seeding routine."""

    conn = SimpleNamespace(run_sync=AsyncMock())
    begin_cm = _AsyncContextManager(conn)

    engine_mock = MagicMock()
    engine_mock.begin.return_value = begin_cm
    engine_mock.dispose = AsyncMock()
    monkeypatch.setattr(main, "engine", engine_mock)

    session = AsyncMock()
    session_ctx = _AsyncContextManager(session)
    session_factory = MagicMock(return_value=session_ctx)
    monkeypatch.setattr(main, "AsyncSessionLocal", session_factory)

    seed_mock = AsyncMock()
    monkeypatch.setattr(main, "seed_billing_plans", seed_mock)

    return {"engine": engine_mock, "session": session, "seed": seed_mock}


@pytest.mark.asyncio
async def test_lifespan_skips_bridge_when_realtime_disabled(lifespan_dependencies, monkeypatch):
    """Ensure bridge is not started when realtime websockets are disabled."""

    monkeypatch.setattr(main.settings, "ENABLE_REALTIME_WEBSOCKETS", False)

    get_subscriber_mock = AsyncMock()
    monkeypatch.setattr(main, "get_event_subscriber", get_subscriber_mock)
    shutdown_mock = AsyncMock()
    monkeypatch.setattr(main, "shutdown_event_bus", shutdown_mock)
    bridge_cls = MagicMock()
    monkeypatch.setattr(main, "RealtimeEventBridge", bridge_cls)

    async with main.lifespan(FastAPI()):
        pass

    get_subscriber_mock.assert_not_awaited()
    bridge_cls.assert_not_called()
    shutdown_mock.assert_not_awaited()
    lifespan_dependencies["seed"].assert_awaited_once()
    lifespan_dependencies["engine"].dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_lifespan_starts_and_stops_bridge_when_enabled(lifespan_dependencies, monkeypatch):
    """Ensure bridge lifecycle runs when realtime websockets are enabled."""

    monkeypatch.setattr(main.settings, "ENABLE_REALTIME_WEBSOCKETS", True)

    subscriber = AsyncMock()
    get_subscriber_mock = AsyncMock(return_value=subscriber)
    monkeypatch.setattr(main, "get_event_subscriber", get_subscriber_mock)

    shutdown_mock = AsyncMock()
    monkeypatch.setattr(main, "shutdown_event_bus", shutdown_mock)

    bridge_instance = SimpleNamespace(start=AsyncMock(), stop=AsyncMock())
    bridge_cls = MagicMock(return_value=bridge_instance)
    manager_stub = object()
    monkeypatch.setattr(main, "websocket_manager", manager_stub)
    monkeypatch.setattr(main, "RealtimeEventBridge", bridge_cls)

    async with main.lifespan(FastAPI()):
        pass

    get_subscriber_mock.assert_awaited_once()
    bridge_cls.assert_called_once()
    called_kwargs = bridge_cls.call_args.kwargs
    assert called_kwargs["subscriber"] is subscriber
    assert called_kwargs["manager"] is manager_stub
    assert called_kwargs["topics"] == [
        main.EventTopic.NOTIFICATIONS,
        main.EventTopic.SCRAPE_JOBS,
    ]
    bridge_instance.start.assert_awaited_once()
    bridge_instance.stop.assert_awaited_once()
    shutdown_mock.assert_awaited_once()
    lifespan_dependencies["seed"].assert_awaited_once()
    lifespan_dependencies["engine"].dispose.assert_awaited_once()
