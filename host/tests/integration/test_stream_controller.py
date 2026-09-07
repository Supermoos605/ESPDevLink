import unittest
from host.stream_controller import StreamController


class StreamControllerTests(unittest.TestCase):
    def test_peer_lifecycle(self):
        controller = StreamController()
        peer = controller.create_peer("session-a")
        self.assertEqual(peer.state, "waiting")
        result = controller.handle_signal(peer.peer_id, "session-a", {"type": "offer", "sdp": "demo"})
        self.assertEqual(result["state"], "negotiating")
        result = controller.handle_signal(peer.peer_id, "session-a", {"type": "answer", "sdp": "demo"})
        self.assertEqual(result["state"], "connected")

    def test_session_isolation(self):
        controller = StreamController()
        peer = controller.create_peer("session-a")
        with self.assertRaises(KeyError):
            controller.handle_signal(peer.peer_id, "session-b", {"type": "offer"})
