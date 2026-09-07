"""No-hardware tests for ESPLink WebRTC signaling."""

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "streaming"))
from signaling import SignalingManager


class SignalingTests(unittest.TestCase):
    def test_each_session_gets_unique_peer_id(self):
        manager = SignalingManager()
        a = manager.create("browser-a")
        b = manager.create("browser-b")
        self.assertNotEqual(a.peer_id, b.peer_id)
        self.assertEqual(a.client_id, "browser-a")
        self.assertEqual(b.client_id, "browser-b")

    def test_messages_are_isolated(self):
        manager = SignalingManager()
        a = manager.create("browser-a")
        b = manager.create("browser-b")
        a.queue({"type": "offer", "sdp": "test-a"})
        self.assertEqual(a.drain(), [{"type": "offer", "sdp": "test-a"}])
        self.assertEqual(b.drain(), [])

    def test_closed_session_rejects_messages(self):
        manager = SignalingManager()
        session = manager.create("browser")
        manager.close(session.peer_id)
        with self.assertRaises(ValueError):
            manager.get(session.peer_id)


if __name__ == "__main__":
    unittest.main()
