"""Data models that represent domain events pushed over websockets."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Type

from pydantic import BaseModel, ConfigDict, Field


class EventTopic(str, Enum):
    """Supported logical channels for outbound events."""

    NOTIFICATIONS = "notifications"
    SCRAPE_JOBS = "scrape_jobs"
    TICKET_COMMENTS = "ticket_comments"


class BaseEvent(BaseModel):
    """Generic event payload shared across websocket consumers.

    Args:
        topic (EventTopic): Logical stream the event belongs to.
        event (str): Specific event identifier (e.g. notification.created).
        payload_version (str): Semantic version of the payload contract.
        payload (Dict[str, Any]): Concrete event data expected by the UI.
        recipient_ids (List[uuid.UUID]): Users that should receive the event.
        trace_id (str): Correlation identifier for observability.
        occurred_at (datetime): UTC timestamp for when the event happened.

    Examples:
        >>> event = BaseEvent(
        ...     topic=EventTopic.NOTIFICATIONS,
        ...     event="notification.created",
        ...     payload_version="1.0",
        ...     payload={"notification_id": "abc"},
        ...     recipient_ids=[uuid.uuid4()],
        ... )
        >>> event.topic
        <EventTopic.NOTIFICATIONS: 'notifications'>
    """

    model_config = ConfigDict(extra="allow")

    topic: EventTopic
    event: str
    payload_version: str = Field(default="1.0")
    payload: Dict[str, Any]
    recipient_ids: List[uuid.UUID] = Field(default_factory=list)
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def dump_json(self) -> str:
        """Serialize events into JSON strings ready for transports.

        Returns:
            str: Serialized JSON payload.

        Examples:
            >>> BaseEvent(
            ...     topic=EventTopic.NOTIFICATIONS,
            ...     event="notification.created",
            ...     payload_version="1.0",
            ...     payload={"notification_id": "abc"},
            ...     recipient_ids=[uuid.uuid4()],
            ... ).dump_json()
            '{"topic":"notifications",...}'
        """

        return self.model_dump_json()

    @classmethod
    def parse_raw(cls: Type["BaseEvent"], raw_message: str) -> "BaseEvent":
        """Deserialize JSON strings emitted by transports.

        Args:
            raw_message (str): Serialized event instance.

        Returns:
            BaseEvent: Parsed event matching the stored metadata.

        Raises:
            ValueError: If validation fails for the payload.

        Examples:
            >>> serialized = BaseEvent(
            ...     topic=EventTopic.NOTIFICATIONS,
            ...     event="notification.read",
            ...     payload_version="1.0",
            ...     payload={"id": "abc"},
            ... ).dump_json()
            >>> BaseEvent.parse_raw(serialized).event
            'notification.read'
        """

        return cls.model_validate_json(raw_message)

    @classmethod
    def from_message(cls, data: Any) -> "BaseEvent":
        """Parse flexible payloads that Redis pubsub may deliver.

        Args:
            data (Any): Raw value from Redis which may be bytes, str, or dict.

        Returns:
            BaseEvent: Parsed event instance.

        Examples:
            >>> BaseEvent.from_message({
            ...     "topic": "notifications",
            ...     "event": "notification.created",
            ...     "payload_version": "1.0",
            ...     "payload": {"id": "abc"},
            ... }).event
            'notification.created'
        """

        if isinstance(data, (bytes, bytearray)):
            return cls.parse_raw(data.decode())
        if isinstance(data, str):
            return cls.parse_raw(data)
        return cls.model_validate(data)


class NotificationEvent(BaseEvent):
    """Event emitted for notification lifecycle changes."""

    topic: EventTopic = Field(default=EventTopic.NOTIFICATIONS, frozen=True)


class ScrapeJobEvent(BaseEvent):
    """Event emitted for scrape job lifecycle updates."""

    topic: EventTopic = Field(default=EventTopic.SCRAPE_JOBS, frozen=True)


class TicketCommentEvent(BaseEvent):
    """Event emitted for ticket comment lifecycle changes (created, updated, deleted)."""

    topic: EventTopic = Field(default=EventTopic.TICKET_COMMENTS, frozen=True)
