"""Transport-neutral request adapter for the ESPLink signaling relay."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .relay import SignalingRelay


@dataclass(frozen=True)
class RelayResponse:
    status: int
    body: dict[str, Any]


class RelayTransport:
    """Map JSON-style requests to the authenticated signaling relay.

    A future HTTP or WebSocket server can call ``handle`` without duplicating
    authentication, validation, or queue behavior.
    """

    def __init__(self, relay: SignalingRelay | None = None) -> None:
        self.relay = relay or SignalingRelay()

    def handle(self, action: str, payload: dict[str, Any] | None = None, token: str | None = None) -> RelayResponse:
        data = payload or {}
        try:
            if action == "register":
                peer = self.relay.register(
                    self._required(data, "client_id"),
                    self._required(data, "session_id"),
                    token,
                )
                return RelayResponse(201, {"peer_id": peer.peer_id})
            if action == "send":
                self.relay.send(
                    self._required(data, "peer_id"),
                    self._required(data, "session_id"),
                    self._message(data),
                    token,
                )
                return RelayResponse(202, {"ok": True})
            if action == "poll":
                messages = self.relay.poll(
                    self._required(data, "peer_id"),
                    self._required(data, "session_id"),
                    token,
                )
                return RelayResponse(200, {"messages": messages})
            if action == "close":
                self.relay.close(
                    self._required(data, "peer_id"),
                    self._required(data, "session_id"),
                    token,
                )
                return RelayResponse(200, {"ok": True})
            return RelayResponse(404, {"error": "unknown_action"})
        except PermissionError:
            return RelayResponse(401, {"error": "unauthorized"})
        except (KeyError, ValueError):
            return RelayResponse(400, {"error": "invalid_request"})
        except OverflowError:
            return RelayResponse(429, {"error": "queue_full"})

    @staticmethod
    def _required(payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} is required")
        return value.strip()

    @staticmethod
    def _message(payload: dict[str, Any]) -> dict[str, Any]:
        message = payload.get("message")
        if not isinstance(message, dict) or not message:
            raise ValueError("message must be a non-empty object")
        return message
