"""Validated browser-to-host input events for ESPLink."""
from dataclasses import dataclass
from time import time


_ALLOWED_TYPES = {"key", "mouse"}
_MAX_TEXT = 64


@dataclass(frozen=True)
class InputEvent:
    """A normalized input event received from a streaming client."""

    type: str
    action: str
    data: dict
    created_at: float


def normalize_input(payload: object) -> InputEvent:
    """Validate and normalize one browser input event.

    This layer intentionally does not inject input into Windows. It provides
    a bounded protocol that a platform-specific input backend can consume.
    """
    if not isinstance(payload, dict):
        raise ValueError("Input event must be an object")
    event_type = str(payload.get("type", "")).strip().lower()
    action = str(payload.get("action", "")).strip().lower()
    if event_type not in _ALLOWED_TYPES:
        raise ValueError("Unsupported input event type")
    if not action or len(action) > _MAX_TEXT:
        raise ValueError("Input event action is invalid")

    raw_data = payload.get("data", {})
    if not isinstance(raw_data, dict):
        raise ValueError("Input event data must be an object")

    data: dict = {}
    for key, value in raw_data.items():
        key = str(key)
        if len(key) > _MAX_TEXT:
            raise ValueError("Input event data key is too long")
        if isinstance(value, (str, int, float, bool)) or value is None:
            if isinstance(value, str) and len(value) > _MAX_TEXT:
                raise ValueError("Input event data value is too long")
            data[key] = value
        else:
            raise ValueError("Input event data contains an unsupported value")

    return InputEvent(event_type, action, data, time())
