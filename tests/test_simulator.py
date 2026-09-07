"""Tests for simulator network defaults and configuration parsing."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from simulator import esp_link_simulator as simulator


class SimulatorTests(unittest.TestCase):
    def test_simulator_binds_all_interfaces_by_default(self):
        self.assertEqual(simulator.HOST, "0.0.0.0")
        self.assertEqual(simulator.PORT, 8080)

    def test_config_can_override_bind_address_and_port(self):
        with tempfile.TemporaryDirectory() as temp:
            config_path = Path(temp) / "config.json"
            config_path.write_text(json.dumps({
                "gateway": {"bind_host": "127.0.0.1", "port": 9090}
            }), encoding="utf-8")
            with patch.object(simulator, "CONFIG", config_path):
                config = simulator.load_config()
        self.assertEqual(config["gateway"]["bind_host"], "127.0.0.1")
        self.assertEqual(config["gateway"]["port"], 9090)


if __name__ == "__main__":
    unittest.main()
