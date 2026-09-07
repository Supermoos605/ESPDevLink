"""Basic no-hardware checks for the ESPLink simulator session flow."""

import json
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "streaming"))
from session_state import StreamSession


class StreamSessionTests(unittest.TestCase):
    def test_full_session(self):
        s = StreamSession()
        s.transition("ready")
        s.start("Test Stream", "browser")
        self.assertEqual(s.state, "connecting")
        self.assertEqual(s.game, "Test Stream")
        s.begin_stream()
        self.assertEqual(s.state, "streaming")
        s.stop()
        self.assertEqual(s.state, "ready")
        self.assertEqual(s.game, "")

    def test_invalid_transition_is_rejected(self):
        s = StreamSession()
        with self.assertRaises(ValueError):
            s.begin_stream()


class ConfigTests(unittest.TestCase):
    def test_config_is_valid_json(self):
        path = Path(__file__).with_name("config.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("host", data)
        self.assertIn("gateway", data)
        self.assertIn("heartbeat_timeout_seconds", data)


if __name__ == "__main__":
    unittest.main()
