# WebRTC tests

Tests for the host-side WebRTC signaling layer.

The current tests verify peer creation, offer/answer state transitions, and session isolation. They do not require the optional `aiortc` media dependency because the signaling tests operate on the host's lightweight signaling model.

Run this group from the repository root with:

```text
python -m unittest discover -s host/tests/webrtc -p "test_*.py"
```

Real browser media negotiation and media transport will be added when the WebRTC media backend is enabled.
