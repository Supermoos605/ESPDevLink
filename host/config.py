"""Windows host configuration for ESPLink.

Keep user-editable host settings here. Environment variables take precedence,
so the same host can still be used with the local simulator.
"""
import json
import os
import socket

DEFAULT_ESP32_URL = "http://steamlink.local"
DEFAULT_HEARTBEAT_SECONDS = 2
DEFAULT_COMPUTER_NAME = socket.gethostname()
DEFAULT_CAPTURE_FPS = 30

ESP32_URL = os.environ.get("ESPLINK_ESP32", DEFAULT_ESP32_URL).rstrip("/")
_DEFAULT_CORS_ORIGIN = ESP32_URL
CORS_ORIGINS = [item.strip().rstrip("/") for item in os.environ.get("ESPLINK_CORS_ORIGINS", _DEFAULT_CORS_ORIGIN).split(",") if item.strip()]
COMPUTER_NAME = os.environ.get("ESPLINK_COMPUTER_NAME", DEFAULT_COMPUTER_NAME).strip() or DEFAULT_COMPUTER_NAME
HEARTBEAT_SECONDS = max(1, float(os.environ.get("ESPLINK_HEARTBEAT", DEFAULT_HEARTBEAT_SECONDS)))
CAPTURE_FPS = max(1, int(os.environ.get("ESPLINK_CAPTURE_FPS", DEFAULT_CAPTURE_FPS)))
ALLOW_CONNECTIONS = os.environ.get("ESPLINK_ALLOW_CONNECTIONS", "1").lower() not in {"0", "false", "no", "off"}
try:
    from .local_config import AUTHORIZATION_CODE as LOCAL_AUTHORIZATION_CODE
except ImportError:
    try:
        from local_config import AUTHORIZATION_CODE as LOCAL_AUTHORIZATION_CODE
    except ImportError:
        LOCAL_AUTHORIZATION_CODE = ""

AUTHORIZATION_CODE = os.environ.get("ESPLINK_AUTH_CODE", LOCAL_AUTHORIZATION_CODE).strip()

if not AUTHORIZATION_CODE:
    raise RuntimeError(
        "ESPLINK_AUTH_CODE is not set. Set it to the same value as the ESP32 ACCESS_CODE."
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
