"""Dedicated Codespace integration test for the ESPDevLink simulator.

This test is intentionally cross-platform. It starts the HTTP simulator on an
ephemeral localhost port and exercises the same API flow used by the browser:
status -> auth -> PC discovery -> connect -> stream -> WebRTC signaling ->
disconnect -> logout.
"""
import json
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]


class CodespaceIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        cls.proc = subprocess.Popen(
            [sys.executable, "-m", "simulator.esp_link_simulator", "--host", "127.0.0.1", "--port", str(cls.port)],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            text=True,
        )
        cls.base = f"http://127.0.0.1:{cls.port}"
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                with urlopen(cls.base + "/api/status", timeout=1) as r:
                    if r.status == 200:
                        return
            except Exception:
                time.sleep(0.1)
        output = ""
        try:
            cls.proc.kill()
            output, _ = cls.proc.communicate(timeout=2)
        except Exception:
            pass
        cls.proc.kill()
        raise RuntimeError("Simulator did not start. Output: " + output)

    @classmethod
    def tearDownClass(cls):
        if cls.proc.poll() is None:
            cls.proc.terminate()
            try:
                cls.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                cls.proc.kill()
                cls.proc.wait(timeout=2)

    def request(self, method, path, body=None, session=None, peer=None):
        headers = {"Content-Type": "application/json"}
        if session:
            headers["X-ESPLink-Session"] = session
        if peer:
            headers["X-ESPLink-Peer"] = peer
        data = json.dumps(body).encode() if body is not None else None
        try:
            with urlopen(Request(self.base + path, data=data, headers=headers, method=method), timeout=3) as r:
                return r.status, json.loads(r.read().decode())
        except HTTPError as e:
            return e.code, json.loads(e.read().decode())

    def test_complete_browser_flow(self):
        status, data = self.request("GET", "/api/status")
        self.assertEqual(status, 200)
        self.assertTrue(data["authorization_required"])

        status, data = self.request("GET", "/api/pc")
        self.assertEqual(status, 401)

        status, data = self.request("POST", "/api/auth/login", {"code": "wrong"})
        self.assertEqual(status, 403)

        status, data = self.request("POST", "/api/auth/login", {"code": "CHANGE-ME"})
        self.assertEqual(status, 200)
        session = data["session_id"]
        self.assertTrue(session)

        status, data = self.request("GET", "/api/pc", session=session)
        self.assertEqual(status, 200)
        self.assertTrue(data["online"])

        status, data = self.request(
            "POST", "/api/connect",
            {"game": "Codespace Test", "client_id": "codespace-test"},
            session=session,
        )
        self.assertEqual(status, 200)

        status, data = self.request("POST", "/api/stream/begin", session=session)
        self.assertEqual(status, 200)

        status, data = self.request("GET", "/api/stream/state", session=session)
        self.assertEqual(status, 200)
        self.assertEqual(data["state"], "streaming")

        status, data = self.request("POST", "/api/webrtc/session", session=session)
        self.assertEqual(status, 200)
        peer = data["peer_id"]

        status, data = self.request(
            "POST", "/api/webrtc/message",
            {"type": "offer", "sdp": "codespace-test"},
            session=session, peer=peer,
        )
        self.assertEqual(status, 200)

        status, data = self.request("GET", "/api/webrtc/messages", session=session, peer=peer)
        self.assertEqual(status, 200)
        self.assertEqual(data["messages"][0]["type"], "offer")

        status, data = self.request("POST", "/api/webrtc/close", session=session, peer=peer)
        self.assertEqual(status, 200)

        status, data = self.request("POST", "/api/stream/disconnect", session=session)
        self.assertEqual(status, 200)

        status, data = self.request("POST", "/api/auth/logout", session=session)
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
