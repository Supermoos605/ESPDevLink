"""Tests for the optional Windows loopback audio track."""
import unittest

from host.webrtc.desktop_audio import DesktopAudioTrack


class DesktopAudioTrackTests(unittest.TestCase):
    def test_track_reports_missing_optional_dependencies_cleanly(self):
        try:
            DesktopAudioTrack()
        except RuntimeError as exc:
            self.assertIn("loopback audio", str(exc).lower())
        else:
            # A Windows development machine with the optional dependencies may
            # initialize successfully; the important contract is that startup
            # does not raise an unrelated import error.
            self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
