"""ESPLink Windows host diagnostics launcher.

Run from the repository root with:
    python -m host.run_host
"""
from __future__ import annotations

import json
import os
import sys

from .network.discovery import get_endpoint
from .status import HostStatus
from .streaming import EncoderProfile, StreamConfig, build_manifest, get_capture_info


def diagnostics() -> dict:
    config = StreamConfig()
    encoder = EncoderProfile()
    encoder.validate(config)
    endpoint = get_endpoint()
    return {
        "service": "ESPLink Windows Host",
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "working_directory": os.getcwd(),
        "capture": get_capture_info().__dict__,
        "status": HostStatus().snapshot(),
        "network": endpoint.as_dict(),
        "browser_url": f"http://{endpoint.host}:{endpoint.port}/",
        "manifest": build_manifest(config, encoder),
    }


def main() -> None:
    print("ESPLink Windows Host diagnostics")
    print(json.dumps(diagnostics(), indent=2))
    print()
    print("Diagnostics complete. Start the HTTP host with:")
    print("    python -m host.host_server")


if __name__ == "__main__":
    main()
