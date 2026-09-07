"""Application API for the ESPLink Windows host.

This module keeps HTTP routing thin and makes host operations reusable by
both the real HTTP server and the local simulator.
"""
import json
import os
from uuid import uuid4

from .config import AUTHORIZATION_CODE
from .games.service import GameService
from .host_core import ESPLinkHost
from .webrtc.signaling import HostSignaling


class HostAPI:
    def __init__(
        self,
        host: ESPLinkHost | None = None,
        games: GameService | None = None,
        signaling: HostSignaling | None = None,
    ) -> None:
        self.host = host or ESPLinkHost(AUTHORIZATION_CODE)
        self.games = games or self.host.games
        self.signaling = signaling or HostSignaling()

    def status(self) -> dict:
        return self.host.status()

    def health(self) -> dict:
        return {"ok": True, "service": "ESPLink Windows Host"}

    def authorize(self, code: str, client_id: str = "browser") -> dict:
        session_id = uuid4().hex
        return self.host.authorize(code, session_id, client_id)

    def logout(self, session_id: str) -> dict:
        closed_peers = self.signaling.close_session(session_id)
        self.host.sessions.disconnect(session_id)
        return {"ok": True, "closed_peers": closed_peers}

    def list_games(self) -> list[dict]:
        return self.games.list()

    def launch_game(self, game_id: str) -> dict:
        return self.host.launch_game(game_id)

    def stop_game(self, game_id: str) -> dict:
        return self.host.stop_game(game_id)

    def start_stream(self) -> dict:
        self.host.start_stream()
        return {"ok": True, "status": self.host.status()}

    def stop_stream(self) -> dict:
        self.host.stop_stream()
        return {"ok": True, "status": self.host.status()}

    @staticmethod
    def _ice_server(value: object) -> dict | None:
        if isinstance(value, str):
            urls = [item.strip() for item in value.split(",") if item.strip()]
            return {"urls": urls} if urls else None
        if not isinstance(value, dict):
            return None
        urls = value.get("urls")
        if isinstance(urls, str):
            urls = [item.strip() for item in urls.split(",") if item.strip()]
        if not isinstance(urls, list):
            return None
        clean_urls = [item.strip() for item in urls if isinstance(item, str) and item.strip()]
        if not clean_urls:
            return None
        result = {"urls": clean_urls}
        for key in ("username", "credential"):
            item = value.get(key)
            if isinstance(item, str) and item:
                result[key] = item
        return result

    def webrtc_config(self) -> dict:
        """Return browser ICE configuration from environment variables.

        ``ESPLINK_ICE_SERVERS`` accepts a JSON array of RTCIceServer-like
        objects, allowing authenticated STUN/TURN entries. The older
        ``ESPLINK_STUN_URL`` comma-separated variable remains supported.
        """
        servers: list[dict] = []
        raw_json = os.environ.get("ESPLINK_ICE_SERVERS", "").strip()
        if raw_json:
            try:
                values = json.loads(raw_json)
            except json.JSONDecodeError as exc:
                raise ValueError("ESPLINK_ICE_SERVERS must be valid JSON") from exc
            if not isinstance(values, list):
                raise ValueError("ESPLINK_ICE_SERVERS must be a JSON array")
            for value in values:
                server = self._ice_server(value)
                if server is not None:
                    servers.append(server)

        if not servers:
            legacy = self._ice_server(os.environ.get("ESPLINK_STUN_URL", ""))
            if legacy is not None:
                servers.append(legacy)
        return {"ice_servers": servers}

    def create_peer(self, session_id: str, video_mode: str | None = None) -> dict:
        peer = self.signaling.create_peer(session_id, video_mode=video_mode)
        result = {"peer_id": peer.peer_id, "state": peer.state, "webrtc": peer.rtc is not None}
        if peer.rtc is not None:
            result["input"] = peer.rtc.input_backend.status
            result["audio"] = {
                "enabled": peer.rtc.audio_track is not None,
                "error": peer.rtc.audio_error,
            }
        else:
            result["input"] = {"enabled": False, "platform_supported": False, "keyboard": False, "mouse": False, "gamepad": False}
            result["audio"] = {"enabled": False, "error": "WebRTC unavailable"}
        return result

    def signal_peer(self, peer_id: str, session_id: str, message: dict) -> dict:
        peer = self.signaling.signal(peer_id, session_id, message)
        return {"peer_id": peer.peer_id, "state": peer.state, "outbound": list(peer.outbound)}

    def close_peer(self, peer_id: str, session_id: str) -> dict:
        self.signaling.close(peer_id, session_id)
        return {"peer_id": peer_id, "closed": True}
