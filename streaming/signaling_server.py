"""ESPLink development signaling server.

This is intentionally a small, dependency-free HTTP signaling service. It is
not the game streamer itself. It gives the browser and Windows host a common
place to exchange a WebRTC offer/answer and ICE candidates during development.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

HOST = "127.0.0.1"
PORT = 8765

lock = threading.Lock()
state = {
    "offer": None,
    "answer": None,
    "browser_candidates": [],
    "host_candidates": [],
}


def read_json(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None


class Handler(BaseHTTPRequestHandler):
    def send_json(self, value, status=200):
        data = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/signaling/state":
            with lock:
                self.send_json(state)
            return
        self.send_error(404, "Not Found")

    def do_POST(self):
        if not self.path.startswith("/api/signaling/"):
            self.send_error(404, "Not Found")
            return

        payload = read_json(self)
        if payload is None:
            self.send_json({"ok": False, "error": "Invalid JSON"}, 400)
            return

        with lock:
            if self.path == "/api/signaling/offer":
                state["offer"] = payload
            elif self.path == "/api/signaling/answer":
                state["answer"] = payload
            elif self.path == "/api/signaling/browser-candidate":
                state["browser_candidates"].append(payload)
            elif self.path == "/api/signaling/host-candidate":
                state["host_candidates"].append(payload)
            elif self.path == "/api/signaling/reset":
                state["offer"] = None
                state["answer"] = None
                state["browser_candidates"] = []
                state["host_candidates"] = []
            else:
                self.send_error(404, "Not Found")
                return

        self.send_json({"ok": True})

    def log_message(self, fmt, *args):
        print("[SIGNAL] " + fmt % args)


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("ESPLink signaling server")
    print(f"Listening on http://{HOST}:{PORT}")
    print("This is a development signaling server, not a media server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
