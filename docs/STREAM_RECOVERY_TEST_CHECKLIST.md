# Stream Recovery Test Checklist

Use this checklist when the ESP32 and Windows host are available.

## Recovery triggers

- [ ] Start a stream and confirm the dashboard reaches `LIVE`.
- [ ] Temporarily interrupt the network and confirm the dashboard changes to `RECONNECTING`.
- [ ] Restore the network and confirm the stream returns to `LIVE`.
- [ ] Leave the host running without video frames and confirm the media watchdog reports `Video stream stalled.`.
- [ ] Delay the WebRTC connection and confirm the 15-second timeout reports `Connection timed out.`.
- [ ] Force an ICE failure and confirm recovery starts after the grace period.
- [ ] Press Retry during recovery and confirm only one connection attempt runs.
- [ ] Disconnect during recovery and confirm reconnect scheduling stops.

## Input safety during recovery

- [ ] Hold a keyboard key, trigger recovery, and confirm the host receives the key release.
- [ ] Hold a mouse button, trigger recovery, and confirm the host receives the button release.
- [ ] Touch or drag on the stream, trigger recovery, and confirm the input state is cleared.
- [ ] Confirm the selected game remains selected after recovery.

## Dashboard checks

- [ ] Connection state changes from `LIVE` to `RECONNECTING` to `LIVE`.
- [ ] Reconnect count increments and displays the current attempt limit.
- [ ] Last error shows the recovery reason.
- [ ] Latency, video, and audio metrics resume after restoration.
- [ ] The top status dot receives the correct state class and accessible label.
