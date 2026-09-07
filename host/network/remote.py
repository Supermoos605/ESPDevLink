"""Remote signaling configuration for ESPLink.

This module only parses configuration. It does not open sockets or expose the
Windows host directly to the public internet.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class RemoteConfig:
    enabled: bool
    signaling_url: str | None
    access_token: str | None


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _valid_signaling_url(value: str | None) -> str | None:
    if not value:
        return None
    url = value.strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "wss"} or not parsed.netloc:
        raise ValueError("ESPLINK_REMOTE_SIGNALING_URL must use https:// or wss://")
    return url


def load_remote_config(environ: dict[str, str] | None = None) -> RemoteConfig:
    values = os.environ if environ is None else environ
    signaling_url = _valid_signaling_url(values.get("ESPLINK_REMOTE_SIGNALING_URL"))
    access_token = values.get("ESPLINK_REMOTE_ACCESS_TOKEN", "").strip() or None
    enabled = _truthy(values.get("ESPLINK_REMOTE_ENABLED"))
    if enabled and signaling_url is None:
        raise ValueError("Remote mode requires ESPLINK_REMOTE_SIGNALING_URL")
    return RemoteConfig(enabled, signaling_url, access_token)
