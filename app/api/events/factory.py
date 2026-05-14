"""Factory helpers for lazily configuring realtime event transports."""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, Optional

from redis.asyncio import Redis

from app.api.core.config import settings
from app.api.events.models import EventTopic
from app.api.events.providers.redis_pubsub import RedisEventPublisher, RedisEventSubscriber
from app.api.events.publisher import EventPublisher
from app.api.events.subscriber import EventSubscriber

_factory_lock = asyncio.Lock()
_redis_client: Optional[Redis] = None
_event_publisher: Optional[RedisEventPublisher] = None
_event_subscriber: Optional[RedisEventSubscriber] = None

logger = logging.getLogger("app")


def _channel_map() -> Dict[EventTopic, str]:
    """Return EventTopic-aware Redis channel mappings.

    Returns:
        Dict[EventTopic, str]: Mapping between topics and Redis channels.

    Examples:
        >>> _channel_map()[EventTopic.NOTIFICATIONS]
        'events:notifications'
    """

    return {
        EventTopic.NOTIFICATIONS: settings.REALTIME_NOTIFICATIONS_CHANNEL,
        EventTopic.SCRAPE_JOBS: settings.REALTIME_SCRAPE_CHANNEL,
    }


def _assert_realtime_enabled() -> None:
    """Ensure realtime websockets have been opted in via configuration.

    Raises:
        RuntimeError: If realtime support has not been enabled.

    Examples:
        >>> _assert_realtime_enabled()
        None
    """

    if not settings.ENABLE_REALTIME_WEBSOCKETS:
        raise RuntimeError("Realtime websockets are disabled")


async def _get_redis_client() -> Redis:
    """Lazily instantiate a shared Redis asyncio client.

    NOTE: Caller must hold _factory_lock before calling this function.

    Returns:
        Redis: Shared asyncio Redis client.

    Raises:
        RuntimeError: If realtime websockets are disabled.

    Examples:
        >>> async with _factory_lock:
        ...     client = await _get_redis_client()
        True
    """

    global _redis_client
    _assert_realtime_enabled()
    if _redis_client is None:
        _redis_client = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=False,
            socket_connect_timeout=5,
            socket_keepalive=True,
        )
        # Test the connection immediately to catch errors early
        await _redis_client.ping()
    return _redis_client


async def get_event_publisher() -> EventPublisher:
    """Return a singleton Redis-backed event publisher.

    Returns:
        EventPublisher: Publisher that services use to emit events.

    Raises:
        RuntimeError: If realtime websockets are not enabled.

    Examples:
        >>> publisher = await get_event_publisher()
        >>> await publisher.publish(some_event)
        None
    """

    global _event_publisher
    _assert_realtime_enabled()
    async with _factory_lock:
        if _event_publisher is None:
            redis_client = await _get_redis_client()
            _event_publisher = RedisEventPublisher(
                redis_client=redis_client, channel_map=_channel_map()
            )
        return _event_publisher


async def get_event_subscriber() -> EventSubscriber:
    """Return a singleton Redis-backed event subscriber.

    Returns:
        EventSubscriber: Subscriber that listens for events to relay.

    Raises:
        RuntimeError: If realtime websockets are not enabled.

    Examples:
        >>> subscriber = await get_event_subscriber()
        >>> await subscriber.listen([EventTopic.NOTIFICATIONS], handler)
        None
    """

    global _event_subscriber
    _assert_realtime_enabled()
    async with _factory_lock:
        if _event_subscriber is None:
            redis_client = await _get_redis_client()
            _event_subscriber = RedisEventSubscriber(
                redis_client=redis_client, channel_map=_channel_map()
            )
        return _event_subscriber


async def shutdown_event_bus() -> None:
    """Cleanup shared Redis resources when the application stops.

    Returns:
        None

    Examples:
        >>> await shutdown_event_bus()
        None
    """

    global _event_publisher, _event_subscriber, _redis_client
    async with _factory_lock:
        if _event_subscriber is not None:
            await _event_subscriber.stop()
            _event_subscriber = None
        _event_publisher = None
        if _redis_client is not None:
            await _redis_client.close()
            await _redis_client.connection_pool.disconnect()
            _redis_client = None
