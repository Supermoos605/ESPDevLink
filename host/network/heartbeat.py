"""Windows host heartbeat agent for ESPLink."""
from __future__ import annotations

import csv
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request

from ..config import ALLOW_CONNECTIONS, AUTHORIZATION_CODE, COMPUTER_NAME, ESP32_URL, HEARTBEAT_SECONDS, KNOWN_GAMES
from ..errors import HostError, message


_pc_session = ""


def get_pc_name() -> str:
    return COMPUTER_NAME or socket.gethostname()


def get_local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return ""
    finally:
        sock.close()


def get_running_processes() -> set[str]:
    """Return executable names from Windows Tasklist without third-party packages."""
    try:
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        processes = set()
        for line in result.stdout.splitlines():
            try:
                row = next(csv.reader([line]))
                if row:
                    processes.add(row[0].lower())
            except (StopIteration, IndexError, csv.Error):
                pass
        return processes
    except (OSError, subprocess.SubprocessError):
        return set()


def get_current_game() -> str:
    processes = get_running_processes()
    for executable, name in KNOWN_GAMES.items():
        if executable in processes:
            return name
    return ""


def get_stream_state() -> str:
    return "Ready"


def login_pc() -> str:
    """Obtain the ESP32 session required by the protected PC heartbeat route."""
    payload = json.dumps({"code": AUTHORIZATION_CODE}).encode("utf-8")
    request = urllib.request.Request(
        ESP32_URL + "/api/pc/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=3) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not result.get("ok") or not result.get("session_id"):
        raise RuntimeError(result.get("error", "PC authorization failed"))
    return str(result["session_id"])


def heartbeat() -> str:
    global _pc_session
    if not _pc_session:
        _pc_session = login_pc()

    payload = {
        "name": get_pc_name(),
        "ip": get_local_ip(),
        "game": get_current_game(),
        "stream": get_stream_state(),
        "allow_connections": ALLOW_CONNECTIONS,
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        ESP32_URL + "/api/pc/heartbeat",
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-ESPLink-PC-Session": _pc_session,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        if error.code == 401:
            _pc_session = login_pc()
            return heartbeat()
        raise


def main() -> None:
    print("====================================")
    print("          ESPLink Windows Host")
    print("====================================")
    print(f"PC name: {get_pc_name()}")
    print(f"PC IP:   {get_local_ip()}")
    print(f"ESPLink: {ESP32_URL or 'not configured'}")
    print(f"Accept connections: {'yes' if ALLOW_CONNECTIONS else 'no'}")
    mode = os.environ.get("ESPLINK_CONNECTION_MODE", "AUTOMATIC").upper()
    if mode in {"REMOTE", "FORCE_REMOTE"}:
        print(f"Connection mode: {mode}")
        print("Remote mode: LAN/mDNS heartbeat to the ESP32 is skipped.")
        print("The Quick Tunnel + KeyVal rendezvous handles the remote path.")
        return

    if not ESP32_URL:\n        print("ESP32 address is not configured. Set ESPLINK_ESP32 to the ESP32 LAN address.")\n        return\n\n    print("Starting heartbeat...\n")

    while True:
        try:
            result = heartbeat()
            print(f"[{time.strftime('%H:%M:%S')}] Online - {result}")
        except urllib.error.HTTPError as error:
            if error.code == 503:
                print(f"[{time.strftime('%H:%M:%S')}] {message(HostError.PC_UNAVAILABLE)}")
            else:
                print(f"[{time.strftime('%H:%M:%S')}] ESPLink HTTP error {error.code}")
        except urllib.error.URLError:
            print(f"[{time.strftime('%H:%M:%S')}] {message(HostError.ESP32_OFFLINE)}")
        except Exception as error:
            print(f"[{time.strftime('%H:%M:%S')}] Host error - {error}")
        time.sleep(HEARTBEAT_SECONDS)


if __name__ == "__main__":
    main()
