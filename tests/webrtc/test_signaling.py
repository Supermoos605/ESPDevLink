"""Regression tests for host-side WebRTC signaling."""
import os
import threading
import unittest
from unittest.mock import patch

from host.webrtc.signaling import HostSignaling


class HostSignalingTests(unittest.TestCase):
    def test_peer_is_bound_to_session(self):
        signaling = HostSignaling(enable_rtc=False)
        peer = signaling.create_peer("session-a")
        self.assertEqual(peer.state, "waiting")
        self.assertIs(signaling.get_peer(peer.peer_id, "session-a"), peer)
        with self.assertRaises(KeyError):
            signaling.get_peer(peer.peer_id, "session-b")

    def test_peers_for_session_returns_only_owned_peers(self):
        signaling = HostSignaling(enable_rtc=False)
        first = signaling.create_peer("session-a")
        second = signaling.create_peer("session-b")
        self.assertEqual({p.peer_id for p in signaling.peers_for_session("session-a")}, {first.peer_id})
        self.assertEqual({p.peer_id for p in signaling.peers_for_session("session-b")}, {second.peer_id})
        self.assertEqual(signaling.peers_for_session("missing"), [])

    def test_empty_session_is_rejected(self):
        signaling = HostSignaling(enable_rtc=False)
        with self.assertRaises(ValueError):
            signaling.create_peer("   ")

    def test_invalid_session_is_rejected_by_close_session(self):
        signaling = HostSignaling(enable_rtc=False)
        with self.assertRaises(ValueError):
            signaling.close_session("   ")

    def test_empty_signaling_message_is_rejected(self):
        signaling = HostSignaling(enable_rtc=False)
        peer = signaling.create_peer("session-a")
        with self.assertRaises(ValueError):
            peer.receive({})
        with self.assertRaises(ValueError):
            peer.receive(None)

    def test_offer_without_media_reports_unavailable(self):
        signaling = HostSignaling(enable_rtc=False)
        peer = signaling.create_peer("session-a")
        result = signaling.signal(peer.peer_id, "session-a", {"type": "offer", "sdp": "test"})
        self.assertEqual(result.state, "error")
        self.assertEqual(result.outbound, [{"type": "error", "code": "webrtc_unavailable", "message": "WebRTC peer initialization failed. Check the host terminal for the actual error."}])

    def test_peer_initialization_failure_is_reported(self):
        with patch("host.webrtc.signaling.WebRTCPeer", side_effect=RuntimeError("Capture is already running")):
            signaling = HostSignaling(enable_rtc=True)
            with self.assertRaisesRegex(RuntimeError, "WebRTC peer initialization failed: Capture is already running"):
                signaling.create_peer("session-a")
        self.assertEqual(signaling.peers_for_session("session-a"), [])

    def test_safari_negotiation_error_is_preserved_and_peer_is_cleaned(self):
        class FailingRTC:
            def __init__(self): self.closed = False
            def accept_offer(self, sdp): raise ValueError("aiortc could not negotiate Safari media directions")
            def close(self): self.closed = True
        signaling = HostSignaling(enable_rtc=False)
        peer = signaling.create_peer("session-safari")
        rtc = FailingRTC(); peer.rtc = rtc
        result = signaling.signal_result(peer.peer_id, "session-safari", {"type": "offer", "sdp": "v=0\\r\\n"})
        self.assertEqual(result["state"], "error")
        self.assertEqual(result["outbound"][0]["code"], "webrtc_negotiation_failed")
        self.assertTrue(rtc.closed)
        self.assertIsNone(peer.rtc)

    def test_empty_offer_sdp_is_rejected_by_rtc_peer(self):
        signaling = HostSignaling(enable_rtc=False)
        peer = signaling.create_peer("session-a")
        with patch.object(peer, "receive", side_effect=ValueError("sdp must be a non-empty string")):
            with self.assertRaises(ValueError):
                signaling.signal(peer.peer_id, "session-a", {"type": "offer", "sdp": ""})

    def test_non_object_ice_candidate_is_rejected_by_rtc_peer(self):
        signaling = HostSignaling(enable_rtc=False)
        peer = signaling.create_peer("session-a")
        with patch.object(peer, "receive", side_effect=ValueError("candidate must be an object")):
            with self.assertRaises(ValueError):
                signaling.signal(peer.peer_id, "session-a", {"type": "ice-candidate", "candidate": "bad"})

    def test_ice_candidate_is_queued_until_offer_is_applied(self):
        rtc = type("FakeRTC", (), {"accept_offer": lambda self, sdp: {"type": "answer", "sdp": "answer"}, "add_ice_candidate": lambda self, candidate: None})()
        signaling = HostSignaling(enable_rtc=False)
        peer = signaling.create_peer("session-a")
        peer.rtc = rtc
        candidate = {"candidate": "candidate:ipad", "sdpMid": "0", "sdpMLineIndex": 0}
        result = signaling.signal(peer.peer_id, "session-a", {"type": "ice-candidate", "candidate": candidate})
        self.assertIs(result, peer)
        self.assertEqual(peer.pending_ice, [candidate])
        self.assertFalse(peer.remote_description_set)
        self.assertEqual(peer.outbound, [])
        signaling.signal(peer.peer_id, "session-a", {"type": "offer", "sdp": "ipad-offer"})
        self.assertTrue(peer.remote_description_set)
        self.assertEqual(peer.pending_ice, [])
        self.assertEqual(peer.outbound, [{"type": "answer", "sdp": "answer"}])

    def test_queued_ice_is_flushed_after_offer_before_later_ice(self):
        added = []
        class FakeRTC:
            def accept_offer(self, sdp): return {"type": "answer", "sdp": "answer"}
            def add_ice_candidate(self, candidate): added.append(candidate)
        signaling = HostSignaling(enable_rtc=False)
        peer = signaling.create_peer("session-a")
        peer.rtc = FakeRTC()
        early = {"candidate": "candidate:early"}
        late = {"candidate": "candidate:late"}
        signaling.signal(peer.peer_id, "session-a", {"type": "ice-candidate", "candidate": early})
        signaling.signal(peer.peer_id, "session-a", {"type": "offer", "sdp": "ipad-offer"})
        signaling.signal(peer.peer_id, "session-a", {"type": "ice-candidate", "candidate": late})
        self.assertEqual(added, [early, late])
        self.assertEqual(peer.pending_ice, [])
        self.assertTrue(peer.remote_description_set)
        self.assertEqual(peer.state, "connected")

    def test_concurrent_offer_and_ice_are_race_safe(self):
        class FakeRTC:
            def __init__(self): self.added = []
            def accept_offer(self, sdp): return {"type": "answer", "sdp": "answer"}
            def add_ice_candidate(self, candidate): self.added.append(candidate)
        for _ in range(20):
            signaling = HostSignaling(enable_rtc=False)
            peer = signaling.create_peer("session-a")
            rtc = FakeRTC(); peer.rtc = rtc
            candidate = {"candidate": "candidate:ipad-race"}
            start = threading.Barrier(3); errors = []
            def send_offer():
                try:
                    start.wait(); signaling.signal(peer.peer_id, "session-a", {"type": "offer", "sdp": "ipad-offer"})
                except Exception as exc: errors.append(exc)
            def send_ice():
                try:
                    start.wait(); signaling.signal(peer.peer_id, "session-a", {"type": "ice-candidate", "candidate": candidate})
                except Exception as exc: errors.append(exc)
            a = threading.Thread(target=send_offer); b = threading.Thread(target=send_ice)
            a.start(); b.start(); start.wait(); a.join(); b.join()
            self.assertEqual(errors, [])
            self.assertEqual(rtc.added, [candidate])
            self.assertEqual(peer.pending_ice, [])
            self.assertTrue(peer.remote_description_set)
            self.assertEqual(peer.state, "connected")
            self.assertEqual(peer.outbound, [{"type": "answer", "sdp": "answer"}])

    def test_signal_and_drain_concurrent_do_not_duplicate_or_lose_messages(self):
        class FakeRTC:
            def accept_offer(self, sdp): return {"type": "answer", "sdp": "answer"}
            def add_ice_candidate(self, candidate): return None
        for _ in range(20):
            signaling = HostSignaling(enable_rtc=False)
            peer = signaling.create_peer("session-a"); peer.rtc = FakeRTC()
            start = threading.Barrier(3); errors = []; drained = []
            def signal_offer():
                try:
                    start.wait(); signaling.signal(peer.peer_id, "session-a", {"type": "offer", "sdp": "offer"})
                except Exception as exc: errors.append(exc)
            def drain():
                try:
                    start.wait(); drained.extend(signaling.drain_outbound(peer.peer_id, "session-a"))
                except Exception as exc: errors.append(exc)
            a = threading.Thread(target=signal_offer); b = threading.Thread(target=drain)
            a.start(); b.start(); start.wait(); a.join(); b.join()
            drained.extend(signaling.drain_outbound(peer.peer_id, "session-a"))
            self.assertEqual(errors, [])
            self.assertEqual([m["type"] for m in drained], ["answer"])
            self.assertEqual(signaling.drain_outbound(peer.peer_id, "session-a"), [])

    def test_signal_and_close_concurrent_never_leaves_stale_peer(self):
        class FakeRTC:
            def accept_offer(self, sdp): return {"type": "answer", "sdp": "answer"}
            def close(self): return None
        for _ in range(20):
            signaling = HostSignaling(enable_rtc=False)
            peer = signaling.create_peer("session-a"); peer.rtc = FakeRTC()
            start = threading.Barrier(3); outcomes = []
            def signal_offer():
                try:
                    start.wait(); signaling.signal_result(peer.peer_id, "session-a", {"type": "offer", "sdp": "offer"}); outcomes.append("signal-ok")
                except (KeyError, ValueError): outcomes.append("signal-closed")
            def close_peer():
                start.wait()
                try: signaling.close(peer.peer_id, "session-a"); outcomes.append("close-ok")
                except (KeyError, ValueError): outcomes.append("close-already-gone")
            a = threading.Thread(target=signal_offer); b = threading.Thread(target=close_peer)
            a.start(); b.start(); start.wait(); a.join(); b.join()
            self.assertIn("close-ok", outcomes)
            self.assertNotIn(peer.peer_id, signaling.peers)
            self.assertEqual(peer.state, "closed")
            self.assertIsNone(peer.rtc)

    def test_close_session_concurrent_with_signal_cleans_peer(self):
        class FakeRTC:
            def accept_offer(self, sdp): return {"type": "answer", "sdp": "answer"}
            def close(self): return None
        for _ in range(20):
            signaling = HostSignaling(enable_rtc=False)
            peer = signaling.create_peer("session-a"); peer.rtc = FakeRTC()
            start = threading.Barrier(3); errors = []
            def signal_offer():
                try:
                    start.wait(); signaling.signal_result(peer.peer_id, "session-a", {"type": "offer", "sdp": "offer"})
                except (KeyError, ValueError): pass
                except Exception as exc: errors.append(exc)
            def close_session():
                try: start.wait(); signaling.close_session("session-a")
                except Exception as exc: errors.append(exc)
            a = threading.Thread(target=signal_offer); b = threading.Thread(target=close_session)
            a.start(); b.start(); start.wait(); a.join(); b.join()
            self.assertEqual(errors, [])
            self.assertNotIn(peer.peer_id, signaling.peers)
            self.assertEqual(peer.state, "closed")
            self.assertIsNone(peer.rtc)

    def test_drain_outbound_is_atomic(self):
        signaling = HostSignaling(enable_rtc=False)
        peer = signaling.create_peer("session-a")
        peer.send({"type": "answer"}); peer.send({"type": "candidate"})
        messages = signaling.drain_outbound(peer.peer_id, "session-a")
        self.assertEqual(messages, [{"type": "answer"}, {"type": "candidate"}])
        self.assertEqual(peer.outbound, [])
        self.assertEqual(signaling.drain_outbound(peer.peer_id, "session-a"), [])

    def test_close_clears_outbound_messages(self):
        signaling = HostSignaling(enable_rtc=False); peer = signaling.create_peer("session-a")
        peer.send({"type": "test"}); signaling.close(peer.peer_id, "session-a")
        self.assertEqual(peer.state, "closed"); self.assertEqual(peer.outbound, [])

    def test_failed_offer_preserves_error_for_browser_after_cleanup(self):
        class FailingRTC:
            def __init__(self): self.closed = False
            def accept_offer(self, sdp): raise ValueError("None is not in list")
            def close(self): self.closed = True
        signaling = HostSignaling(enable_rtc=False)
        peer = signaling.create_peer("session-a")
        rtc = FailingRTC()
        peer.rtc = rtc
        result = signaling.signal_result(peer.peer_id, "session-a", {"type": "offer", "sdp": "safari-offer"})
        self.assertEqual(result["state"], "error")
        self.assertEqual(result["peer_id"], peer.peer_id)
        self.assertEqual(result["outbound"][0]["code"], "webrtc_negotiation_failed")
        self.assertTrue(rtc.closed)
        self.assertIsNone(peer.rtc)
        self.assertEqual(peer.pending_ice, [])
        self.assertFalse(peer.remote_description_set)

    def test_close_cleans_up_even_when_rtc_close_fails(self):
        class FailingRTC:
            def close(self): raise RuntimeError("already closed")
        signaling = HostSignaling(enable_rtc=False); peer = signaling.create_peer("session-a")
        peer.rtc = FailingRTC(); peer.pending_ice.append({"candidate": "stale"}); peer.remote_description_set = True; peer.outbound.append({"type": "stale"})
        signaling.close(peer.peer_id, "session-a")
        self.assertNotIn(peer.peer_id, signaling.peers); self.assertIsNone(peer.rtc); self.assertEqual(peer.state, "closed")
        self.assertEqual(peer.pending_ice, []); self.assertFalse(peer.remote_description_set); self.assertEqual(peer.outbound, [])

    def test_reconnect_replaces_old_peer_with_fresh_state(self):
        signaling = HostSignaling(enable_rtc=False); old_peer = signaling.create_peer("session-a")
        old_peer.pending_ice.append({"candidate": "old"}); old_peer.outbound.append({"type": "old"})
        new_peer = signaling.create_peer("session-a")
        self.assertNotEqual(new_peer.peer_id, old_peer.peer_id); self.assertNotIn(old_peer.peer_id, signaling.peers)
        self.assertEqual(new_peer.state, "waiting"); self.assertEqual(new_peer.pending_ice, []); self.assertEqual(new_peer.outbound, [])
        self.assertFalse(new_peer.remote_description_set)

    def test_close_session_removes_only_owned_peers(self):
        signaling = HostSignaling(enable_rtc=False); owned = signaling.create_peer("session-a"); other = signaling.create_peer("session-b")
        self.assertEqual(signaling.close_session("session-a"), 1)
        self.assertNotIn(owned.peer_id, signaling.peers); self.assertIn(other.peer_id, signaling.peers); self.assertEqual(other.state, "waiting")

    def test_input_is_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ESPLINK_INPUT_ENABLED", None); signaling = HostSignaling(enable_rtc=False)
        self.assertFalse(signaling.input_enabled)

    def test_input_can_be_enabled_from_environment(self):
        with patch.dict(os.environ, {"ESPLINK_INPUT_ENABLED": "1"}): signaling = HostSignaling(enable_rtc=False)
        self.assertTrue(signaling.input_enabled)

    def test_false_environment_values_disable_input(self):
        for value in ("0", "false", "no", "off", ""):
            with self.subTest(value=value), patch.dict(os.environ, {"ESPLINK_INPUT_ENABLED": value}):
                signaling = HostSignaling(enable_rtc=False); self.assertFalse(signaling.input_enabled)


if __name__ == "__main__":
    unittest.main()
