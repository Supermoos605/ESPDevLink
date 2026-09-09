# ESPLink WebRTC Troubleshooting

## Browser shows `ICE servers configured — 0`

This is normal for local-network testing. The host and browser will try direct ICE candidates first. For connections across different networks, configure STUN or TURN servers with `ESPLINK_ICE_SERVERS` before starting the host.

Example PowerShell configuration:

```powershell
$env:ESPLINK_AUTH_CODE="DEVTEST"
$env:ESPLINK_ICE_SERVERS='[{"urls":"stun:stun.l.google.com:19302"}]'
python -m host.host_server
```

## Browser cannot reach the host

1. Confirm the Windows host is running.
2. Confirm TCP port `8765` is allowed through Windows Firewall.
3. Confirm the ESP32 and receiving device are on the same network for local testing.
4. Check that the ESP32 reports the correct Windows host IP address.
5. Refresh the stream page and retry authorization.

## WebRTC diagnostics

The stream page displays a diagnostics panel automatically when a connection starts. Useful entries include:

- `session created`: the host created a WebRTC peer session.
- `ICE servers configured`: the number of configured STUN/TURN server entries.
- `local ICE candidate`: the browser discovered a network route.
- `track received`: the browser received an audio or video track.
- `connectionState`: the final WebRTC connection state.

## Connection reaches `failed`

For local testing, check firewall rules and verify that both devices can reach the host IP. For cross-network testing, a STUN server may help discover the public route, while a TURN server is required when both sides cannot establish a direct connection.

## No video but audio or input works

Check browser autoplay restrictions. Click the video area once to start playback. Also verify that the selected stream mode is supported by the Windows host and that the capture backend is installed.

## Host dependency reminder

Real Windows capture and WebRTC streaming require the packages in the repository's root `requirements.txt`. Install them on Windows rather than in a Linux Codespace.
