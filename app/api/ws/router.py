"""FastAPI router exposing websocket endpoints."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocket, WebSocketDisconnect

from app.api.db.database import get_db
from app.api.ws.auth import authenticate_websocket_user
from app.api.ws.connection_manager import manager
from app.api.ws.exceptions import WebSocketException

router = APIRouter()


@router.websocket("/ws")
async def websocket_gateway(websocket: WebSocket, db: AsyncSession = Depends(get_db)) -> None:
    """Primary websocket endpoint for realtime notifications.

    Args:
        websocket (WebSocket): Incoming client connection.
        db (AsyncSession): Database session resolved via dependency injection.

    Returns:
        None

    Raises:
        WebSocketException: Propagated when authentication fails.

    Examples:
        >>> # handled internally by FastAPI
        >>> await websocket_gateway(websocket, db)
    """

    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing token")
        return
    try:
        user = await authenticate_websocket_user(token, db)
    except WebSocketException as exc:
        await websocket.close(code=exc.code, reason=exc.reason)
        return

    user_id: UUID = user.id
    await manager.connect(user_id, websocket)

    try:
        while True:
            message: Any = await websocket.receive_json()
            try:
                acknowledgement = await manager.handle_client_message(user_id, websocket, message)
                await websocket.send_json(acknowledgement)
            except ValueError as exc:
                await websocket.send_json({"type": "error", "detail": str(exc)})
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(user_id, websocket)
