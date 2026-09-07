"""Tests for the optional Windows input backend."""
import os
import unittest
from unittest.mock import patch

from host.webrtc.input import normalize_input
from host.webrtc.windows_input import WindowsInputBackend


class WindowsInputBackendTests(unittest.TestCase):
    def test_backend_is_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ESPLINK_INPUT_ENABLED", None)
            backend = WindowsInputBackend()
        self.assertFalse(backend.enabled)
        self.assertFalse(backend.handle(normalize_input({"type": "key", "action": "down", "data": {"code": "KeyW"}})))

    def test_status_exposes_platform_and_capabilities(self):
        backend = WindowsInputBackend(enabled=True)
        status = backend.status
        self.assertIn("enabled", status)
        self.assertIn("platform_supported", status)
        self.assertFalse(status["gamepad"])
        if not backend.platform_supported:
            self.assertFalse(status["enabled"])


if __name__ == "__main__":
    unittest.main()
