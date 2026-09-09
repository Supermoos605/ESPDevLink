# WebRTC Reconnect Test Checklist

Use this checklist after the ESP32 and Windows host are available.

## Before testing

- [ ] The ESP32 is connected to the same network as the receiving device.
- [ ] The ESP32 reports the Windows host IP at `/api/pc`.
- [ ] The Windows host is listening on port `8765`.
- [ ] The selected game is available to the Windows host.
- [ ] The browser can open `stream.html`.

## Initial connection

- [ ] The page changes from `READY` to `CONNECTING`.
- [ ] The host authorization prompt appears.
- [ ] The page reaches `LIVE` after the WebRTC answer arrives.
- [ ] The video track appears and playback starts.
- [ ] Keyboard, mouse, and touch input work.

## Reconnect behavior

1. Start a stream and confirm that it reaches `LIVE`.
2. Temporarily stop or restart the Windows streaming host.
3. Confirm that the page displays a retry message.
4. Confirm that retries occur at approximately 1, 2, 4, 8, and 16 seconds.
5. Restore the host before the fifth retry is exhausted.
6. Confirm that the page returns to `LIVE`.
7. Confirm that a successful connection resets the retry counter.

## Disconnect behavior

- [ ] Pressing **Disconnect** stops the peer connection.
- [ ] A pending retry is cancelled.
- [ ] The video track is stopped.
- [ ] The page returns to `READY`.
- [ ] No new connection starts until the page is loaded again.

## Diagnostics

The browser console and the diagnostics panel should show:

- `connectionState`
- `iceConnectionState`
- `signalingState`
- `signal sent` and `signal received`
- `reconnect`
- `failure`

A retry message alone does not prove that the host recovered; verify that a new video track is received and the state returns to `LIVE`.
