"""Authenticated, in-memory signaling relay primitives.

The relay is transport-agnostic: an HTTP/WebSocket adapter can call these
methods later without changing the host-side signaling model.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from secrets import token_urlsafe
from time import time
from typing import Mapping


@dataclass
class RelayPeer:
    peer_id: str
    client_id: str
    session_id: str
    created_at: float = field(default_factory=time)
    queue: list[dict] = field(default_factory=list)


class SignalingRelay:
    """Small authenticated broker for offers, answers, and ICE candidates."""

    def __init__(self, access_token: str | None = None, max_queue: int = 128) -> None:
        if max_queue < 1:
            raise ValueError("max_queue must be positive")
        self.access_token = access_token
        self.max_queue = max_queue
        self.peers: dict[str, RelayPeer] = {}

    def _authorize(self, token: str | None) -> None:
        if self.access_token is not None and token != self.access_token:
            raise PermissionError("Invalid signaling access token")

    @staticmethod
    def _text(value: object, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string")
        return value.strip()

    def register(self, client_id: str, session_id: str, token: str | None = None) -> RelayPeer:
        self._authorize(token)
        client_id = self._text(client_id, "client_id")
        session_id = self._text(session_id, "session_id")
        peer_id = token_urlsafe(18)
        while peer_id in self.peers:
            peer_id = token_urlsafe(18)
        peer = RelayPeer(peer_id, client_id, session_id)
        self.peers[peer_id] = peer
        return peer

    def send(
        self,
        peer_id: str,
        session_id: str,
        message: Mapping[str, object],
        token: str | None = None,
    ) -> None:
        self._authorize(token)
        peer = self._get(peer_id, session_id)
        if not isinstance(message, Mapping) or not message:
            raise ValueError("message must be a non-empty mapping")
        if len(peer.queue) >= self.max_queue:
            raise OverflowError("Signaling peer queue is full")
        peer.queue.append(dict(message))

    def poll(self, peer_id: str, session_id: str, token: str | None = None) -> list[dict]:
        self._authorize(token)
        peer = self._get(peer_id, session_id)
        messages = list(peer.queue)
        peer.queue.clear()
        return messages

    def close(self, peer_id: str, session_id: str, token: str | None = None) -> None:
        self._authorize(token)
        self._get(peer_id, session_id)
        self.peers.pop(peer_id, None)

    def _get(self, peer_id: str, session_id: str) -> RelayPeer:
        peer = self.peers.get(peer_id)
        if peer is None or peer.session_id != session_id:
            raise KeyError("Unknown signaling peer")
        return peer
