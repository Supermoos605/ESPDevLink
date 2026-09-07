import unittest

from host.webrtc.peer import WebRTCPeer


class WebRTCPeerValidationTests(unittest.TestCase):
    def test_ice_candidate_requires_object(self):
        with self.assertRaises(ValueError):
            WebRTCPeer._candidate_from_payload(None)

    def test_empty_ice_candidate_is_treated_as_end_of_candidates(self):
        self.assertIsNone(WebRTCPeer._candidate_from_payload({}))
        self.assertIsNone(WebRTCPeer._candidate_from_payload({"candidate": ""}))

    def test_candidate_prefix_is_removed(self):
        class FakeCandidate:
            sdpMid = None
            sdpMLineIndex = None

        class FakeCandidateFactory:
            def __call__(self, value):
                self.value = value
                return FakeCandidate()

        factory = FakeCandidateFactory()
        original = __import__("host.webrtc.peer", fromlist=["candidate_from_sdp"]).candidate_from_sdp
        module = __import__("host.webrtc.peer", fromlist=["candidate_from_sdp"])
        module.candidate_from_sdp = factory
        try:
            candidate = WebRTCPeer._candidate_from_payload(
                {"candidate": "candidate:1 1 UDP 123 192.0.2.1 5000 typ host", "sdpMid": "0", "sdpMLineIndex": 0}
            )
        finally:
            module.candidate_from_sdp = original

        self.assertEqual(factory.value, "1 1 UDP 123 192.0.2.1 5000 typ host")
        self.assertEqual(candidate.sdpMid, "0")
        self.assertEqual(candidate.sdpMLineIndex, 0)


if __name__ == "__main__":
    unittest.main()
