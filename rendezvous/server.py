"""Minimal ESPDevLink rendezvous service.

Stores a short-lived Cloudflare URL for each ESPDevLink device.
This service never handles WebRTC media.
"""

import os
import secrets
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

BIND = os.getenv("RENDEZVOUS_BIND", "0.0.0.0")
PORT = int(os.getenv("RENDEZVOUS_PORT", "8080"))
REGISTRATION_TOKEN = os.getenv("RENDEZVOUS_REGISTRATION_TOKEN", "")
TTL = int(os.getenv("RENDEZVOUS_TTL", "120"))

records = {}


def clean():
    now = time.time()
    for device_id in list(records):
        if records[device_id]["expires_at"] <= now:
            del records[device_id]


class Handler(BaseHTTPRequestHandler):
    server_version = "ESPDevLink-Rendezvous/1.0"

    def json(self, status, body):
        import json
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        return bool(REGISTRATION_TOKEN) and secrets.compare_digest(
            self.headers.get("Authorization", "").removeprefix("Bearer ").strip(),
            REGISTRATION_TOKEN,
        )

    def do_POST(self):
        if self.path != "/api/register":
            self.json(404, {"ok": False, "error": "not found"})
            return
        if not self.authorized():
            self.json(401, {"ok": False, "error": "unauthorized"})
            return

        import json
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length))
            device_id = str(body["device_id"]).strip()
            url = str(body["url"]).strip()
        except (ValueError, KeyError, json.JSONDecodeError):
            self.json(400, {"ok": False, "error": "invalid request"})
            return

        if not device_id or len(device_id) > 64:
            self.json(400, {"ok": False, "error": "invalid device_id"})
            return
        if not url.startswith("https://") or len(url) > 512:
            self.json(400, {"ok": False, "error": "url must be HTTPS"})
            return

        clean()
        expires = time.time() + TTL
        records[device_id] = {"url": url, "expires_at": expires}
        self.json(200, {"ok": True, "device_id": device_id, "expires_at": expires})

    def do_GET(self):
        prefix = "/api/lookup/"
        if not self.path.startswith(prefix):
            self.json(404, {"ok": False, "error": "not found"})
            return

        device_id = self.path[len(prefix):].strip("/")
        if not device_id or len(device_id) > 64:
            self.json(400, {"ok": False, "error": "invalid device_id"})
            return

        clean()
        record = records.get(device_id)
        if not record:
            self.json(200, {"ok": True, "online": False, "url": None})
            return

        self.json(200, {
            "ok": True,
            "online": True,
            "url": record["url"],
            "expires_at": record["expires_at"],
        })

    def log_message(self, fmt, *args):
        print("[rendezvous]", fmt % args)


if __name__ == "__main__":
    print(f"ESPDevLink rendezvous listening on {BIND}:{PORT}")
    ThreadingHTTPServer((BIND, PORT), Handler).serve_forever()
