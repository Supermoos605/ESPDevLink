"""Pull the latest ESPDevLink revision and restart the Windows host."""
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
START_BAT = ROOT / "start_server.bat"

def main():
    time.sleep(2)
    print("[ESPDevLink] Pulling latest revision...")
    result = subprocess.run(["git", "pull", "--ff-only"], cwd=ROOT)
    if result.returncode != 0:
        print("[ESPDevLink] git pull failed; host was not restarted.")
        return result.returncode
    print("[ESPDevLink] Update complete. Restarting host...")
    if not START_BAT.is_file():
        print("[ESPDevLink] start_server.bat is missing.")
        return 1
    if os.name == "nt":
        subprocess.Popen(
            ["cmd", "/c", str(START_BAT), "scheduled"],
            cwd=ROOT,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
    else:
        subprocess.Popen([sys.executable, "-m", "host.host_server"], cwd=ROOT)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
