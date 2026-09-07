"""Local-only HTTP server for the ESPLink signaling relay."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .transport import RelayTransport


class RelayRequestHandler(BaseHTTPRequestHandler):
    transport = RelayTransport()
    max_body_bytes = 64 * 1024

    def _write(self, status: int, body: dict[str, Any]) -> None:
        encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self) -> None:  # noqa: N802
        action = self.path.removeprefix("/")
        if action not in {"register", "send", "poll", "close"}:
            self._write(404, {"error": "unknown_action"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > self.max_body_bytes:
                raise ValueError("request body too large")
            raw = self.rfile.read(length)
            payload = json.loads(raw or b"{}")
            if not isinstance(payload, dict):
                raise ValueError("payload must be an object")
        except (ValueError, TypeError, json.JSONDecodeError):
            self._write(400, {"error": "invalid_json"})
            return

        token = self.headers.get("Authorization")
        if token and token.lower().startswith("bearer "):
            token = token[7:].strip()
        response = self.transport.handle(action, payload, token)
        self._write(response.status, response.body)

    def log_message(self, format: str, *args: object) -> None:
        return


def create_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    """Create a local relay server; callers decide when to serve it."""
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("relay server must bind to localhost")
    return ThreadingHTTPServer((host, port), RelayRequestHandler)


if __name__ == "__main__":
    server = create_server()
    print("ESPLink relay listening on http://127.0.0.1:8765")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
