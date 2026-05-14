"""Redis-backed publisher and subscriber implementations."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

from redis.asyncio import Redis

from app.api.events.models import BaseEvent, EventTopic
from app.api.events.publisher import EventPublisher
from app.api.events.subscriber import EventHandler, EventSubscriber


@dataclass(slots=True)
class RedisEventPublisher(EventPublisher):
    """Publish events to Redis channels derived from topics."""

    redis_client: Redis
    channel_map: Mapping[EventTopic, str]

    async def publish(self, event: BaseEvent) -> None:
        """Publish the event to the configured Redis channel.

        Args:
            event (BaseEvent): Event that should be serialized and broadcast.

        Returns:
            None

        Raises:
            ValueError: When the topic lacks a configured channel.

        Examples:
            >>> await publisher.publish(some_event)
        """

        topic = EventTopic(event.topic)
        channel = self.channel_map.get(topic)
        if not channel:
            raise ValueError(f"No Redis channel configured for topic {topic}")
        await self.redis_client.publish(channel, event.dump_json())


@dataclass(slots=True)
class RedisEventSubscriber(EventSubscriber):
    """Listen to Redis Pub/Sub channels and forward events to handlers."""

    redis_client: Redis
    channel_map: Mapping[EventTopic, str]
    _stop_event: asyncio.Event = field(default_factory=asyncio.Event, init=False)

    async def listen(self, topics: Iterable[EventTopic], handler: EventHandler) -> None:
        """Consume Redis pub/sub messages and forward to the handler.

        Args:
            topics (Iterable[EventTopic]): Topics that should be monitored.
            handler (EventHandler): Coroutine that processes each event.

        Returns:
            None

        Examples:
            >>> await subscriber.listen([EventTopic.NOTIFICATIONS], handler)
        """

        channels = self._resolve_channels(topics)
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe(*channels)
        try:
            while not self._stop_event.is_set():
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if not message:
                    await asyncio.sleep(0)
                    continue
                data = message["data"]
                event = BaseEvent.from_message(data)
                await handler(event)
        finally:
            await pubsub.unsubscribe(*channels)
            await pubsub.close()

    async def stop(self) -> None:
        """Signal the listener loop to halt at the next opportunity."""

        self._stop_event.set()

    def _resolve_channels(self, topics: Iterable[EventTopic]) -> Sequence[str]:
        """Map topics to Redis channel names.

        Args:
            topics (Iterable[EventTopic]): Topics requested by callers.

        Returns:
            Sequence[str]: Ordered Redis channels.

        Raises:
            ValueError: If any topic lacks a configured channel.

        Examples:
            >>> subscriber._resolve_channels([EventTopic.NOTIFICATIONS])
            ['events:notifications']
        """

        channels: list[str] = []
        for topic in topics:
            channel = self.channel_map.get(topic)
            if not channel:
                raise ValueError(f"No Redis channel configured for topic {topic}")
            channels.append(channel)
        return channels
