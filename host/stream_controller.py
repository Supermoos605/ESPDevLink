"""Coordinate WebRTC peers and the ESPLink streaming package."""
from .webrtc import HostSignaling, WebRTCPeer
from .streaming import StreamRuntime, HostMediaRegistry, negotiate_profile, StreamConfig, EncoderProfile


class StreamController:
    def __init__(self, config=None, encoder=None) -> None:
        self.signaling = HostSignaling()
        self.runtime = StreamRuntime(config or StreamConfig(), encoder or EncoderProfile())
        self.media = HostMediaRegistry()
        self.media.configure_defaults()
        self.webrtc = {}

    def create_peer(self, session_id: str):
        peer = self.signaling.create_peer(session_id)
        try:
            self.webrtc[peer.peer_id] = WebRTCPeer()
        except RuntimeError:
            pass
        return peer

    async def accept_offer(self, peer_id: str, session_id: str, sdp: str) -> dict:
        peer = self.signaling.get_peer(peer_id, session_id)
        real_peer = self.webrtc.get(peer_id)
        if real_peer is None:
            raise RuntimeError("WebRTC media dependencies are not installed")
        answer = await real_peer.accept_offer(sdp)
        peer.receive({"type": "offer", "sdp": sdp})
        return answer

    def handle_signal(self, peer_id: str, session_id: str, message: dict) -> dict:
        peer = self.signaling.get_peer(peer_id, session_id)
        peer.receive(message)
        return {"peer_id": peer.peer_id, "state": peer.state}

    async def close_peer(self, peer_id: str, session_id: str) -> None:
        self.signaling.get_peer(peer_id, session_id)
        real_peer = self.webrtc.pop(peer_id, None)
        if real_peer is not None:
            await real_peer.close()
        self.signaling.close(peer_id, session_id)

    def start_stream(self) -> None:
        self.media.pipeline.start()
        self.runtime.start()

    def stop_stream(self) -> None:
        self.media.pipeline.stop()
        self.runtime.stop()

    def negotiate(self, client=None) -> dict:
        return negotiate_profile(self.runtime.config, self.runtime.encoder, client)

    def status(self) -> dict:
        return {"media": self.media.status(), "runtime": self.runtime.status(),
                "peers": len(self.signaling.peers), "webrtc_peers": len(self.webrtc)}
