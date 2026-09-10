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

    def test_signal_peer_uses_atomic_signaling_result(self):
        signaling = Mock()
        signaling.signal_result.return_value = {
            "peer_id": "peer-123",
            "state": "connected",
            "outbound": [{"type": "answer", "sdp": "answer"}],
        }
        api = HostAPI(host=Mock(), signaling=signaling)
        message = {"type": "offer", "sdp": "offer"}

        result = api.signal_peer("peer-123", "session-a", message)

        signaling.signal_result.assert_called_once_with("peer-123", "session-a", message)
        signaling.signal.assert_not_called()
        self.assertEqual(result, signaling.signal_result.return_value)


if __name__ == "__main__":
    unittest.main()
