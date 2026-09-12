# ESPLink

ESPLink is a browser-first local PC game gateway built around an ESP32 gateway and a Windows host. The ESP32 handles local discovery and the browser-facing control UI; the Windows PC runs the game and provides the real-time media/input path.

## Project layout

```text
ESPLink/
├── platformio.ini          # ESP32 PlatformIO project
├── src/main.cpp            # ESP32 firmware
├── data/index.html         # Browser UI served by LittleFS
├── host/                   # Windows host package
├── simulator/              # ESP32 HTTP/API simulator
└── tests/                  # Cross-platform host/protocol tests
```

## Run the Windows host

From the repository root:

```text
python -m host.run_host
```

This runs host diagnostics without starting the HTTP service.

To start the Windows host HTTP service:

```text
python -m host.host_server
```

The host binds to `0.0.0.0:8765` so a browser on the same LAN can reach it at `http://<PC-IP>:8765/`.

The heartbeat agent is separate:

```text
python -m host.network.heartbeat
```

`host/run_esp_link.bat` is a Windows shortcut for starting the heartbeat agent.

## Development without the ESP32

The simulator lets the PC-side software be developed without physical ESP32 hardware.

Start it from the repository root:

```text
python simulator/esp_link_simulator.py
```

The simulator binds to `0.0.0.0:8080` by default and prints both the local and LAN URLs when it starts. It can also be overridden without editing config:

```text
python simulator/esp_link_simulator.py --host 0.0.0.0 --port 8080
```

Open the printed LAN URL from another device on the same network. The simulator's mDNS name is currently only simulated; real `steamlink.local` discovery will be provided by the ESP32 firmware.

In another terminal, point the heartbeat agent at the simulator:

### Command Prompt

```bat
set ESPLINK_ESP32=http://127.0.0.1:8080
python -m host.network.heartbeat
```

### PowerShell

```powershell
$env:ESPLINK_ESP32="http://127.0.0.1:8080"
python -m host.network.heartbeat
```

The simulator uses `simulator/config.json` for its test PC state, mDNS name, bind address/port, heartbeat behavior, and authorization code.

## Host authorization

The host uses one shared authorization code configured with `ESPLINK_AUTH_CODE`. Every authorized connection receives its own session ID; the session IDs are different while the authorization code remains the same until the configuration is changed.

Do not commit a real private authorization code to source control. Use an environment variable on the machine running the host.

## Browser input

Browser keyboard and mouse events are transported over a WebRTC data channel named `input`. The Windows host validates and bounds these events before passing them to an optional native `SendInput` backend.

The native input backend is **disabled by default**. To enable keyboard/mouse injection on the Windows host, set:

### Command Prompt

```bat
set ESPLINK_INPUT_ENABLED=1
python -m host.host_server
```

### PowerShell

```powershell
$env:ESPLINK_INPUT_ENABLED="1"
python -m host.host_server
```

Gamepad transport is part of the protocol but does not yet inject a virtual controller on Windows.

## Audio

The WebRTC host can capture the Windows default speaker mix through WASAPI loopback using the optional SoundCard dependency. Audio capture is non-fatal: if loopback is unavailable, video streaming can continue and the browser diagnostics panel reports the audio failure.

## Cross-network Quick Tunnel discovery

ESPLink can use a Cloudflare Quick Tunnel for the Windows host without requiring a Cloudflare account. The helper in `tools/remote_share.py` starts `cloudflared tunnel --url <local-url>`, detects the temporary `trycloudflare.com` address, and publishes that address to KeyVal.

Set `ESPDEVLINK_KEYVAL_KEY` on the Windows host and put the same long random key in `KEYVAL_KEY` in `src/main.cpp`. Do not commit a real key to source control.

KeyVal is only used as a tiny rendezvous/address-book service. It does not carry WebRTC video, audio, or input traffic.

```text
Windows host -> Quick Tunnel -> trycloudflare.com
      |
      +------ publish URL -> KeyVal
                              ^
                              |
ESP32 -> KeyVal lookup -------+
        -> current tunnel URL
```

## Cross-network WebRTC

ESPLink supports browser ICE configuration through the authenticated `/api/webrtc/config` endpoint. Local host/LAN candidates are used by default. For internet connections, configure a public STUN server and, when direct connectivity is not possible, an authenticated TURN relay.

The preferred configuration variable is `ESPLINK_ICE_SERVERS`, containing a JSON array of ICE-server objects. Each object may contain `urls`, `username`, and `credential`:

```powershell
$env:ESPLINK_ICE_SERVERS='[{"urls":["stun:stun.example.com:3478"]},{"urls":["turns:turn.example.com:5349"],"username":"user","credential":"token"}]'
python -m host.host_server
```

The older `ESPLINK_STUN_URL` variable remains supported for simple comma-separated STUN URLs. TURN credentials are sent to the browser as part of peer setup, so use temporary or restricted credentials when possible and do not commit them to source control.

A TURN server is a relay for cases where the two endpoints cannot establish a direct path. It is not replaced by a second ESP32, and it may carry the media traffic, so bandwidth and cost should be considered. The browser and host still need a reachable HTTPS/HTTP signaling endpoint; exposing the host port alone is not a complete security solution.

## Testing

Run the full cross-platform test suite from the repository root:

```text
python -m unittest discover -s tests -p "test_*.py"
```

The tests cover game lifecycle behavior, authentication/session behavior, network helpers, streaming configuration/runtime, WebRTC signaling, browser input validation, simulator LAN configuration, loopback-audio initialization, and the Windows input safety gate.

## Current API layers

The ESP32/simulator API includes gateway status, PC status, heartbeat, authorization, connection, and signaling functionality. The Windows host also has its own local HTTP control API under `/api/host/*`.

The ESP32 does not run Windows executables or encode PC game video. The Windows host is responsible for those PC-side tasks.

## Streaming status

The host now has desktop/test video capture, optional Windows WASAPI loopback audio, validated browser keyboard/mouse transport, native Windows input injection behind an explicit safety gate, WebRTC diagnostics, and configurable ICE server support. The browser diagnostics panel reports connection state, media counters, audio availability, and input availability.

The remaining major PC-side work is encoder/runtime tuning and stronger session/network hardening. The ESP32 gateway/mDNS layer will be integrated after the PC/browser path is stable.
