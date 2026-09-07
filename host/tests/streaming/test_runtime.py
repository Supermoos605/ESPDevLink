import unittest
from host.streaming import StreamRuntime


class StreamRuntimeTests(unittest.TestCase):
    def test_start_and_stop(self):
        runtime = StreamRuntime()
        self.assertEqual(runtime.status()["state"], "ready")
        runtime.start()
        self.assertEqual(runtime.status()["state"], "streaming")
        runtime.stop()
        self.assertEqual(runtime.status()["state"], "ready")

    def test_frame_telemetry(self):
        runtime = StreamRuntime()
        runtime.frame_sent(1024)
        health = runtime.status()["health"]
        self.assertEqual(health["frames_sent"], 1)
        self.assertEqual(health["bytes_sent"], 1024)
        self.assertIsNotNone(health["seconds_since_frame"])

    def test_degraded_network_reduces_quality(self):
        runtime = StreamRuntime()
        before = runtime.status()["quality"]["video_bitrate_kbps"]
        after = runtime.report_network(packet_loss_percent=10, rtt_ms=250)
        self.assertLess(after["video_bitrate_kbps"], before)


if __name__ == "__main__":
    unittest.main()
