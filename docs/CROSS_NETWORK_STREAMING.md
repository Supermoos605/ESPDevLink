# Cross-network streaming

ESPLink keeps local streaming as the default. Cross-network support is an optional connection path for browsers that are not on the same LAN as the Windows host.

## Connection layers

1. The browser obtains an authenticated session and WebRTC configuration from the signaling endpoint.
2. WebRTC attempts a direct connection using host/LAN candidates and configured ICE servers.
3. A public STUN server can help discover a usable network path.
4. A TURN server can relay media when a direct path is unavailable.

The ESP32 is not the media relay and does not run the Windows game. It remains the local discovery and browser-facing gateway. The Windows host continues to capture the game and provide the WebRTC media and input channels.

## Configuration

The Windows host can publish an externally reachable signaling URL to the ESP32 with `ESPLINK_PUBLIC_URL`. When set, browsers using the ESP32 gateway prefer this URL instead of constructing `http://<LAN-PC-IP>:8765`. This is the first step toward remote-network connections; the URL must already route to the Windows host HTTP service.

```powershell
$env:ESPLINK_PUBLIC_URL="https://stream.example.com"
```

Keep the existing LAN setup unchanged by leaving `ESPLINK_PUBLIC_URL` empty. For an Internet-facing deployment, use HTTPS for the signaling endpoint.


Set `ESPLINK_ICE_SERVERS` on the Windows host to a JSON array of ICE-server objects:

```powershell
$env:ESPLINK_ICE_SERVERS='[{"urls":["stun:stun.example.com:3478"]},{"urls":["turns:turn.example.com:5349"],"username":"temporary-user","credential":"temporary-password"}]'
python -m host.host_server
```

Each object may contain `urls`, `username`, and `credential`. Use temporary or restricted TURN credentials and never commit real credentials to the repository.

The older `ESPLINK_STUN_URL` setting remains available for simple STUN-only setups.

## Requirements for an internet connection

- The browser must be able to reach the signaling endpoint.
- The signaling endpoint must be protected by the existing authorization/session mechanism.
- The host and browser need compatible WebRTC support.
- A TURN relay may be required because many networks block direct peer-to-peer connectivity.
- TURN bandwidth and server availability affect the quality and cost of remote streaming.

Opening the host HTTP port alone is not a complete remote-streaming solution. It exposes signaling but does not guarantee that WebRTC media can traverse NATs or firewalls.

## Safe development order

1. Keep local LAN streaming unchanged.
2. Configure and validate an externally reachable signaling URL.
3. Validate ICE configuration before sending it to the browser.
4. Test signaling and ICE failure messages independently of desktop capture.
5. Test with a private relay or tunnel before exposing the host publicly.
6. Add remote-mode UI only after the network path is proven.
