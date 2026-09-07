import unittest
from host.streaming import EncoderProfile, StreamConfig


class EncoderProfileTests(unittest.TestCase):
    def test_default_profile(self):
        profile = EncoderProfile()
        profile.validate(StreamConfig())
        self.assertEqual(profile.as_dict()["codec"], "H264")

    def test_invalid_codec(self):
        with self.assertRaises(ValueError):
            EncoderProfile(codec="not-a-codec").validate(StreamConfig())

    def test_keyframe_limit(self):
        with self.assertRaises(ValueError):
            EncoderProfile(keyframe_interval=601).validate(StreamConfig(fps=60))


if __name__ == "__main__":
    unittest.main()
