# ESPLink WebRTC Signaling Protocol v1

ESPLink uses the existing authenticated API as the signaling relay. WebRTC itself carries the media directly between the Windows host and browser; the ESPLink gateway does not process the video/audio stream.

WebRTC negotiation requires an offer/answer exchange and ICE candidate exchange. The signaling transport is intentionally independent of WebRTC. See MDN's WebRTC signaling documentation for the standard flow.

## Session

Every streaming connection uses the existing unique ESPLink session ID. A separate random `peer_id` identifies the WebRTC negotiation instance.

## Endpoints

`POST /api/webrtc/session`

Creates a signaling session for the authenticated ESPLink session.

Request:

```json
{"game":"Desktop"}
```

Response:

```json
{"ok":true,"peer_id":"...","state":"new"}
```

`POST /api/webrtc/message`

Relays one signaling message between the browser and Windows host.

Supported message types:

- `offer`
- `answer`
- `ice-candidate`
- `ready`
- `close`

The server treats SDP and ICE payloads as opaque data and does not modify them.

`GET /api/webrtc/messages?peer_id=...`

Returns queued messages for the authenticated session and peer. Messages are removed after retrieval.

`POST /api/webrtc/close`

Closes the signaling peer and removes its queued messages.

## Security

All signaling endpoints require the existing ESPLink session ID. A peer ID is scoped to that session and cannot be used by another authenticated session.

The authorization code remains the shared gateway authorization mechanism; peer IDs remain unique per streaming negotiation.

## Media

The signaling layer does not capture, encode, decode, or proxy media. The eventual Windows host will create an `RTCPeerConnection`, add the desktop/audio tracks, and exchange SDP/ICE through these endpoints. The browser will attach the received tracks to the existing stream video element.
