"""Subscriber interfaces for consuming domain events."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Iterable

from app.api.events.models import BaseEvent, EventTopic

EventHandler = Callable[[BaseEvent], Awaitable[None]]


class EventSubscriber(ABC):
    """Abstract subscription interface for background dispatchers."""

    @abstractmethod
    async def listen(self, topics: Iterable[EventTopic], handler: EventHandler) -> None:
        """Consume events for the supplied topics and invoke the handler.

        Args:
            topics (Iterable[EventTopic]): Topics to subscribe to.
            handler (EventHandler): Coroutine invoked for each incoming event.

        Returns:
            None: Implementations stream until cancelled.

        Raises:
            RuntimeError: If subscriptions cannot be established.

        Examples:
            >>> await subscriber.listen([EventTopic.NOTIFICATIONS], handler)
        """

    @abstractmethod
    async def stop(self) -> None:
        """Request a graceful shutdown for in-flight subscriptions.

        Returns:
            None

        Examples:
            >>> await subscriber.stop()
        """
