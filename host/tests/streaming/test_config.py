import unittest
from host.streaming import StreamConfig


class StreamConfigTests(unittest.TestCase):
    def test_defaults(self):
        config = StreamConfig()
        self.assertEqual(config.fps, 60)
        self.assertEqual(config.width, 1280)
        self.assertEqual(config.height, 720)

    def test_custom_values(self):
        config = StreamConfig(width=1920, height=1080, fps=30, video_bitrate_kbps=8000)
        self.assertEqual(config.as_dict()["width"], 1920)
        self.assertEqual(config.as_dict()["fps"], 30)

    def test_invalid_fps(self):
        with self.assertRaises(ValueError):
            StreamConfig(fps=0)


if __name__ == "__main__":
    unittest.main()
