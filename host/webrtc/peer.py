"""WebRTC peer lifecycle for the Windows host."""
from concurrent.futures import Future
import asyncio
import json
import threading

try:
    from aiortc import RTCPeerConnection, RTCConfiguration, RTCIceServer, RTCSessionDescription
    from aiortc.sdp import candidate_from_sdp
except ImportError:
    RTCPeerConnection = None
    RTCConfiguration = None
    RTCIceServer = None
    RTCSessionDescription = None
    candidate_from_sdp = None

from ..config import CAPTURE_FPS, ICE_SERVERS
from .desktop_audio import DesktopAudioTrack
from .desktop_video import DesktopVideoTrack
from .input import normalize_input
from .test_video import TestVideoTrack
from .windows_input import WindowsInputBackend


class WebRTCPeer:
    """Own an aiortc peer on a persistent asyncio event-loop thread."""

    def __init__(
        self,
        video_mode: str = "desktop",
        display_index: int = 0,
        input_enabled: bool = False,
        audio_enabled: bool = True,
    ) -> None:
        if RTCPeerConnection is None:
            raise RuntimeError(
                "aiortc is not installed. Install the streaming host dependencies before enabling real WebRTC media."
            )
        if video_mode not in {"desktop", "test", "none"}:
            raise ValueError("video_mode must be desktop, test, or none")
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._input_lock = threading.Lock()
        self._input_events: list[dict] = []
        self.closed = False
        self.video_mode = video_mode
        self.display_index = display_index
        self.audio_enabled = audio_enabled
        self.input_backend = WindowsInputBackend(enabled=input_enabled)
        self.video_track = None
        self.audio_track = None
        self.audio_error: str | None = None
        self._thread = threading.Thread(target=self._run_loop, name="ESPLink-WebRTC", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=2):
            raise RuntimeError("WebRTC event loop failed to start")
        try:
            self.connection = self._submit(self._create_connection()).result(timeout=10)
        except Exception:
            self.closed = True
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=2)
            raise

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._ready.set()
        self._loop.run_forever()
        self._loop.close()

    @staticmethod
    def _ice_configuration():
        servers = [RTCIceServer(**server) for server in ICE_SERVERS]
        return RTCConfiguration(iceServers=servers) if servers else None

    async def _create_connection(self):
        configuration = self._ice_configuration()
        connection = RTCPeerConnection(configuration=configuration) if configuration else RTCPeerConnection()

        @connection.on("datachannel")
        def on_datachannel(channel):
            if channel.label != "input":
                return

            @channel.on("message")
            def on_message(message):
                try:
                    if isinstance(message, bytes):
                        message = message.decode("utf-8")
                    event = normalize_input(json.loads(message))
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
                    return
                event_dict = {
                    "type": event.type,
                    "action": event.action,
                    "data": event.data,
                    "created_at": event.created_at,
                }
                with self._input_lock:
                    if len(self._input_events) >= 256:
                        self._input_events.pop(0)
                    self._input_events.append(event_dict)
                self.input_backend.handle(event)

        if self.video_mode == "desktop":
            self.video_track = DesktopVideoTrack(
                display_index=self.display_index,
                target_fps=CAPTURE_FPS,
            )
            connection.addTrack(self.video_track)
        elif self.video_mode == "test":
            self.video_track = TestVideoTrack()
            connection.addTrack(self.video_track)

        if self.audio_enabled:
            try:
                self.audio_track = DesktopAudioTrack()
            except RuntimeError as exc:
                self.audio_error = str(exc)
            else:
                connection.addTrack(self.audio_track)
        return connection

    def _submit(self, coroutine) -> Future:
        if self.closed:
            coroutine.close()
            raise RuntimeError("WebRTC peer is closed")
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop)

    async def _accept_offer(self, sdp: str) -> dict:
        offer = RTCSessionDescription(sdp=sdp, type="offer")
        await self.connection.setRemoteDescription(offer)
        answer = await self.connection.createAnswer()
        await self.connection.setLocalDescription(answer)
        description = self.connection.localDescription
        return {"type": description.type, "sdp": description.sdp}

    def accept_offer(self, sdp: str) -> dict:
        return self._submit(self._accept_offer(sdp)).result(timeout=15)

    @staticmethod
    def _candidate_from_payload(payload: dict):
        if not isinstance(payload, dict):
            raise ValueError("ICE candidate must be an object")
        candidate_sdp = str(payload.get("candidate", ""))
        if not candidate_sdp:
            return None
        if candidate_sdp.startswith("candidate:"):
            candidate_sdp = candidate_sdp[len("candidate:"):]
        candidate = candidate_from_sdp(candidate_sdp)
        candidate.sdpMid = payload.get("sdpMid")
        candidate.sdpMLineIndex = payload.get("sdpMLineIndex")
        return candidate

    async def _add_ice_candidate(self, payload: dict) -> None:
        candidate = self._candidate_from_payload(payload)
        if candidate is not None:
            await self.connection.addIceCandidate(candidate)

    def add_ice_candidate(self, payload: dict) -> None:
        self._submit(self._add_ice_candidate(payload)).result(timeout=10)

    def drain_input_events(self) -> list[dict]:
        with self._input_lock:
            events = list(self._input_events)
            self._input_events.clear()
        return events

    async def _stats(self) -> dict:
        report = await self.connection.getStats()
        with self._input_lock:
            queued_input = len(self._input_events)
        result = {
            "connection_state": self.connection.connectionState,
            "ice_connection_state": self.connection.iceConnectionState,
            "signaling_state": self.connection.signalingState,
            "ice_server_count": len(ICE_SERVERS),
            "input_events": queued_input,
            "input_backend": self.input_backend.status,
            "audio_capture": {"enabled": self.audio_enabled and self.audio_track is not None, "error": self.audio_error},
            "video": {},
            "audio": {},
        }
        for stat in report.values():
            kind = getattr(stat, "kind", None)
            if stat.type == "outbound-rtp" and kind in {"video", "audio"}:
                result[kind] = {
                    "packets_sent": getattr(stat, "packetsSent", 0),
                    "bytes_sent": getattr(stat, "bytesSent", 0),
                    "frames_encoded": getattr(stat, "framesEncoded", 0),
                }
        return result

    def stats(self) -> dict:
        return self._submit(self._stats()).result(timeout=5)

    async def _close(self) -> None:
        if self.video_track is not None:
            self.video_track.stop()
        if self.audio_track is not None:
            self.audio_track.stop()
        await self.connection.close()

    def close(self) -> None:
        if self.closed:
            return
        try:
            self._submit(self._close()).result(timeout=5)
        finally:
            self.closed = True
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=2)
