#!/usr/bin/env python3
"""Start an ESPDevLink Cloudflare Quick Tunnel and publish its URL."""

import os
import re
import signal
import subprocess
import sys
import time
import json
import urllib.request
import urllib.error
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from include.espdevlink_secrets import KEYVAL_KEY as LOCAL_KEYVAL_KEY
except ImportError:
    LOCAL_KEYVAL_KEY = ""

HOST_URL = os.environ.get("ESPDEVLINK_LOCAL_URL", "http://127.0.0.1:8765")
CLOUDFLARED = os.environ.get("CLOUDFLARED_PATH", "cloudflared")
URL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
TUNNEL_START_TIMEOUT = 30
KEYVAL_BASE_URL = "https://api.keyval.org"
KEYVAL_KEY = os.environ.get("ESPDEVLINK_KEYVAL_KEY", LOCAL_KEYVAL_KEY).strip()


def publish_url(public_url: str) -> bool:
    if len(KEYVAL_KEY) < 10:
        print("[ERROR] ESPDEVLINK_KEYVAL_KEY must be at least 10 characters.")
        return False

    endpoint = f"{KEYVAL_BASE_URL}/set"
    body = json.dumps({"key": KEYVAL_KEY, "val": public_url}).encode("utf-8")

    try:
        request = urllib.request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151.0 Safari/537.36",
                "Origin": "https://keyval.org",
                "Referer": "https://keyval.org/",
            },
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            result = response.read().decode("utf-8", errors="replace").strip()
        print(f"[ESPDevLink] Published Quick Tunnel URL: {result}")
        return True
    except urllib.error.HTTPError as exc:
        try:
            response_body = exc.read().decode("utf-8", errors="replace").strip()
        except Exception:
            response_body = "(unable to read response body)"
        print(f"[ERROR] KeyVal publish failed: HTTP {exc.code} {exc.reason}")
        print(f"[ERROR] KeyVal response: {response_body or '(empty response body)'}")
        return False
    except Exception as exc:
        print(f"[ERROR] KeyVal publish failed: {exc}")
        return False


def start_tunnel() -> tuple[subprocess.Popen, str]:
    print(f"[ESPDevLink] Starting Quick Tunnel for {HOST_URL}")
    try:
        tunnel = subprocess.Popen(
            [CLOUDFLARED, "tunnel", "--url", HOST_URL],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        raise RuntimeError("cloudflared was not found. Install cloudflared or set CLOUDFLARED_PATH.")

    deadline = time.monotonic() + TUNNEL_START_TIMEOUT
    while time.monotonic() < deadline:
        line = tunnel.stdout.readline()
        if not line:
            if tunnel.poll() is not None:
                raise RuntimeError(f"cloudflared exited with code {tunnel.returncode}.")
            time.sleep(0.1)
            continue
        print("[cloudflared]", line.rstrip())
        match = URL_PATTERN.search(line)
        if match:
            return tunnel, match.group(0)

    if tunnel.poll() is None:
        tunnel.terminate()
    raise RuntimeError("Timed out waiting for a trycloudflare.com URL.")


def main() -> int:
    tunnel = None
    try:
        while True:
            try:
                tunnel, public_url = start_tunnel()
                print(f"[ESPDevLink] Public URL: {public_url}")
                if not publish_url(public_url):
                    return 1

                print("[ESPDevLink] Tunnel is running. If it disconnects, a new tunnel will be created automatically.")
                while tunnel.poll() is None:
                    time.sleep(1)

                print(f"[ESPDevLink] cloudflared exited with code {tunnel.returncode}. Restarting...")
                tunnel = None
                time.sleep(2)
            except RuntimeError as exc:
                print(f"[ERROR] {exc}")
                if tunnel is not None and tunnel.poll() is None:
                    tunnel.terminate()
                return 1
    except KeyboardInterrupt:
        print("\n[ESPDevLink] Stopping tunnel...")
        return 0
    finally:
        if tunnel is not None and tunnel.poll() is None:
            if sys.platform == "win32":
                tunnel.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                tunnel.terminate()
            try:
                tunnel.wait(timeout=5)
            except subprocess.TimeoutExpired:
                tunnel.kill()


if __name__ == "__main__":
    raise SystemExit(main())
