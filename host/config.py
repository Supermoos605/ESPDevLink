"""Windows host configuration for ESPLink.

Keep user-editable host settings here. Environment variables take precedence,
so the same host can still be used with the local simulator.
"""
import json
import os
import socket
import sys
from pathlib import Path

# Allow host scripts launched from the host/ directory to import the shared
# private configuration stored in the repository-level include/ directory.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

DEFAULT_ESP32_URL = "http://steamlink.local"
DEFAULT_HEARTBEAT_SECONDS = 2
DEFAULT_COMPUTER_NAME = socket.gethostname()
DEFAULT_CAPTURE_FPS = 30
DEFAULT_VIDEO_STATS_INTERVAL = 5
DEFAULT_VIDEO_MAX_BITRATE = 0
DEFAULT_VIDEO_MAX_WIDTH = 0
DEFAULT_VIDEO_MAX_HEIGHT = 0

ESP32_URL = os.environ.get("ESPLINK_ESP32", DEFAULT_ESP32_URL).rstrip("/")
_DEFAULT_CORS_ORIGIN = ESP32_URL
CORS_ORIGINS = [item.strip().rstrip("/") for item in os.environ.get("ESPLINK_CORS_ORIGINS", _DEFAULT_CORS_ORIGIN).split(",") if item.strip()]
COMPUTER_NAME = os.environ.get("ESPLINK_COMPUTER_NAME", DEFAULT_COMPUTER_NAME).strip() or DEFAULT_COMPUTER_NAME
HEARTBEAT_SECONDS = max(1, float(os.environ.get("ESPLINK_HEARTBEAT", DEFAULT_HEARTBEAT_SECONDS)))
CAPTURE_FPS = max(1, int(os.environ.get("ESPLINK_CAPTURE_FPS", DEFAULT_CAPTURE_FPS)))
VIDEO_STATS_INTERVAL = max(1, float(os.environ.get("ESPLINK_VIDEO_STATS_INTERVAL", DEFAULT_VIDEO_STATS_INTERVAL)))
VIDEO_MAX_BITRATE = max(0, int(os.environ.get("ESPLINK_VIDEO_MAX_BITRATE", DEFAULT_VIDEO_MAX_BITRATE)))
VIDEO_MAX_WIDTH = max(0, int(os.environ.get("ESPLINK_VIDEO_MAX_WIDTH", DEFAULT_VIDEO_MAX_WIDTH)))
VIDEO_MAX_HEIGHT = max(0, int(os.environ.get("ESPLINK_VIDEO_MAX_HEIGHT", DEFAULT_VIDEO_MAX_HEIGHT)))
ALLOW_CONNECTIONS = os.environ.get("ESPLINK_ALLOW_CONNECTIONS", "1").lower() not in {"0", "false", "no", "off"}
try:
    from include.espdevlink_secrets import (
        ACCESS_CODE as LOCAL_ACCESS_CODE,
        KEYVAL_KEY as LOCAL_KEYVAL_KEY,
    )
except ImportError:
    LOCAL_ACCESS_CODE = ""
    LOCAL_KEYVAL_KEY = ""

AUTHORIZATION_CODE = os.environ.get("ESPLINK_AUTH_CODE", LOCAL_ACCESS_CODE).strip()
KEYVAL_KEY = os.environ.get("ESPDEVLINK_KEYVAL_KEY", LOCAL_KEYVAL_KEY).strip()

if not AUTHORIZATION_CODE:
    raise RuntimeError(
        "Set ACCESS_CODE in include.espdevlink_secrets.py or ESPLINK_AUTH_CODE."
    )


# Free public STUN servers used for ICE candidate discovery by default.
# STUN does not relay media; it only helps peers discover their public-facing
# NAT addresses. Set ESPLINK_ICE_SERVERS explicitly to replace these defaults.
DEFAULT_ICE_SERVERS = [
    {"urls": ["stun:stun.l.google.com:19302"]},
    {"urls": ["stun:stun.cloudflare.com:3478"]},
]

def _load_ice_servers() -> list[dict]:
    """Load optional STUN/TURN servers from ESPLINK_ICE_SERVERS.

    The value is a JSON array, for example:
    [{"urls": "stun:stun.l.google.com:19302"}]
    """
    raw = os.environ.get("ESPLINK_ICE_SERVERS", "").strip()
    if not raw:
        return [dict(server) for server in DEFAULT_ICE_SERVERS]
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("ESPLINK_ICE_SERVERS must contain valid JSON") from exc
    if not isinstance(value, list):
        raise RuntimeError("ESPLINK_ICE_SERVERS must be a JSON array")
    for server in value:
        if not isinstance(server, dict) or not server.get("urls"):
            raise RuntimeError("Each ICE server must be an object containing urls")
    return value


ICE_SERVERS = _load_ice_servers()

# Friendly name -> executable. Add games here as they are supported.
KNOWN_GAMES = {
    "steamwebhelper.exe": "Steam",
}
