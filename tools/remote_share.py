#!/usr/bin/env python3
"""Start an ESPDevLink Cloudflare Quick Tunnel and print its URL."""

import os
import re
import signal
import subprocess
import sys
import time
import urllib.parse
import urllib.request


HOST_URL = os.environ.get("ESPDEVLINK_LOCAL_URL", "http://127.0.0.1:8765")
CLOUDFLARED = os.environ.get("CLOUDFLARED_PATH", "cloudflared")
URL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
TUNNEL_START_TIMEOUT = 30
KEYVAL_BASE_URL = "https://api.keyval.org"
KEYVAL_KEY = os.environ.get("ESPDEVLINK_KEYVAL_KEY", "").strip()


def publish_url(public_url: str) -> bool:
    if len(KEYVAL_KEY) < 10:
        print("[ESPDevLink] KeyVal publishing disabled (ESPDEVLINK_KEYVAL_KEY is missing or too short).")
        return True

    endpoint = (
        f"{KEYVAL_BASE_URL}/set/"
        f"{urllib.parse.quote(KEYVAL_KEY, safe='')}/"
        f"{urllib.parse.quote(public_url, safe='')}"
    )
    try:
        with urllib.request.urlopen(endpoint, timeout=15) as response:
            result = response.read().decode("utf-8", errors="replace").strip()
        print(f"[ESPDevLink] Published Quick Tunnel URL to KeyVal: {result}")
        return True
    except Exception as exc:
        print(f"[ERROR] KeyVal publish failed: {exc}")
        return False


def main() -> int:
    print(f"[ESPDevLink] Starting Cloudflare Quick Tunnel for {HOST_URL}")

    try:
        tunnel = subprocess.Popen(
            [CLOUDFLARED, "tunnel", "--url", HOST_URL],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        print("[ERROR] cloudflared was not found. Install cloudflared or set CLOUDFLARED_PATH.")
        return 1

    public_url = None
    deadline = time.monotonic() + TUNNEL_START_TIMEOUT

    try:
        while time.monotonic() < deadline:
            line = tunnel.stdout.readline()
            if not line:
                if tunnel.poll() is not None:
                    print(f"[ERROR] cloudflared exited with code {tunnel.returncode}.")
                    return 1
                time.sleep(0.1)
                continue

            print("[cloudflared]", line.rstrip())
            match = URL_PATTERN.search(line)
            if match:
                public_url = match.group(0)
                break

        if not public_url:
            print("[ERROR] Timed out waiting for a trycloudflare.com URL.")
            return 1

        print(f"[ESPDevLink] Public URL: {public_url}")
        if not publish_url(public_url):
            return 1
        print("[ESPDevLink] Tunnel is running. Press Ctrl+C to stop.")

        while tunnel.poll() is None:
            time.sleep(1)

        print(f"[ESPDevLink] cloudflared exited with code {tunnel.returncode}.")
        return tunnel.returncode or 0

    except KeyboardInterrupt:
        print("\n[ESPDevLink] Stopping tunnel...")
        return 0
    finally:
        if tunnel.poll() is None:
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
