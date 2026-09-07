"""Hardware-independent WebRTC signaling session manager.

This module only exchanges signaling messages. It does not carry media and
therefore can be used by the simulator before a real WebRTC implementation is
attached to the Windows host.
"""

from dataclasses import dataclass, field
from secrets import token_urlsafe
from time import time


@dataclass
class PeerSession:
    peer_id: str
    client_id: str
    created_at: float = field(default_factory=time)
    messages: list[dict] = field(default_factory=list)
    closed: bool = False

    def queue(self, message: dict) -> None:
        if self.closed:
            raise ValueError("WebRTC session is closed")
        self.messages.append(message)

    def drain(self) -> list[dict]:
        messages = self.messages[:]
        self.messages.clear()
        return messages


class SignalingManager:
    def __init__(self) -> None:
        self.sessions: dict[str, PeerSession] = {}

    def create(self, client_id: str) -> PeerSession:
        peer_id = token_urlsafe(18)
        while peer_id in self.sessions:
            peer_id = token_urlsafe(18)
        session = PeerSession(peer_id=peer_id, client_id=client_id)
        self.sessions[peer_id] = session
        return session

    def get(self, peer_id: str) -> PeerSession:
        try:
            session = self.sessions[peer_id]
        except KeyError:
            raise KeyError("Unknown WebRTC peer") from None
        if session.closed:
            raise ValueError("WebRTC session is closed")
        return session

    def close(self, peer_id: str) -> None:
        session = self.sessions.get(peer_id)
        if session:
            session.closed = True
            session.messages.clear()
