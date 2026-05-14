"""Publisher interfaces for emitting domain events."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.api.events.models import BaseEvent


class EventPublisher(ABC):
    """Abstract publisher used by services to enqueue events.

    Subclasses hide the underlying transport (Redis, message bus, etc.).
    """

    @abstractmethod
    async def publish(self, event: BaseEvent) -> None:
        """Emit the supplied event through the configured transport.

        Args:
            event (BaseEvent): Event to be propagated.

        Returns:
            None: Subclasses perform the side effect directly.

        Raises:
            ValueError: When the implementation rejects the event payload.

        Examples:
            >>> await publisher.publish(BaseEvent(...))
        """
