"""Tests for the browser input protocol."""
import unittest

from host.webrtc.input import normalize_input


class InputProtocolTests(unittest.TestCase):
    def test_normalizes_keyboard_event(self):
        event = normalize_input({"type": "key", "action": "down", "data": {"code": "KeyW", "key": "w"}})
        self.assertEqual(event.type, "key")
        self.assertEqual(event.action, "down")
        self.assertEqual(event.data["code"], "KeyW")

    def test_rejects_unknown_event_type(self):
        with self.assertRaises(ValueError):
            normalize_input({"type": "clipboard", "action": "paste", "data": {}})

    def test_rejects_nested_data(self):
        with self.assertRaises(ValueError):
            normalize_input({"type": "mouse", "action": "move", "data": {"position": {"x": 1}}})


if __name__ == "__main__":
    unittest.main()
