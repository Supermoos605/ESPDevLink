"""Windows host configuration for ESPLink.

Keep user-editable host settings here. Environment variables take precedence,
so the same host can still be used with the local simulator.
"""
import os
import socket

DEFAULT_ESP32_URL = "http://steamlink.local"
DEFAULT_HEARTBEAT_SECONDS = 2
DEFAULT_COMPUTER_NAME = socket.gethostname()

ESP32_URL = os.environ.get("ESPLINK_ESP32", DEFAULT_ESP32_URL).rstrip("/")
COMPUTER_NAME = os.environ.get("ESPLINK_COMPUTER_NAME", DEFAULT_COMPUTER_NAME).strip() or DEFAULT_COMPUTER_NAME
HEARTBEAT_SECONDS = max(1, float(os.environ.get("ESPLINK_HEARTBEAT", DEFAULT_HEARTBEAT_SECONDS)))
ALLOW_CONNECTIONS = os.environ.get("ESPLINK_ALLOW_CONNECTIONS", "1").lower() not in {"0", "false", "no", "off"}
AUTHORIZATION_CODE = os.environ.get("ESPLINK_AUTH_CODE", "").strip()

if not AUTHORIZATION_CODE:
    raise RuntimeError(
        "ESPLINK_AUTH_CODE is not set. Set it to the same value as the ESP32 ACCESS_CODE."
    )

# Friendly name -> executable. Add games here as they are supported.
KNOWN_GAMES = {
    "steamwebhelper.exe": "Steam",
}
