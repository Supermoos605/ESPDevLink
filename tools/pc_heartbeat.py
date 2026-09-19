"""Send an authenticated PC heartbeat to an ESPLink gateway.

Usage:
    python tools/pc_heartbeat.py http://ESP32-IP 192.168.1.50
    python tools/pc_heartbeat.py http://ESP32-IP 192.168.1.50 "Gaming PC" ESPSERVERACCESS
"""
from __future__ import annotations

import json
import sys
import urllib.request


def request_json(url: str, payload: dict, headers: dict[str, str] | None = None) -> dict:
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def login(gateway: str, access_code: str) -> str:
    result = request_json(
        gateway.rstrip("/") + "/api/pc/login",
        {"code": access_code},
    )
    if not result.get("ok") or not result.get("session_id"):
        raise RuntimeError(f"PC login failed: {result}")
    return str(result["session_id"])


def send(gateway: str, pc_ip: str, name: str = "Gaming PC", access_code: str | None = None) -> None:
    if not access_code:
        raise SystemExit("An ESPLink access code is required as the fourth argument.")
    session = login(gateway, access_code)
    headers = {"X-ESPLink-PC-Session": session}
    url = gateway.rstrip("/") + "/api/pc/heartbeat"
    payload = {
        "name": name,
        "ip": pc_ip,
        "game": "",
        "stream": "Ready",
    }
    result = request_json(url, payload, headers)
    print(result)


if __name__ == "__main__":
    if len(sys.argv) < 5:
        raise SystemExit(
            "Usage: python tools/pc_heartbeat.py GATEWAY_URL PC_IP PC_NAME ACCESS_CODE"
        )
    gateway, pc_ip, name, access_code = sys.argv[1:5]
    send(gateway, pc_ip, name, access_code)
