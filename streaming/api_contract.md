# ESPLink Browser ↔ Simulator/ESP32 API Contract v1

These endpoints are intentionally small so the browser UI can be developed against the local simulator before hardware is available.

## Host information

`GET /api/pc`

Returns:

```json
{"name":"Gaming PC","ip":"192.168.1.10","online":true,"game":"","stream":"Ready"}
```

## Connect

`POST /api/connect`

Body:

```json
{"game":"Example Game","client_id":"browser"}
```

A successful response returns `ok`, host information, selected game, and the current stream state.

## Stream state

`GET /api/stream/state`

Returns the current session state, game, and client ID.

## Begin stream

`POST /api/stream/begin`

Moves an accepted connection from `connecting` to `streaming`.

## Disconnect

`POST /api/stream/disconnect`

Stops the current session and returns the host to `ready`.

## Heartbeat

`POST /api/pc/heartbeat`

The Windows host reports its name, IP, current game, and stream state. The simulator expires a host after five seconds without a heartbeat.

## Compatibility rule

The simulator is the reference implementation for browser-side development. The physical ESP32 should implement the same request paths and JSON fields when this API is moved into the firmware.
