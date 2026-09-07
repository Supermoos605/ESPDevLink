# ESPLink Network Layer

The network package separates local discovery, heartbeat reporting, and signaling transport from the Windows media host.

## Responsibilities

- `discovery.py` finds the host endpoint and local address.
- `heartbeat.py` reports host availability to the ESP32 or simulator.
- `remote.py` loads optional remote-signaling configuration.
- `relay.py` stores short-lived signaling messages for a peer.
- `transport.py` maps JSON-style requests to the authenticated relay.

## Signaling boundary

The relay carries signaling messages such as offers, answers, and ICE candidates. It does not encode video, capture audio, launch Windows executables, or replace a TURN server.

A production remote deployment must place the transport behind an authenticated encrypted HTTP or WebSocket service. Do not expose an unauthenticated relay directly to the public internet.

## Message lifecycle

1. A client registers with a client ID and session ID.
2. The transport returns a peer ID.
3. The client sends signaling messages to that peer.
4. The client polls and drains queued messages.
5. The client closes the peer when the session ends.

The in-memory implementation is intended for local development and as a transport adapter contract. It does not provide persistence, multi-process coordination, rate limiting across workers, or TURN media relay functionality.
