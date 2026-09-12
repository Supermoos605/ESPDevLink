"""HTTP control and browser server for the ESPLink Windows host."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import threading
import time
from collections import defaultdict, deque
from secrets import token_urlsafe
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from .api import HostAPI
from .config import (
    ESP32_URL,
    AUTHORIZATION_CODE,
    COMPUTER_NAME,
    HEARTBEAT_SECONDS,
    CORS_ORIGINS,
)

HOST = "0.0.0.0"
PORT = 8765
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
api = HostAPI()
_auth_attempts = defaultdict(deque)
_AUTH_WINDOW_SECONDS = 60
_AUTH_MAX_ATTEMPTS = 10

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


class ESP32Heartbeat:
    def __init__(self):
        self.session = ""
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, name="esp32-heartbeat", daemon=True)

    def start(self):
        print(f"[ESP32] Target: {ESP32_URL}")
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=3)

    def request_json(self, path, payload):
        data = json.dumps(payload).encode("utf-8")
        request = Request(
            f"{ESP32_URL}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=3) as response:
            return json.loads(response.read().decode("utf-8"))

    def login(self):
        result = self.request_json("/api/pc/login", {"code": AUTHORIZATION_CODE})
        if not result.get("ok") or not result.get("session_id"):
            raise RuntimeError(result.get("error", "ESP32 PC login failed"))
        self.session = result["session_id"]
        print("[ESP32] PC session established.")

    def heartbeat(self):
        status = api.status()["host"]
        network = api.status()["network"]
        data = json.dumps({
            "name": status["name"],
            "ip": network["host"],
            "game": status["game"],
            "stream": status["stream"],
        }).encode("utf-8")
        request = Request(
            f"{ESP32_URL}/api/pc/heartbeat",
            data=data,
            headers={
                "Content-Type": "application/json",
                "X-ESPLink-PC-Session": self.session,
            },
            method="POST",
        )
        with urlopen(request, timeout=3) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not result.get("ok"):
            raise RuntimeError(result.get("error", "ESP32 heartbeat failed"))

    def run(self):
        while not self.stop_event.is_set():
            try:
                if not self.session:
                    self.login()
                self.heartbeat()
            except (HTTPError, URLError, TimeoutError, OSError, ValueError, RuntimeError) as exc:
                print(f"[ESP32] Heartbeat unavailable: {exc}")
                self.session = ""
            self.stop_event.wait(HEARTBEAT_SECONDS)


class HostHandler(BaseHTTPRequestHandler):
    def send_json(self, payload, status=200):
        data = json.dumps(payload).encode("utf-8")
        origin = self.headers.get("Origin", "")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if origin and origin.rstrip("/") in CORS_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-ESPLink-Session, X-ESPLink-Host-Session, X-ESPLink-Peer")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Request body must contain valid JSON") from exc
        if not isinstance(value, dict):
            raise ValueError("Request body must be a JSON object")
        return value

    def require_session(self, body=None):
        session_id = self.headers.get("X-ESPLink-Host-Session") or self.headers.get("X-ESPLink-Session", "")
        if not session_id and isinstance(body, dict):
            session_id = str(body.get("session_id", "")).strip()
        if not session_id:
            self.send_json({"ok": False, "error": "Authorization required"}, 401)
            return None
        try:
            api.host.sessions.get(session_id)
        except KeyError:
            self.send_json({"ok": False, "error": "Invalid session id"}, 401)
            return None
        return session_id

    def serve_static(self):
        request_path = urlsplit(self.path).path
        if request_path == "/":
            request_path = "/index.html"
        relative = Path(request_path.lstrip("/"))
        if not relative.parts or ".." in relative.parts:
            return False
        target = (DATA_DIR / relative).resolve()
        try:
            target.relative_to(DATA_DIR.resolve())
        except ValueError:
            return False
        if not target.is_file():
            return False
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPES.get(target.suffix.lower(), "application/octet-stream"))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        return True

    def do_OPTIONS(self):
        origin = self.headers.get("Origin", "")
        if origin and origin.rstrip("/") not in CORS_ORIGINS:
            self.send_json({"ok": False, "error": "Origin not allowed"}, 403)
            return
        self.send_json({"ok": True})

    def do_GET(self):
        try:
            path = urlsplit(self.path).path
            if path == "/api/status":
                status = api.status()
                self.send_json({"status": "online", "ip": status["network"]["host"], "mdns": status["network"]["mdns_name"], "authorization_required": True})
            elif path == "/api/host/status":
                self.send_json(api.status())
            elif path == "/api/host/health":
                self.send_json(api.health())
            elif path == "/api/games":
                self.send_json({"games": api.list_games()})
            elif path == "/api/pc":
                session_id = self.require_session()
                if session_id is not None:
                    status = api.status()["host"]
                    network = api.status()["network"]
                    self.send_json({
                        "name": status["name"],
                        "ip": network["host"],
                        "online": status["online"],
                        "game": status["game"],
                        "stream": status["stream"],
                    })
            elif path == "/api/stream/state":
                session_id = self.require_session()
                if session_id is not None:
                    status = api.status()["host"]
                    self.send_json({"state": status["stream"], "game": status["game"], "client_id": api.host.sessions.get(session_id).client_id})
            elif path == "/api/webrtc/config":
                session_id = self.require_session()
                if session_id is not None:
                    self.send_json(api.webrtc_config())
            elif path == "/api/webrtc/stats":
                session_id = self.require_session()
                if session_id is not None:
                    peer_id = self.headers.get("X-ESPLink-Peer", "")
                    self.send_json(api.signaling.stats(peer_id, session_id))
            elif path == "/api/webrtc/messages":
                session_id = self.require_session()
                if session_id is not None:
                    peer_id = self.headers.get("X-ESPLink-Peer", "")
                    messages = api.signaling.drain_outbound(peer_id, session_id)
                    self.send_json({"ok": True, "peer_id": peer_id, "messages": messages})
            elif not self.serve_static():
                self.send_json({"ok": False, "error": "Not found"}, 404)
        except KeyError as exc:
            self.send_json({"ok": False, "error": str(exc)}, 404)
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, 500)

    def do_POST(self):
        try:
            path = urlsplit(self.path).path
            if path in {"/api/auth", "/api/auth/login"}:
                now = time.monotonic()
                key = self.client_address[0]
                attempts = _auth_attempts[key]
                while attempts and now - attempts[0] > _AUTH_WINDOW_SECONDS:
                    attempts.popleft()
                if len(attempts) >= _AUTH_MAX_ATTEMPTS:
                    self.send_json({"ok": False, "error": "Too many authorization attempts; try again later."}, 429)
                    return
                attempts.append(now)
                body = self.read_json()
                result = api.authorize(str(body.get("code", "")), str(body.get("client_id") or token_urlsafe(12)))
                self.send_json({"ok": True, **result})
                return

            body = self.read_json()
            session_id = self.require_session(body)
            if session_id is None:
                return

            if path == "/api/games/launch":
                self.send_json({"ok": True, **api.launch_game(str(body.get("id", "")))})
            elif path == "/api/games/stop":
                self.send_json({"ok": True, **api.stop_game(str(body.get("id", "")))})
            elif path == "/api/connect":
                game_name = str(body.get("game", "")).strip()
                if not game_name:
                    raise ValueError("game is required")
                game = next((item for item in api.games.list() if item["name"] == game_name), None)
                if game is None:
                    if game_name != "Test Stream":
                        raise KeyError("Unknown game")
                    api.host.status_model.update(game=game_name)
                    api.start_stream()
                    self.send_json({"ok": True, "pc": api.status()["host"]["name"], "ip": api.status()["network"]["host"], "state": "CONNECTING", "game": game_name})
                    return
                game_definition = api.games.get(game["id"])
                if game_definition.id != "desktop" and (game_definition.launcher.lower() == "steam" or game_definition.executable):
                    api.launch_game(game_definition.id)
                else:
                    api.host.status_model.update(game=game_definition.name)
                api.start_stream()
                self.send_json({"ok": True, "pc": api.status()["host"]["name"], "ip": api.status()["network"]["host"], "state": "CONNECTING", "game": game_definition.name})
            elif path in {"/api/host/stream/start", "/api/stream/begin"}:
                self.send_json(api.start_stream())
            elif path in {"/api/host/stream/stop", "/api/stream/disconnect"}:
                api.stop_stream()
                api.host.status_model.update(game="", stream_state="ready")
                self.send_json({"ok": True, "state": "READY"})
            elif path in {"/api/webrtc/peer", "/api/webrtc/session"}:
                video_mode = body.get("video_mode")
                self.send_json({"ok": True, **api.create_peer(session_id, video_mode=video_mode)})
            elif path in {"/api/webrtc/signal", "/api/webrtc/message"}:
                peer_id = str(body.get("peer_id", self.headers.get("X-ESPLink-Peer", "")))
                message = body.get("message", body)
                if not isinstance(message, dict):
                    raise ValueError("message must be a JSON object")
                self.send_json({"ok": True, **api.signal_peer(peer_id, session_id, message)})
            elif path == "/api/webrtc/close":
                peer_id = str(body.get("peer_id", self.headers.get("X-ESPLink-Peer", "")))
                self.send_json({"ok": True, **api.close_peer(peer_id, session_id)})
            elif path == "/api/auth/logout":
                self.send_json(api.logout(session_id))
            else:
                self.send_json({"ok": False, "error": "Not found"}, 404)
        except PermissionError as exc:
            self.send_json({"ok": False, "error": str(exc)}, 403)
        except KeyError as exc:
            self.send_json({"ok": False, "error": str(exc)}, 404)
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, 400)
        except RuntimeError as exc:
            self.send_json({"ok": False, "error": str(exc)}, 409)
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, 500)

    def log_message(self, fmt, *args):
        print("[HOST] " + fmt % args)


def main():
    server = ThreadingHTTPServer((HOST, PORT), HostHandler)
    heartbeat = ESP32Heartbeat()
    heartbeat.start()
    print(f"ESPLink Windows Host: http://0.0.0.0:{PORT}")
    print("Browser UI: http://<PC-IP>:8765/")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nHost stopped.")
    finally:
        heartbeat.stop()
        api.signaling.close_all()
        server.server_close()


if __name__ == "__main__":
    main()
