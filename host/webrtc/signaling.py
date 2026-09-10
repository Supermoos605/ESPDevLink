"""Windows-host-side WebRTC signaling and peer lifecycle."""
from dataclasses import dataclass, field
import os
from secrets import token_urlsafe
from threading import RLock
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
    pending_ice: list[dict] = field(default_factory=list)
    remote_description_set: bool = False
    rtc: WebRTCPeer | None = field(default=None, repr=False)

    def send(self, message: dict) -> None:
        if self.state == "closed":
            raise ValueError("Peer is closed")
        self.outbound.append(message)

    def receive(self, message: dict) -> None:
        if self.state == "closed":
            raise ValueError("Peer is closed")
        if not isinstance(message, dict) or not message:
            raise ValueError("message must be a non-empty object")
        message_type = message.get("type")
        if message_type == "offer":
            self.state = "negotiating"
        elif message_type == "answer":
            self.state = "connected"


class HostSignaling:
    """Thread-safe signaling state for the HTTP server.

    Safari/iPadOS can emit ICE candidates immediately after setting the local
    description. Because the HTTP server handles requests concurrently, an
    ICE request can otherwise race the offer request. Candidates are therefore
    queued until the remote offer has been applied.
    """

    def __init__(self, enable_rtc: bool = True, video_mode: str = "desktop", input_enabled: bool | None = None) -> None:
        self.peers: dict[str, HostPeer] = {}
        self.enable_rtc = enable_rtc
        self.video_mode = video_mode
        self.input_enabled = _env_bool("ESPLINK_INPUT_ENABLED") if input_enabled is None else bool(input_enabled)
        self._lock = RLock()

    def create_peer(self, session_id: str, video_mode: str | None = None) -> HostPeer:
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must be a non-empty string")
        session_id = session_id.strip()
        mode = video_mode or self.video_mode
        if mode not in {"desktop", "test", "none"}:
            raise ValueError("video_mode must be desktop, test, or none")
        with self._lock:
            self.close_session(session_id)
            peer_id = token_urlsafe(18)
            while peer_id in self.peers:
                peer_id = token_urlsafe(18)
            rtc = None
            if self.enable_rtc:
                try:
                    rtc = WebRTCPeer(video_mode=mode, input_enabled=self.input_enabled)
                except RuntimeError as exc:
                    print(f"[WebRTC] Peer initialization failed: {exc}")
                    raise RuntimeError(f"WebRTC peer initialization failed: {exc}") from exc
            peer = HostPeer(peer_id=peer_id, session_id=session_id, rtc=rtc)
            self.peers[peer_id] = peer
            return peer

    def get_peer(self, peer_id: str, session_id: str) -> HostPeer:
        with self._lock:
            peer = self.peers.get(peer_id)
            if peer is None or peer.session_id != session_id:
                raise KeyError("Unknown WebRTC peer")
            if peer.state == "closed":
                raise ValueError("Peer is closed")
            return peer

    def peers_for_session(self, session_id: str) -> list[HostPeer]:
        """Return active peers owned by a session without exposing other sessions."""
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must be a non-empty string")
        with self._lock:
            return [peer for peer in self.peers.values() if peer.session_id == session_id.strip() and peer.state != "closed"]

    def signal(self, peer_id: str, session_id: str, message: dict) -> HostPeer:
        with self._lock:
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
                if peer.rtc is not None and not peer.remote_description_set:
                    peer.pending_ice.append(candidate)
                    return peer
            peer.receive(message)
            if message_type == "offer" and peer.rtc is not None:
                try:
                    answer = peer.rtc.accept_offer(message["sdp"])
                    peer.remote_description_set = True
                except Exception as exc:
                    # A failed offer must not leave the capture/RTC peer alive.
                    # Safari can immediately retry the session; keeping the failed
                    # peer around leaves DXGI capture running and causes the next
                    # attempt to hit "Capture is already running".
                    print(f"[WebRTC] Offer negotiation failed: {exc!r}")
                    self._close_peer(peer)
                    peer.state = "error"
                    peer.send({"type": "error", "code": "webrtc_negotiation_failed", "message": "WebRTC negotiation failed. Check the host terminal for details."})
                else:
                    peer.send(answer)
                    peer.state = "connected"
                    pending = list(peer.pending_ice)
                    peer.pending_ice.clear()
                    for candidate in pending:
                        try:
                            peer.rtc.add_ice_candidate(candidate)
                        except Exception as exc:
                            print(f"[WebRTC] Queued ICE candidate rejected: {exc!r}")
                            peer.send({"type": "error", "code": "webrtc_ice_failed", "message": "WebRTC ICE candidate was rejected. Check the host terminal for details."})
                            break
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

    def signal_result(self, peer_id: str, session_id: str, message: dict) -> dict:
        """Signal a peer and snapshot its outbound queue under one lock."""
        with self._lock:
            peer = self.signal(peer_id, session_id, message)
            return {"peer_id": peer.peer_id, "state": peer.state, "outbound": list(peer.outbound)}

    def drain_outbound(self, peer_id: str, session_id: str) -> list[dict]:
        """Atomically return and clear queued messages for a peer."""
        with self._lock:
            peer = self.get_peer(peer_id, session_id)
            messages = list(peer.outbound)
            peer.outbound.clear()
            return messages

    def stats(self, peer_id: str, session_id: str) -> dict:
        with self._lock:
            peer = self.get_peer(peer_id, session_id)
            if peer.rtc is None:
                return {"peer_id": peer.peer_id, "state": peer.state, "webrtc": False}
            return {"peer_id": peer.peer_id, "state": peer.state, "webrtc": True, "stats": peer.rtc.stats()}

    def close(self, peer_id: str, session_id: str) -> None:
        with self._lock:
            peer = self.get_peer(peer_id, session_id)
            self._close_peer(peer)
            self.peers.pop(peer_id, None)

    def _close_peer(self, peer: HostPeer) -> None:
        try:
            if peer.rtc is not None:
                peer.rtc.close()
        except Exception as exc:
            print(f"[WebRTC] Peer cleanup failed: {exc!r}")
        finally:
            peer.rtc = None
            peer.state = "closed"
            peer.pending_ice.clear()
            peer.remote_description_set = False
            peer.outbound.clear()

    def close_session(self, session_id: str) -> int:
        """Close and remove every WebRTC peer owned by a client session."""
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must be a non-empty string")
        with self._lock:
            closed = 0
            for peer_id, peer in list(self.peers.items()):
                if peer.session_id != session_id.strip():
                    continue
                self._close_peer(peer)
                self.peers.pop(peer_id, None)
                closed += 1
            return closed

    def close_all(self) -> None:
        with self._lock:
            for peer in list(self.peers.values()):
                self._close_peer(peer)
            self.peers.clear()
