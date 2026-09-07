# ESPLink Browser Streaming

This directory is the next-stage streaming prototype for ESPLink.

## Goal

The intended architecture is:

```text
Browser client
      |
      | WebRTC media + data channels
      v
Windows ESPLink Host
      |
      +-- screen/game capture
      +-- hardware/software video encoder
      +-- audio capture
      +-- keyboard/mouse/controller input
      |
     Game
```

The ESP32 remains the discovery/control gateway. It is not expected to encode a PC game stream.

## Development order

1. Establish browser-to-Windows signaling.
2. Establish a WebRTC peer connection.
3. Add a test video source before capturing games.
4. Add Windows screen/game capture.
5. Add audio.
6. Add input over a WebRTC data channel.
7. Integrate the ESP32 `/api/connect` handshake.
8. Add remote-network support.

The first implementation intentionally uses a test media source. This lets signaling and WebRTC connectivity be verified before adding the complexity of Windows game capture and hardware encoding.
