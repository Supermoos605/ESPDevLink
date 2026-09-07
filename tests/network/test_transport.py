import unittest

from host.network.relay import SignalingRelay
from host.network.transport import RelayTransport


class RelayTransportTests(unittest.TestCase):
    def test_register_requires_token(self):
        transport = RelayTransport(SignalingRelay(access_token="secret"))

        denied = transport.handle(
            "register",
            {"client_id": "browser", "session_id": "session"},
            token="wrong",
        )
        allowed = transport.handle(
            "register",
            {"client_id": "browser", "session_id": "session"},
            token="secret",
        )

        self.assertEqual(denied.status, 401)
        self.assertEqual(allowed.status, 201)
        self.assertIn("peer_id", allowed.body)

    def test_send_and_poll(self):
        transport = RelayTransport()
        registered = transport.handle(
            "register", {"client_id": "browser", "session_id": "session"}
        )
        peer_id = registered.body["peer_id"]

        sent = transport.handle(
            "send",
            {
                "peer_id": peer_id,
                "session_id": "session",
                "message": {"type": "offer", "sdp": "example"},
            },
        )
        polled = transport.handle(
            "poll", {"peer_id": peer_id, "session_id": "session"}
        )

        self.assertEqual(sent.status, 202)
        self.assertEqual(polled.status, 200)
        self.assertEqual(polled.body["messages"], [{"type": "offer", "sdp": "example"}])

    def test_invalid_request_and_unknown_action(self):
        transport = RelayTransport()

        invalid = transport.handle("register", {"client_id": ""})
        unknown = transport.handle("not-an-action", {})

        self.assertEqual(invalid.status, 400)
        self.assertEqual(unknown.status, 404)

    def test_queue_limit(self):
        transport = RelayTransport(SignalingRelay(max_queue=1))
        registered = transport.handle(
            "register", {"client_id": "browser", "session_id": "session"}
        )
        peer_id = registered.body["peer_id"]
        payload = {"peer_id": peer_id, "session_id": "session", "message": {"type": "ice"}}

        first = transport.handle("send", payload)
        second = transport.handle("send", payload)

        self.assertEqual(first.status, 202)
        self.assertEqual(second.status, 429)


if __name__ == "__main__":
    unittest.main()
