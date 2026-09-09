"""Regression tests for the WebRTC-facing HostAPI facade."""
import unittest
from unittest.mock import Mock

from host.api import HostAPI


class HostAPITests(unittest.TestCase):
    def test_logout_closes_session_peers_before_disconnect(self):
        signaling = Mock()
        host = Mock()
        api = HostAPI(host=host, signaling=signaling)

        result = api.logout("session-a")

        signaling.close_session.assert_called_once_with("session-a")
        host.sessions.disconnect.assert_called_once_with("session-a")
        self.assertEqual(result, {"ok": True, "closed_peers": signaling.close_session.return_value})

    def test_authorize_returns_new_session_details(self):
        host = Mock()
        host.authorize.return_value = {"authorized": True, "session_id": "session-123", "state": "connected"}
        api = HostAPI(host=host, signaling=Mock())

        result = api.authorize("code", client_id="phone")

        host.authorize.assert_called_once()
        self.assertTrue(result["authorized"])
        self.assertEqual(result["session_id"], "session-123")
        self.assertEqual(result["state"], "connected")


if __name__ == "__main__":
    unittest.main()
