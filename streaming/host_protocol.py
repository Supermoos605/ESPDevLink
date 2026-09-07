"""Shared ESPLink streaming protocol constants and helpers.

This module contains protocol-level definitions only. It intentionally does
not start a server, capture the desktop, inject input, or launch games.
"""

from dataclasses import dataclass, asdict
from typing import Any, Dict
import json

PROTOCOL_VERSION = 1
STREAM_STATES = ("Offline", "Ready", "Connecting", "Streaming", "Stopping", "Error")
MESSAGE_TYPES = (
    "hello",
    "hello_ack",
    "stream_request",
    "stream_accept",
    "stream_stop",
    "stream_state",
    "error",
)


@dataclass
class HostInfo:
    name: str
    ip: str
    game: str = ""
    stream: str = "Ready"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def make_message(message_type: str, **payload: Any) -> Dict[str, Any]:
    if message_type not in MESSAGE_TYPES:
        raise ValueError(f"Unknown ESPLink message type: {message_type}")
    return {
        "protocol": PROTOCOL_VERSION,
        "type": message_type,
        **payload,
    }


def encode_message(message_type: str, **payload: Any) -> bytes:
    return (json.dumps(make_message(message_type, **payload), separators=(",", ":")) + "\n").encode("utf-8")


def decode_message(raw: bytes) -> Dict[str, Any]:
    message = json.loads(raw.decode("utf-8"))
    if message.get("protocol") != PROTOCOL_VERSION:
        raise ValueError("Unsupported ESPLink protocol version")
    if message.get("type") not in MESSAGE_TYPES:
        raise ValueError("Unknown ESPLink message type")
    return message
