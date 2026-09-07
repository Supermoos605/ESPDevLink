import unittest
from host.config import COMPUTER_NAME
from host.status import HostStatus
from host.streaming import EncoderProfile, StreamConfig, build_manifest, get_capture_info
from host.run_host import diagnostics


class HostIntegrationTests(unittest.TestCase):
    def test_manifest_is_self_consistent(self):
        config = StreamConfig()
        encoder = EncoderProfile()
        manifest = build_manifest(config, encoder)
        self.assertEqual(manifest["transport"], "WebRTC")
        self.assertEqual(manifest["video"]["width"], config.width)
        self.assertEqual(manifest["encoder"]["codec"], encoder.codec)

    def test_status_snapshot_is_json_friendly(self):
        status = HostStatus(name=COMPUTER_NAME).snapshot()
        self.assertTrue(status["online"])
        self.assertIn("updated_at", status)

    def test_capture_info_has_backend(self):
        info = get_capture_info()
        self.assertTrue(info.backend)
        self.assertIsInstance(info.available, bool)

    def test_launcher_diagnostics(self):
        result = diagnostics()
        self.assertEqual(result["service"], "ESPLink Windows Host")
        self.assertIn("manifest", result)
        self.assertIn("capture", result)
