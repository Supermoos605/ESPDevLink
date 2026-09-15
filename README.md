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


## Quick start guide

ESPLink has two main parts:

- **ESP32 gateway:** serves the browser UI, provides local discovery through `steamlink.local`, and helps the browser find the Windows host.
- **Windows host:** actually runs the game, captures the desktop/audio, handles WebRTC signaling, and receives keyboard/mouse input.

The ESP32 is therefore a **gateway, not the gaming computer**. The game continues running on the Windows PC; the phone/tablet only needs a compatible browser.

### 1. Install the Windows requirements

On the Windows gaming PC, install Python and make sure the repository is available locally.

For remote connections, install **cloudflared** and make sure the `cloudflared` command is available from PowerShell/Command Prompt.

Verify it with:

```text
cloudflared version
```

### 2. Configure the host

For normal development/testing:

#### PowerShell

```powershell
$env:ESPLINK_INPUT_ENABLED="1"
$env:ESPLINK_AUTH_CODE="DEVTEST"
python -m host.host_server
```

The input flag enables the Windows keyboard/mouse injection backend. The authorization code must match the code configured on the ESP32/simulator.

For personal use, **do not commit your real authorization code, KeyVal key, or TURN credentials to GitHub**.

### 3. The easy way: `start_server.bat`

The repository includes `start_server.bat` so you do not have to type the startup commands every time.

Double-click it and choose:

```text
1. Start server now
2. Schedule daily start
3. Cancel scheduled start
4. Show current schedule
5. Exit
```

**Start server now** launches the Windows host.

**Schedule daily start** creates a Windows Task Scheduler entry. For example, entering `07:00` makes Windows start ESPLink every day at that time. The PC must be available for the scheduled task to run.

If the supervised host exits unexpectedly, the launcher waits briefly and attempts to restart it.

### 4. Local connection

When the ESP32 is on the same LAN as the Windows PC:

```text
Phone/tablet browser
        |
        v
   steamlink.local
        |
        v
      ESP32
        |
        v
 Windows ESPLink host
        |
        v
   Game + WebRTC
```

Open `steamlink.local` in the browser and connect to the available host.

The ESP32 handles the gateway/discovery side; the Windows host handles the actual stream.

### 5. Remote connection

For a connection from outside the home network, the Windows host can start a Cloudflare Quick Tunnel.

The Quick Tunnel URL is a **rendezvous address**. KeyVal does not carry the game's video or audio. The actual media/input path is WebRTC between the browser and Windows host.

Remote WebRTC connectivity may additionally require suitable ICE/STUN/TURN configuration. A Quick Tunnel by itself does not guarantee that WebRTC media can establish a direct path.

### 6. Streaming

The Windows PC provides the real-time media path:

```text
Windows desktop
     |
     +--> Video --> WebRTC --> Browser
     |
     +--> Audio --> WebRTC --> Browser
```

The stream page provides connection and stream diagnostics. Video quality, FPS, bitrate, connection state, packet loss, and related WebRTC statistics can be inspected while testing.

### 7. Input

ESPLink currently supports:

- Keyboard
- Mouse
- Browser touch controls

Gamepad input is **not part of the current project plan**.

Keyboard/mouse injection on Windows is deliberately protected by the `ESPLINK_INPUT_ENABLED` setting.

### 8. Audio troubleshooting

Audio is the part that deserves the most attention during real-world testing.

A successful WebRTC connection can show an audio track and receiver while the computer still produces no audible sound. If that happens, use the stream diagnostics to determine whether the problem is Windows audio capture, WebRTC transport, browser playback, or the selected browser output device.

The Windows host uses WASAPI loopback through the optional SoundCard dependency to capture the speaker mix. The browser must also be allowed to play the received audio.

### 9. Testing without the ESP32

If the ESP32 is unavailable, run the simulator:

```text
python simulator/esp_link_simulator.py
```

Then point the heartbeat agent at it:

```powershell
$env:ESPLINK_ESP32="http://127.0.0.1:8080"
python -m host.network.heartbeat
```

This lets you work on the Windows/browser side without having the physical gateway connected.

### 10. Troubleshooting checklist

**Host is offline**

- Make sure `host.host_server` is running.
- Check that port `8765` is available.
- Check the host authorization code.
- For remote mode, verify that `cloudflared` started successfully and that the Quick Tunnel URL was published.

**Remote lookup is empty**

- Check that the KeyVal key is configured on both sides.
- Make sure the host successfully published the current Quick Tunnel URL.
- Remember that Quick Tunnel addresses are temporary and change when a new tunnel is created.

**Remote WebRTC connects but media does not**

- Check the ICE configuration.
- For difficult NAT situations, a TURN relay may be required.
- Use the stream diagnostics to inspect ICE and connection states.

**Video works but audio does not**

- Check the Windows playback/capture device.
- Check the audio diagnostics.
- Press the browser's audio/unmute control after the stream connects.
- Check that the browser is allowed to play audio and is using the intended output device.

**Input does not work**

- Confirm that `ESPLINK_INPUT_ENABLED=1` is set on the Windows host.
- Verify that the browser's input channel reaches the host.
- Check the input diagnostics.

### 11. Useful commands

Start the host directly:

```text
python -m host.host_server
```

Start the simulator:

```text
python simulator/esp_link_simulator.py
```

Run the tests:

```text
python -m unittest discover -s tests -p "test_*.py"
```

Check Cloudflare:

```text
cloudflared version
```

For normal personal use, `start_server.bat` is the recommended Windows starting point.

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

Gamepad input is not part of the current project plan. ESPLink focuses on keyboard, mouse, and browser touch input.

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
