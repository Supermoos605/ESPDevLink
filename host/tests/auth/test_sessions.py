import unittest
from host.auth import AuthenticatedHost, ConnectionManager, SessionAuthorizer


class SessionTests(unittest.TestCase):
    def test_authorizer_accepts_shared_code(self):
        authorizer = SessionAuthorizer("test-code")
        self.assertTrue(authorizer.authorize("test-code"))
        self.assertTrue(authorizer.authorize("test-code"))
        self.assertFalse(authorizer.authorize("wrong-code"))

    def test_status_does_not_expose_code(self):
        self.assertNotIn("secret", str(SessionAuthorizer("secret").status()))

    def test_authenticated_host_allows_multiple_sessions(self):
        host = AuthenticatedHost("shared-code")
        host.authorize_and_connect("shared-code", "session-a", "client-a")
        result = host.authorize_and_connect("shared-code", "session-b", "client-b")
        self.assertEqual(result["session_id"], "session-b")
        self.assertEqual(len(host.status()["sessions"]), 2)

    def test_wrong_code_is_rejected(self):
        host = AuthenticatedHost("shared-code")
        with self.assertRaises(PermissionError):
            host.authorize_and_connect("wrong", "session-a", "client-a")

    def test_connection_lifecycle(self):
        manager = ConnectionManager()
        session = manager.connect("session-1", "browser-1")
        self.assertEqual(session.state, "connected")
        manager.set_state("session-1", "streaming")
        self.assertEqual(manager.get("session-1").state, "streaming")
        manager.disconnect("session-1")
        self.assertEqual(manager.snapshot(), [])

    def test_unknown_session(self):
        with self.assertRaises(KeyError):
            ConnectionManager().get("missing")


if __name__ == "__main__":
    unittest.main()
