"""Windows-host-side WebRTC signaling and peer lifecycle."""
from dataclasses import dataclass, field
import os
from secrets import token_urlsafe
from time import time

from .peer import WebRTCPeer


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off", ""}


@dataclass
class HostPeer:
    peer_id: str
    session_id: str
    created_at: float = field(default_factory=time)
    state: str = "waiting"
    outbound: list[dict] = field(default_factory=list)
    rtc: WebRTCPeer | None = field(default=None, repr=False)

    def send(self, message: dict) -> None:
        if self.state == "closed":
            raise ValueError("Peer is closed")
        self.outbound.append(message)

    def receive(self, message: dict) -> None:
        if self.state == "closed":
            raise ValueError("Peer is closed")
        message_type = message.get("type")
        if message_type == "offer":
            self.state = "negotiating"
        elif message_type == "answer":
            self.state = "connected"


class HostSignaling:
    def __init__(self, enable_rtc: bool = True, video_mode: str = "desktop", input_enabled: bool | None = None) -> None:
        self.peers: dict[str, HostPeer] = {}
        self.enable_rtc = enable_rtc
        self.video_mode = video_mode
        self.input_enabled = _env_bool("ESPLINK_INPUT_ENABLED") if input_enabled is None else bool(input_enabled)

    def create_peer(self, session_id: str, video_mode: str | None = None) -> HostPeer:
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must be a non-empty string")
        peer_id = token_urlsafe(18)
        while peer_id in self.peers:
            peer_id = token_urlsafe(18)
        mode = video_mode or self.video_mode
        if mode not in {"desktop", "test", "none"}:
            raise ValueError("video_mode must be desktop, test, or none")
        rtc = None
        if self.enable_rtc:
            try:
                rtc = WebRTCPeer(video_mode=mode, input_enabled=self.input_enabled)
            except RuntimeError as exc:
                print(f"[WebRTC] Peer initialization failed: {exc}")
                rtc = None
        peer = HostPeer(peer_id=peer_id, session_id=session_id.strip(), rtc=rtc)
        self.peers[peer_id] = peer
        return peer

    def get_peer(self, peer_id: str, session_id: str) -> HostPeer:
        peer = self.peers.get(peer_id)
        if peer is None or peer.session_id != session_id:
            raise KeyError("Unknown WebRTC peer")
        if peer.state == "closed":
            raise ValueError("Peer is closed")
        return peer

    def signal(self, peer_id: str, session_id: str, message: dict) -> HostPeer:
        peer = self.get_peer(peer_id, session_id)
        if not isinstance(message, dict) or not message:
            raise ValueError("message must be a non-empty object")
        message_type = message.get("type")
        if message_type == "offer":
            sdp = message.get("sdp")
            if not isinstance(sdp, str) or not sdp.strip():
                raise ValueError("offer sdp must be a non-empty string")
        elif message_type == "ice-candidate":
            candidate = message.get("candidate")
            if not isinstance(candidate, dict):
                raise ValueError("ICE candidate must be an object")
            # Browsers send an empty candidate object to mark the end of
            # trickle ICE. The peer layer treats it as a no-op.
        peer.receive(message)

        if message_type == "offer" and peer.rtc is not None:
            try:
                answer = peer.rtc.accept_offer(message["sdp"])
            except Exception as exc:
                peer.state = "error"
                print(f"[WebRTC] Offer negotiation failed: {exc!r}")
                peer.send({"type": "error", "code": "webrtc_negotiation_failed", "message": "WebRTC negotiation failed. Check the host terminal for details."})
            else:
                peer.send(answer)
                peer.state = "connected"
        elif message_type == "ice-candidate" and peer.rtc is not None:
            try:
                peer.rtc.add_ice_candidate(message["candidate"])
            except Exception as exc:
                print(f"[WebRTC] ICE candidate rejected: {exc!r}")
                peer.send({"type": "error", "code": "webrtc_ice_failed", "message": "WebRTC ICE candidate was rejected. Check the host terminal for details."})
        elif message_type == "offer" and peer.rtc is None:
            peer.state = "error"
            peer.send({"type": "error", "code": "webrtc_unavailable", "message": "WebRTC peer initialization failed. Check the host terminal for the actual error."})
        return peer

    def stats(self, peer_id: str, session_id: str) -> dict:
        peer = self.get_peer(peer_id, session_id)
        if peer.rtc is None:
            return {"peer_id": peer.peer_id, "state": peer.state, "webrtc": False}
        return {"peer_id": peer.peer_id, "state": peer.state, "webrtc": True, "stats": peer.rtc.stats()}

    def close(self, peer_id: str, session_id: str) -> None:
        peer = self.get_peer(peer_id, session_id)
        self._close_peer(peer)
        self.peers.pop(peer_id, None)

    def _close_peer(self, peer: HostPeer) -> None:
        if peer.rtc is not None:
            peer.rtc.close()
            peer.rtc = None
        peer.state = "closed"
        peer.outbound.clear()

    def close_session(self, session_id: str) -> int:
        """Close and remove every WebRTC peer owned by a client session."""
        closed = 0
        for peer_id, peer in list(self.peers.items()):
            if peer.session_id != session_id:
                continue
            self._close_peer(peer)
            self.peers.pop(peer_id, None)
            closed += 1
        return closed

    def close_all(self) -> None:
        for peer in list(self.peers.values()):
            self._close_peer(peer)
        self.peers.clear()
