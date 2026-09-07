# ESPLink Streaming Protocol v1

This document defines the application-level messages that will sit above the eventual WebRTC transport.

## Host lifecycle

```text
Offline -> Ready -> Connecting -> Streaming -> Stopping -> Ready
                         |
                         +-> Error -> Ready
```

## Message envelope

Every signaling/control message contains:

```json
{
  "protocol": 1,
  "type": "..."
}
```

## Messages

### `hello`

Sent by a client when beginning a session.

```json
{"protocol":1,"type":"hello","client":"browser"}
```

### `hello_ack`

Host/ESPLink acknowledges a compatible client.

### `stream_request`

Requests a stream from the selected host.

```json
{"protocol":1,"type":"stream_request","game":""}
```

### `stream_accept`

Indicates that the host accepted the request and signaling can proceed.

### `stream_state`

Reports one of the states defined in `host_protocol.py`.

### `stream_stop`

Requests the current session to stop.

### `error`

Reports a machine-readable error code and optional human-readable message.

## Design rule

The ESP32 should remain a lightweight discovery/control device. Game media should use a browser-compatible real-time transport rather than passing the video stream through the ESP32.
