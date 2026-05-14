"""Helpers that convert ORM models into websocket-ready events."""

from __future__ import annotations

from typing import Iterable, List

from app.api.events.models import NotificationEvent, ScrapeJobEvent
from app.api.modules.v1.notifications.models.revision_notification import Notification
from app.api.modules.v1.notifications.schemas.notification_schema import NotificationResponse
from app.api.modules.v1.scraping.models.scrape_job import ScrapeJob
from app.api.modules.v1.scraping.schemas.scrape_job_schema import ScrapeJobResponse


def build_notification_events(
    notifications: Iterable[Notification],
    event_name: str = "notification.upserted",
) -> List[NotificationEvent]:
    """Convert notification models into websocket events.

    Args:
        notifications (Iterable[Notification]): Newly created or updated notifications.
        event_name (str, optional): Event identifier shared with the frontend. Defaults to
            "notification.upserted".

    Returns:
        List[NotificationEvent]: Serialized events grouped by notification.

    Raises:
        ValidationError: If the notification model cannot be serialized into the response schema.

    Examples:
        >>> notification_events = build_notification_events([notification])
        >>> notification_events[0].event
        'notification.upserted'
    """

    events: list[NotificationEvent] = []
    for notification in notifications:
        payload = NotificationResponse.model_validate(notification).model_dump(mode="json")
        events.append(
            NotificationEvent(
                event=event_name,
                payload=payload,
                recipient_ids=[notification.user_id],
            )
        )
    return events


def build_scrape_job_event(
    job: ScrapeJob,
    event_name: str = "scrape_job.updated",
) -> ScrapeJobEvent:
    """Transform scrape job instances into websocket events.

    Args:
        job (ScrapeJob): Persisted scrape job model.
        event_name (str, optional): Event identifier for the frontend. Defaults to
            "scrape_job.updated".

    Returns:
        ScrapeJobEvent: Event ready for publishing to Redis/websockets.

    Raises:
        ValidationError: If the scrape job fails to validate against the response schema.

    Examples:
        >>> scrape_event = build_scrape_job_event(job)
        >>> scrape_event.payload["id"] == str(job.id)
        True
    """

    payload = ScrapeJobResponse.model_validate(job).model_dump(mode="json")
    return ScrapeJobEvent(event=event_name, payload=payload)
