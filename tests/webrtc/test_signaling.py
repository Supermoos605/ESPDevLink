"""Regression tests for host-side WebRTC signaling."""
import os
import unittest
from unittest.mock import patch

from host.webrtc.signaling import HostSignaling


class HostSignalingTests(unittest.TestCase):
    def test_peer_is_bound_to_session(self):
        signaling = HostSignaling(enable_rtc=False)
        peer = signaling.create_peer("session-a")
        self.assertEqual(peer.state, "waiting")
        self.assertIs(signaling.get_peer(peer.peer_id, "session-a"), peer)
        with self.assertRaises(KeyError):
            signaling.get_peer(peer.peer_id, "session-b")

    def test_peers_for_session_returns_only_owned_peers(self):
        signaling = HostSignaling(enable_rtc=False)
        first = signaling.create_peer("session-a")
        second = signaling.create_peer("session-a")
        other = signaling.create_peer("session-b")

        self.assertEqual(
            {peer.peer_id for peer in signaling.peers_for_session("session-a")},
            {first.peer_id, second.peer_id},
        )
        self.assertEqual(signaling.peers_for_session("missing"), [])

    def test_empty_session_is_rejected(self):
        signaling = HostSignaling(enable_rtc=False)
        with self.assertRaises(ValueError):
            signaling.create_peer("   ")

    def test_invalid_session_is_rejected_by_close_session(self):
        signaling = HostSignaling(enable_rtc=False)
        with self.assertRaises(ValueError):
            signaling.close_session("   ")

    def test_empty_signaling_message_is_rejected(self):
        signaling = HostSignaling(enable_rtc=False)
        peer = signaling.create_peer("session-a")
        with self.assertRaises(ValueError):
            peer.receive({})
        with self.assertRaises(ValueError):
            peer.receive(None)

    def test_offer_without_media_reports_unavailable(self):
        signaling = HostSignaling(enable_rtc=False)
        peer = signaling.create_peer("session-a")
        result = signaling.signal(peer.peer_id, "session-a", {"type": "offer", "sdp": "test"})
        self.assertEqual(result.state, "error")
        self.assertEqual(result.outbound, [{
            "type": "error",
            "code": "webrtc_unavailable",
            "message": "WebRTC peer initialization failed. Check the host terminal for the actual error.",
        }])

    def test_peer_initialization_failure_is_reported(self):
        with patch("host.webrtc.signaling.WebRTCPeer", side_effect=RuntimeError("Capture is already running")):
            signaling = HostSignaling(enable_rtc=True)
            peer = signaling.create_peer("session-a")

        self.assertIsNone(peer.rtc)
        result = signaling.signal(peer.peer_id, "session-a", {"type": "offer", "sdp": "test"})
        self.assertEqual(result.state, "error")
        self.assertEqual(result.outbound[-1]["code"], "webrtc_unavailable")
        self.assertNotIn("aiortc", result.outbound[-1]["message"])

    def test_empty_offer_sdp_is_rejected_by_rtc_peer(self):
        signaling = HostSignaling(enable_rtc=False)
        peer = signaling.create_peer("session-a")
        with patch.object(peer, "receive", side_effect=ValueError("sdp must be a non-empty string")):
            with self.assertRaises(ValueError):
                signaling.signal(peer.peer_id, "session-a", {"type": "offer", "sdp": ""})

    def test_non_object_ice_candidate_is_rejected_by_rtc_peer(self):
        signaling = HostSignaling(enable_rtc=False)
        peer = signaling.create_peer("session-a")
        with patch.object(peer, "receive", side_effect=ValueError("candidate must be an object")):
            with self.assertRaises(ValueError):
                signaling.signal(peer.peer_id, "session-a", {"type": "ice-candidate", "candidate": "bad"})

    def test_close_clears_outbound_messages(self):
        signaling = HostSignaling(enable_rtc=False)
        peer = signaling.create_peer("session-a")
        peer.send({"type": "test"})
        signaling.close(peer.peer_id, "session-a")
        self.assertEqual(peer.state, "closed")
        self.assertEqual(peer.outbound, [])

    def test_close_session_removes_only_owned_peers(self):
        signaling = HostSignaling(enable_rtc=False)
        owned_a = signaling.create_peer("session-a")
        owned_b = signaling.create_peer("session-a")
        other = signaling.create_peer("session-b")

        self.assertEqual(signaling.close_session("session-a"), 2)
        self.assertNotIn(owned_a.peer_id, signaling.peers)
        self.assertNotIn(owned_b.peer_id, signaling.peers)
        self.assertIn(other.peer_id, signaling.peers)
        self.assertEqual(other.state, "waiting")

    def test_input_is_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ESPLINK_INPUT_ENABLED", None)
            signaling = HostSignaling(enable_rtc=False)
        self.assertFalse(signaling.input_enabled)

    def test_input_can_be_enabled_from_environment(self):
        with patch.dict(os.environ, {"ESPLINK_INPUT_ENABLED": "1"}):
            signaling = HostSignaling(enable_rtc=False)
        self.assertTrue(signaling.input_enabled)

    def test_false_environment_values_disable_input(self):
        for value in ("0", "false", "no", "off", ""):
            with self.subTest(value=value), patch.dict(os.environ, {"ESPLINK_INPUT_ENABLED": value}):
                signaling = HostSignaling(enable_rtc=False)
                self.assertFalse(signaling.input_enabled)


if __name__ == "__main__":
    unittest.main()
