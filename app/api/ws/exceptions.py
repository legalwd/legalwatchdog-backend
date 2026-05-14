"""Custom exceptions used by the websocket layer."""

from __future__ import annotations


class WebSocketException(Exception):
    """Lightweight websocket exception containing close information.

    Args:
        code (int): Websocket close status code.
        reason (str): Human-readable explanation for the closure.

    Examples:
        >>> raise WebSocketException(4401, "Invalid token")
        Traceback (most recent call last):
        ...
        WebSocketException: Invalid token
    """

    def __init__(self, code: int, reason: str) -> None:
        self.code = code
        self.reason = reason
        super().__init__(reason)
