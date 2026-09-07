# ESPLink Windows Host

The `host/` package is the PC-side component of ESPLink. It provides the Windows host facade, local HTTP controls, authorization/session management, network discovery, heartbeat reporting, game configuration, streaming state, and WebRTC signaling.

## Requirements

- Windows 10 or Windows 11 for the Windows-specific host features
- Python 3.9 or newer
- ESPLink ESP32 firmware on the same local network for hardware operation
- No ESP32 is required when using the local simulator

## Host structure

```text
host/
├── auth/       # Authorization and client sessions
├── games/      # Configured game discovery
├── network/    # LAN discovery and PC heartbeat
├── streaming/  # Capture, media, encoder, and runtime state
├── webrtc/     # Signaling, peer, and media interfaces
└── tests/      # Host unit/integration tests
```

The root-level Python files are intentionally limited to the host facade, HTTP server, configuration, status, stream coordinator, and launchers.

## Diagnostics

From the repository root:

```text
python -m host.run_host
```

This checks the host-side streaming configuration and prints a diagnostic manifest. It does not start a server.

## HTTP host

Start the local host control service with:

```text
python -m host.host_server
```

It listens on `127.0.0.1:8765` by default.

Current host endpoints:

- `GET /api/host/health` — host health check
- `GET /api/host/status` — host, network, session, and streaming state
- `POST /api/host/stream/start` — start the host streaming state
- `POST /api/host/stream/stop` — stop the host streaming state

## Heartbeat agent

The PC heartbeat agent is now part of the `network` package:

```text
python -m host.network.heartbeat
```

The Windows shortcut `run_esp_link.bat` starts the same module.

The agent uses `ESPLINK_ESP32` to select the ESP32/simulator URL. It reports the computer name, LAN IP, configured game, stream state, and connection permission.

## Configuration

Configuration is centralized in `host/config.py` and can be overridden with environment variables:

| Variable | Purpose | Default |
|---|---|---|
| `ESPLINK_ESP32` | ESP32 or simulator URL | `http://steamlink.local` |
| `ESPLINK_COMPUTER_NAME` | Name reported by the host | Windows computer name |
| `ESPLINK_HEARTBEAT` | Heartbeat interval in seconds | `2` |
| `ESPLINK_ALLOW_CONNECTIONS` | Allow incoming connections | `1` |
| `ESPLINK_AUTH_CODE` | Shared authorization code | `change-me` |

Keep a real authorization code in an environment variable rather than committing it to the repository.

## Authorization and sessions

ESPLink uses one shared authorization code for authorized clients. Each successful connection has its own session ID, so multiple clients can have different session IDs while using the same configured authorization code.

The code is never returned by the authorization status API.

## Streaming

The streaming package currently contains:

- `capture.py` — Windows capture backend abstraction
- `config.py` — stream and encoder configuration
- `media.py` — host media registration
- `profiles.py` — codec negotiation and stream manifest generation
- `runtime.py` — stream health and adaptive quality state

Actual frame acquisition and complete browser-compatible media transport are still future implementation work. Optional media dependencies are listed in `requirements-streaming.txt`.

## Tests

Run all host tests from the repository root:

```text
python -m unittest discover -s host/tests -p "test_*.py"
```

Run only authentication tests:

```text
python -m unittest discover -s host/tests/auth -p "test_*.py"
```

Run only streaming tests:

```text
python -m unittest discover -s host/tests/streaming -p "test_*.py"
```

Run only WebRTC tests:

```text
python -m unittest discover -s host/tests/webrtc -p "test_*.py"
```
