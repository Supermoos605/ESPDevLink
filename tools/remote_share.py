#!/usr/bin/env python3
"""Start an ESPDevLink Cloudflare Quick Tunnel and email its URL with Gmail SMTP.

Credentials are read from environment variables:
  ESPDEVLINK_EMAIL_FROM
  ESPDEVLINK_EMAIL_TO
  ESPDEVLINK_GMAIL_APP_PASSWORD

The app password is never stored in the repository.
"""

import os
import re
import signal
import smtplib
import subprocess
import sys
import time
from email.message import EmailMessage
from pathlib import Path


HOST_URL = os.environ.get("ESPDEVLINK_LOCAL_URL", "http://127.0.0.1:8765")
CLOUDFLARED = os.environ.get("CLOUDFLARED_PATH", "cloudflared")
URL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
TUNNEL_START_TIMEOUT = 30


def send_email(url: str) -> None:
    sender = os.environ["ESPDEVLINK_EMAIL_FROM"]
    recipient = os.environ["ESPDEVLINK_EMAIL_TO"]
    password = os.environ["ESPDEVLINK_GMAIL_APP_PASSWORD"]

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = "ESPDevLink remote connection"
    msg.set_content(
        "ESPDevLink Cloudflare Quick Tunnel is ready.\n\n"
        f"Open this URL from your remote device:\n{url}\n\n"
        "This is a temporary Cloudflare Quick Tunnel URL and will stop "
        "when the ESPDevLink sharing script exits."
    )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)


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
        print("[ESPDevLink] Sending URL by Gmail...")

        try:
            send_email(public_url)
        except KeyError as exc:
            print(f"[ERROR] Missing environment variable: {exc.args[0]}")
            return 1
        except smtplib.SMTPException as exc:
            print(f"[ERROR] Gmail SMTP failed: {exc}")
            return 1

        print("[ESPDevLink] URL emailed successfully.")
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
