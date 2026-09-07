"""ESPLink local simulator with per-session authorization and WebRTC signaling."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse, json, secrets, socket, sys, time

ROOT = Path(__file__).resolve().parent.parent
STREAMING_DIR = ROOT / "streaming"
DATA_DIR = ROOT / "data"
if str(STREAMING_DIR) not in sys.path:
    sys.path.insert(0, str(STREAMING_DIR))
from session_state import StreamSession
from signaling import SignalingManager

HOST, PORT = "0.0.0.0", 8080
CONFIG = Path(__file__).resolve().parent / "config.json"


def load_config():
    defaults = {
        "host": {"name": socket.gethostname(), "ip": "auto", "online": True, "game": "", "stream": "Ready"},
        "gateway": {"mdns": "steamlink.local", "wifi": -42, "bind_host": "0.0.0.0", "port": 8080},
        "security": {"authorization_code": "CHANGE-ME"},
        "heartbeat_required": False,
        "heartbeat_timeout_seconds": 5,
    }
    try:
        loaded = json.loads(CONFIG.read_text(encoding="utf-8"))
        for section in ("host", "gateway", "security"):
            if isinstance(loaded.get(section), dict):
                defaults[section].update(loaded[section])
        for key in ("heartbeat_required", "heartbeat_timeout_seconds"):
            if key in loaded:
                defaults[key] = loaded[key]
    except (OSError, ValueError, TypeError):
        pass
    return defaults


config = load_config()
PC_TIMEOUT = float(config["heartbeat_timeout_seconds"])
HEARTBEAT_REQUIRED = bool(config["heartbeat_required"])
sessions = {}
signaling = SignalingManager()
state = {
    "name": str(config["host"].get("name", socket.gethostname())),
    "ip": str(config["host"].get("ip", "auto")),
    "online": bool(config["host"].get("online", True)),
    "game": str(config["host"].get("game", "")),
    "stream": str(config["host"].get("stream", "Ready")),
    "last_heartbeat": time.monotonic(),
}


def local_ip():
    """Return the LAN address the simulator can normally be reached on."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("1.1.1.1", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


if state["ip"] in {"", "auto", "localhost"}:
    state["ip"] = local_ip()


def pc_online():
    if not state["online"]:
        return False
    if not HEARTBEAT_REQUIRED:
        return True
    return time.monotonic() - state["last_heartbeat"] <= PC_TIMEOUT


def new_session():
    sid = secrets.token_urlsafe(24)
    sessions[sid] = {"created": time.time(), "last_seen": time.time(), "stream": StreamSession()}
    return sid


def get_session(handler):
    sid = handler.headers.get("X-ESPLink-Session", "")
    session = sessions.get(sid)
    if session:
        session["last_seen"] = time.time()
    return sid, session


class Handler(BaseHTTPRequestHandler):
    def json_response(self, obj, code=200):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        try:
            return json.loads(raw.decode()) if raw else {}
        except (ValueError, UnicodeDecodeError):
            return None

    def require_session(self):
        sid, session = get_session(self)
        if not session:
            self.json_response({"ok": False, "error": "Authorization required"}, 401)
            return None
        return session

    def require_webrtc_peer(self):
        peer_id = self.headers.get("X-ESPLink-Peer", "")
        try:
            return signaling.get(peer_id)
        except (KeyError, ValueError):
            self.json_response({"ok": False, "error": "Invalid WebRTC peer"}, 404)
            return None

    def serve_data_file(self):
        requested = self.path.split("?", 1)[0]
        if requested == "/":
            requested = "/index.html"
        if not requested.startswith("/") or ".." in Path(requested).parts:
            return False
        target = (DATA_DIR / requested.lstrip("/")).resolve()
        try:
            target.relative_to(DATA_DIR.resolve())
        except ValueError:
            return False
        if not target.is_file():
            return False
        content_types = {
            ".html": "text/html; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".ico": "image/x-icon",
            ".svg": "image/svg+xml",
        }
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_types.get(target.suffix.lower(), "application/octet-stream"))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        return True

    def do_GET(self):
        if self.path == "/api/status":
            self.json_response({
                "status": "online",
                "ip": state["ip"],
                "mdns": config["gateway"].get("mdns", "steamlink.local"),
                "wifi": config["gateway"].get("wifi", -42),
                "authorization_required": True,
            })
            return
        if self.path == "/api/auth/status":
            sid, session = get_session(self)
            self.json_response({"authorized": bool(session), "session_id": sid if session else None})
            return
        if self.path == "/api/pc":
            if self.require_session() is None:
                return
            self.json_response({"name": state["name"], "ip": state["ip"], "online": pc_online(), "game": state["game"], "stream": state["stream"]})
            return
        if self.path == "/api/stream/state":
            session = self.require_session()
            if session is None:
                return
            stream = session["stream"]
            self.json_response({"state": stream.state, "game": stream.game, "client_id": stream.client_id})
            return
        if self.path == "/api/webrtc/messages":
            if self.require_session() is None:
                return
            peer = self.require_webrtc_peer()
            if peer is None:
                return
            self.json_response({"ok": True, "peer_id": peer.peer_id, "messages": peer.drain()})
            return
        if self.serve_data_file():
            return
        self.send_error(404, "404 Not Found")

    def do_POST(self):
        if self.path == "/api/auth/login":
            payload = self.body()
            if payload is None:
                self.json_response({"ok": False, "error": "Invalid JSON"}, 400)
                return
            supplied = str(payload.get("code", ""))
            expected = str(config["security"].get("authorization_code", "CHANGE-ME"))
            if not secrets.compare_digest(supplied, expected):
                self.json_response({"ok": False, "error": "Invalid authorization code"}, 403)
                return
            sid = new_session()
            self.json_response({"ok": True, "session_id": sid})
            return
        if self.path == "/api/auth/logout":
            sid, _ = get_session(self)
            sessions.pop(sid, None)
            self.json_response({"ok": True})
            return
        session = self.require_session()
        if session is None:
            return
        stream = session["stream"]
        if self.path == "/api/connect":
            if not pc_online():
                self.json_response({"ok": False, "error": "PC is offline"}, 503)
                return
            payload = self.body()
            if payload is None:
                self.json_response({"ok": False, "error": "Invalid JSON"}, 400)
                return
            game = str(payload.get("game", state["game"])).strip()
            try:
                if stream.state == "offline":
                    stream.transition("ready")
                stream.start(game, str(payload.get("client_id", "browser")))
            except ValueError as exc:
                self.json_response({"ok": False, "error": str(exc)}, 409)
                return
            state["game"] = stream.game
            state["stream"] = stream.state.capitalize()
            self.json_response({"ok": True, "pc": state["name"], "ip": state["ip"], "state": state["stream"], "game": stream.game, "session_id": get_session(self)[0]})
            return
        if self.path == "/api/stream/begin":
            try:
                stream.begin_stream()
            except ValueError as exc:
                self.json_response({"ok": False, "error": str(exc)}, 409)
                return
            state["stream"] = stream.state.capitalize()
            self.json_response({"ok": True, "state": state["stream"]})
            return
        if self.path == "/api/stream/disconnect":
            try:
                stream.stop()
            except ValueError as exc:
                self.json_response({"ok": False, "error": str(exc)}, 409)
                return
            state["game"] = ""
            state["stream"] = stream.state.capitalize()
            self.json_response({"ok": True, "state": state["stream"]})
            return
        if self.path == "/api/pc/heartbeat":
            payload = self.body()
            if payload is None:
                self.json_response({"error": "Invalid JSON"}, 400)
                return
            state["name"] = str(payload.get("name", state["name"]))
            state["ip"] = str(payload.get("ip", state["ip"]))
            state["game"] = str(payload.get("game", state["game"]))
            state["online"] = True
            state["last_heartbeat"] = time.monotonic()
            self.json_response({"ok": True, "online": True})
            return
        if self.path == "/api/webrtc/session":
            peer = signaling.create(str(session.get("client_id", "browser")))
            self.json_response({"ok": True, "peer_id": peer.peer_id, "created_at": peer.created_at})
            return
        if self.path == "/api/webrtc/message":
            peer = self.require_webrtc_peer()
            if peer is None:
                return
            payload = self.body()
            if not isinstance(payload, dict) or not payload.get("type"):
                self.json_response({"ok": False, "error": "Message type required"}, 400)
                return
            peer.queue(payload)
            self.json_response({"ok": True})
            return
        if self.path == "/api/webrtc/close":
            peer = self.require_webrtc_peer()
            if peer is None:
                return
            signaling.close(peer.peer_id)
            self.json_response({"ok": True})
            return
        self.send_error(404, "404 Not Found")

    def log_message(self, fmt, *args):
        print("[SIM] " + fmt % args)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the ESPLink browser/host simulator.")
    parser.add_argument("--host", default=str(config["gateway"].get("bind_host", HOST)), help="Interface to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=int(config["gateway"].get("port", PORT)), help="HTTP port (default: 8080)")
    args = parser.parse_args(argv)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print("========================================")
    print("          ESPLink Local Simulator")
    print("========================================")
    print(f"Bind:      http://{args.host}:{args.port}")
    print(f"Local:     http://127.0.0.1:{args.port}")
    print(f"LAN:       http://{state['ip']}:{args.port}")
    print(f"PC name:   {state['name']}")
    print(f"PC IP:     {state['ip']}")
    print(f"PC online: {state['online']}")
    print(f"mDNS name: {config['gateway'].get('mdns', 'steamlink.local')} (simulated)")
    print("Authorization: configured in simulator/config.json")
    print()
    print("Open the LAN URL from another device on the same network.")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSimulator stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
