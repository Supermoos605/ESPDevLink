import unittest
from host.webrtc import HostSignaling


class SignalingTests(unittest.TestCase):
    def test_peer_lifecycle(self):
        signaling = HostSignaling()
        peer = signaling.create_peer("session-a")
        peer.receive({"type": "offer"})
        self.assertEqual(peer.state, "negotiating")
        peer.receive({"type": "answer"})
        self.assertEqual(peer.state, "connected")

    def test_session_isolation(self):
        signaling = HostSignaling()
        peer = signaling.create_peer("session-a")
        with self.assertRaises(KeyError):
            signaling.get_peer(peer.peer_id, "session-b")
