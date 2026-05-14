"""Bridge Redis pub/sub events to connected websocket clients."""

from __future__ import annotations

import asyncio
import logging
from typing import Iterable, List, Optional

from app.api.events.models import BaseEvent, EventTopic
from app.api.events.subscriber import EventSubscriber
from app.api.ws.connection_manager import WebSocketConnectionManager


class RealtimeEventBridge:
    """Background relay that forwards Redis events to websocket clients."""

    def __init__(
        self,
        subscriber: EventSubscriber,
        manager: WebSocketConnectionManager,
        topics: Iterable[EventTopic],
    ) -> None:
        """Initialize the bridge with dependencies.

        Args:
            subscriber (EventSubscriber): Concrete subscriber reading from Redis channels.
            manager (WebSocketConnectionManager): Connection manager that broadcasts events.
            topics (Iterable[EventTopic]): Event topics that should be relayed.

        Returns:
            None

        Examples:
            >>> bridge = RealtimeEventBridge(subscriber, manager, [EventTopic.NOTIFICATIONS])
        """

        self._subscriber = subscriber
        self._manager = manager
        self._topics: List[EventTopic] = list(topics)
        self._task: Optional[asyncio.Task] = None
        self._logger = logging.getLogger("app")

    async def start(self) -> None:
        """Begin listening to Redis channels and relaying events.

        Raises:
            RuntimeError: If the bridge is already running.

        Returns:
            None

        Examples:
            >>> await bridge.start()
        """

        if self._task is not None:
            raise RuntimeError("Realtime bridge already running")
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Stop the relay and wait for the background task to finish.

        Returns:
            None

        Examples:
            >>> await bridge.stop()
        """

        if self._task is None:
            return
        await self._subscriber.stop()
        await self._task
        self._task = None

    async def _run(self) -> None:
        """Internal loop that streams events from Redis into websockets.

        Returns:
            None

        Examples:
            >>> await bridge._run()
        """

        try:
            await self._subscriber.listen(self._topics, self._handle_event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            self._logger.error("Realtime bridge encountered an error: %s", exc, exc_info=True)

    async def _handle_event(self, event: BaseEvent) -> None:
        """Forward a Redis event to all relevant websocket clients.

        Args:
            event (BaseEvent): Event produced by the subscriber.

        Returns:
            None

        Examples:
            >>> await bridge._handle_event(event)
        """

        await self._manager.send_event(event)
