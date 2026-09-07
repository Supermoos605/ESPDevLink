"""Tests for the Windows-host game service."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from host.games.service import GameService


class GameServiceTests(unittest.TestCase):
    def make_config(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "games.json"
        path.write_text(
            json.dumps({
                "games": [
                    {"id": "desktop", "name": "Desktop", "launcher": "windows", "executable": ""},
                    {"id": "test", "name": "Test Game", "launcher": "windows", "executable": "C:/Games/Test.exe"},
                ]
            }),
            encoding="utf-8",
        )
        return path

    def test_list_returns_configured_games(self):
        service = GameService(self.make_config())
        self.assertEqual(service.list(), [
            {"id": "desktop", "name": "Desktop", "launcher": "windows"},
            {"id": "test", "name": "Test Game", "launcher": "windows"},
        ])

    def test_unknown_game_is_rejected(self):
        service = GameService(self.make_config())
        with self.assertRaises(KeyError):
            service.get("missing")

    def test_unconfigured_game_is_not_launched(self):
        service = GameService(self.make_config())
        with self.assertRaises(RuntimeError):
            service.launch("desktop")

    @patch("host.games.service.subprocess.Popen")
    def test_launch_records_process(self, popen):
        process = popen.return_value
        process.pid = 1234
        process.poll.return_value = None
        service = GameService(self.make_config())
        result = service.launch("test")
        popen.assert_called_once_with(["C:/Games/Test.exe"])
        self.assertEqual(result["pid"], 1234)
        self.assertEqual(result["state"], "launched")
        self.assertEqual(service.status()["running"], {"test": 1234})

    @patch("host.games.service.subprocess.Popen")
    def test_duplicate_launch_is_rejected(self, popen):
        process = popen.return_value
        process.pid = 1234
        process.poll.return_value = None
        service = GameService(self.make_config())
        service.launch("test")
        with self.assertRaises(RuntimeError):
            service.launch("test")
        popen.assert_called_once_with(["C:/Games/Test.exe"])

    @patch("host.games.service.subprocess.Popen")
    def test_stop_terminates_process_and_clears_status(self, popen):
        process = popen.return_value
        process.pid = 1234
        process.poll.return_value = None
        service = GameService(self.make_config())
        service.launch("test")
        result = service.stop("test")
        process.terminate.assert_called_once_with()
        self.assertEqual(result, {"id": "test", "name": "Test Game", "pid": 1234, "state": "stopped"})
        self.assertEqual(service.status()["running"], {})

    @patch("host.games.service.subprocess.Popen")
    def test_finished_process_is_removed_from_status(self, popen):
        process = popen.return_value
        process.pid = 1234
        process.poll.return_value = None
        service = GameService(self.make_config())
        service.launch("test")
        process.poll.return_value = 0
        self.assertEqual(service.status()["running"], {})


if __name__ == "__main__":
    unittest.main()
