# Host tests

The host test suite verifies the PC-side ESPLink architecture without requiring an ESP32.

## Test areas

```text
host/tests/
├── auth/         # Shared authorization code and session behavior
├── network/      # LAN endpoint helpers
├── streaming/    # Stream configuration, encoder, capture, and runtime behavior
├── webrtc/       # WebRTC signaling behavior
└── integration/  # Cross-component host checks
```

## Run everything

From the repository root:

```text
python -m unittest discover -s host/tests -p "test_*.py"
```

## Run one area

```text
python -m unittest discover -s host/tests/auth -p "test_*.py"
python -m unittest discover -s host/tests/network -p "test_*.py"
python -m unittest discover -s host/tests/streaming -p "test_*.py"
python -m unittest discover -s host/tests/webrtc -p "test_*.py"
python -m unittest discover -s host/tests/integration -p "test_*.py"
```

## What the tests do not require

The unit tests use the host's Python components directly. They do not require:

- a physical ESP32
- an ESP32 Wi-Fi connection
- the ESP32 LAN IP address
- real game streaming hardware
- an installed WebRTC media backend for signaling-only tests

The local simulator can be used separately when an HTTP-level ESP32 API is needed.
