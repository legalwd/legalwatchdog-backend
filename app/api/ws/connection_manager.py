"""Connection manager that tracks websocket clients and their subscriptions."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Dict, Set
from uuid import UUID

from fastapi.websockets import WebSocket

from app.api.events.models import BaseEvent, EventTopic


class WebSocketConnectionManager:
    """Maintain websocket connections grouped by user and topic subscriptions."""

    def __init__(self) -> None:
        self._user_connections: Dict[UUID, Set[WebSocket]] = defaultdict(set)
        self._topic_subscribers: Dict[EventTopic, Dict[UUID, Set[WebSocket]]] = defaultdict(
            lambda: defaultdict(set)
        )
        self._lock = asyncio.Lock()

    async def connect(self, user_id: UUID, websocket: WebSocket) -> None:
        """Accept the websocket and store the live connection.

        Args:
            user_id (UUID): Owner of the websocket connection.
            websocket (WebSocket): FastAPI websocket instance.

        Returns:
            None

        Examples:
            >>> await manager.connect(user_id, websocket)
        """

        await websocket.accept()
        async with self._lock:
            self._user_connections[user_id].add(websocket)

    async def disconnect(self, user_id: UUID, websocket: WebSocket) -> None:
        """Remove a websocket from user and topic mappings.

        Args:
            user_id (UUID): Owner of the websocket connection.
            websocket (WebSocket): Connection to remove.

        Returns:
            None

        Examples:
            >>> await manager.disconnect(user_id, websocket)
        """

        async with self._lock:
            self._user_connections[user_id].discard(websocket)
            for topic in EventTopic:
                self._topic_subscribers[topic][user_id].discard(websocket)

    async def subscribe(self, user_id: UUID, websocket: WebSocket, topics: Set[EventTopic]) -> None:
        """Register the websocket to the provided topics.

        Args:
            user_id (UUID): Owner of the websocket connection.
            websocket (WebSocket): Connection requesting subscription.
            topics (Set[EventTopic]): Topics to subscribe to.

        Returns:
            None

        Examples:
            >>> await manager.subscribe(user_id, websocket, {EventTopic.NOTIFICATIONS})
        """

        async with self._lock:
            for topic in topics:
                self._topic_subscribers[topic][user_id].add(websocket)

    async def unsubscribe(
        self, user_id: UUID, websocket: WebSocket, topics: Set[EventTopic]
    ) -> None:
        """Remove the websocket from the supplied topics.

        Args:
            user_id (UUID): Owner of the websocket connection.
            websocket (WebSocket): Connection requesting removal.
            topics (Set[EventTopic]): Topics to unsubscribe from.

        Returns:
            None

        Examples:
            >>> await manager.unsubscribe(user_id, websocket, {EventTopic.NOTIFICATIONS})
        """

        async with self._lock:
            for topic in topics:
                self._topic_subscribers[topic][user_id].discard(websocket)

    async def send_event(self, event: BaseEvent) -> None:
        """Broadcast an event to all websockets subscribed to its topic.

        Args:
            event (BaseEvent): Event being transmitted.

        Returns:
            None

        Examples:
            >>> await manager.send_event(event)
        """

        topic = EventTopic(event.topic)
        subscribers = self._topic_subscribers[topic]
        payload = {
            "topic": topic.value,
            "event": event.event,
            "payload_version": event.payload_version,
            "payload": event.payload,
            "trace_id": event.trace_id,
            "occurred_at": event.occurred_at.isoformat(),
        }
        targets: list[tuple[UUID, WebSocket]] = []
        async with self._lock:
            if event.recipient_ids:
                for user_id in event.recipient_ids:
                    sockets = subscribers.get(user_id, set())
                    targets.extend([(user_id, socket) for socket in sockets])
            else:
                for user_id, sockets in subscribers.items():
                    targets.extend([(user_id, socket) for socket in sockets])
        await self._send_to_targets(targets, payload)

    async def handle_client_message(
        self, user_id: UUID, websocket: WebSocket, message: dict
    ) -> dict:
        """Handle subscribe or unsubscribe commands from clients.

        Args:
            user_id (UUID): Owner of the websocket connection.
            websocket (WebSocket): Connection that sent the message.
            message (dict): Parsed JSON payload containing the action.

        Returns:
            dict: Acknowledgement payload informing clients of success.

        Raises:
            ValueError: When an unsupported action is supplied.

        Examples:
            >>> await manager.handle_client_message(user_id, websocket, {
            ...     "action": "subscribe", "topics": ["notifications"]
            ... })
        """

        action = message.get("action")
        topics_payload = message.get("topics", [])
        topics = {EventTopic(topic) for topic in topics_payload}

        if action == "subscribe":
            await self.subscribe(user_id, websocket, topics)
            return {"type": "ack", "action": "subscribe", "topics": list(topics)}
        if action == "unsubscribe":
            await self.unsubscribe(user_id, websocket, topics)
            return {"type": "ack", "action": "unsubscribe", "topics": list(topics)}
        raise ValueError("Unsupported action")

    async def _send_to_targets(self, targets: list[tuple[UUID, WebSocket]], payload: dict) -> None:
        """Send payloads to each target while dropping closed sockets.

        Args:
            targets (list[tuple[UUID, WebSocket]]): Connections slated for delivery.
            payload (dict): JSON-serializable body.

        Returns:
            None

        Examples:
            >>> await manager._send_to_targets([websocket], {"event": "ping"})
        """

        to_remove: list[tuple[UUID, WebSocket]] = []
        for user_id, socket in targets:
            try:
                await socket.send_json(payload)
            except Exception:
                to_remove.append((user_id, socket))
        for user_id, socket in to_remove:
            await self.disconnect(user_id, socket)


manager = WebSocketConnectionManager()
