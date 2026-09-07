"""Tests the HTTP-facing signaling adapter without a network or device."""

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "streaming"))
from signaling_http import create_session, send_message, receive_messages, close_session


class SignalingHttpTests(unittest.TestCase):
    def test_offer_round_trip(self):
        created = create_session("browser-test")
        peer_id = created["peer_id"]
        self.assertTrue(created["ok"])
        send_message(peer_id, {"type": "offer", "sdp": "test-sdp"})
        received = receive_messages(peer_id)
        self.assertEqual(received["messages"], [{"type": "offer", "sdp": "test-sdp"}])
        self.assertEqual(receive_messages(peer_id)["messages"], [])
        self.assertTrue(close_session(peer_id)["closed"])


if __name__ == "__main__":
    unittest.main()
