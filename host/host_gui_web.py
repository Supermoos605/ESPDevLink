"""Browser-rendered ESPDevLink Windows control center."""
from __future__ import annotations
import importlib.util
import json
import os
import socket
import shutil
import subprocess
import sys
import threading
import urllib.request
import urllib.error
import webbrowser
import atexit
import ctypes
from ctypes import wintypes
from collections import deque
from pathlib import Path

import webview

HOST_URL = "http://127.0.0.1:8765"

# When bundled, the executable is placed in <project>/bin/, while PyInstaller
# resources are unpacked under its temporary bundle directory.
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent.parent
else:
    ROOT = Path(__file__).resolve().parents[1]

BUNDLE_ROOT = Path(__file__).resolve().parents[1]
HTML = Path(__file__).with_name("host_gui_web.html")
ICON = BUNDLE_ROOT / "data" / "espdevlink.ico"


# Keep child processes owned by the Control Center. Windows will terminate
# every process in this job when the Control Center exits.
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JobObjectExtendedLimitInformation = 9


class _JobObject:
    def __init__(self):
        self.handle = None
        if os.name != "nt":
            return
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        self.handle = self._kernel32.CreateJobObjectW(None, None)
        if not self.handle:
            self.handle = None
            return

        class BasicLimit(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]
        class IoCounters(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]
        class ExtendedLimit(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BasicLimit),
                ("IoInfo", IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        info = ExtendedLimit()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        self._kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, wintypes.INT, ctypes.c_void_p, wintypes.DWORD]
        self._kernel32.SetInformationJobObject.restype = wintypes.BOOL
        if not self._kernel32.SetInformationJobObject(
            self.handle, JobObjectExtendedLimitInformation,
            ctypes.byref(info), ctypes.sizeof(info)
        ):
            self._kernel32.CloseHandle(self.handle)
            self.handle = None
            return

        self._kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self._kernel32.AssignProcessToJobObject.restype = wintypes.BOOL

    def add(self, process):
        if not self.handle or process.poll() is not None:
            return
        self._kernel32.AssignProcessToJobObject(self.handle, wintypes.HANDLE(process._handle))

    def close(self):
        if self.handle:
            self._kernel32.CloseHandle(self.handle)
            self.handle = None


class HostControlAPI:
    def __init__(self):
        self.processes = []
        self.output_lines = deque(maxlen=3000)
        self.output_lock = threading.Lock()
        self.host_session = ""
        self.job = _JobObject()

    def _python(self):
        p = ROOT / ".venv" / "Scripts" / "python.exe"
        if p.exists():
            return str(p)

        # A frozen control center must launch the real host with a Python
        # interpreter, not by recursively launching the frozen GUI executable.
        if getattr(sys, "frozen", False):
            for name in ("py.exe", "python.exe"):
                found = shutil.which(name)
                if found:
                    return found
            return "python.exe"

        return sys.executable

    def _append_output(self, text):
        if not text:
            return
        with self.output_lock:
            self.output_lines.extend(str(text).splitlines())

    def _read_process_output(self, process):
        try:
            for line in iter(process.stdout.readline, ""):
                if line:
                    self._append_output(line.rstrip("\r\n"))
        except (OSError, ValueError):
            pass
        finally:
            try:
                process.stdout.close()
            except Exception:
                pass

    def _start(self, args, label):
        try:
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            # The Control Center is the normal Windows entry point, so keep
            # the streaming features enabled unless the user explicitly
            # disabled them in the environment.
            env.setdefault("ESPLINK_INPUT_ENABLED", "1")
            env.setdefault("ESPLINK_AUDIO_ENABLED", "1")
            process = subprocess.Popen(
                args,
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self.processes.append(process)
            self.job.add(process)
            threading.Thread(
                target=self._read_process_output,
                args=(process,),
                daemon=True,
                name=f"espdevlink-output-{label}",
            ).start()
            self._append_output(f"[Control Center] {label} started (PID {process.pid}).")
            return f"{label} started (PID {process.pid})."
        except Exception as exc:
            message = f"[Control Center] {label} failed: {exc}"
            self._append_output(message)
            return message

    def _start_host_stack(self):
        self._append_output("[ESPDevLink] Starting Cloudflare Quick Tunnel...")
        self._append_output("[ESPDevLink] Cloudflare output will appear below.")
        self._append_output("[ESPDevLink] Expected executable: C:\\Cloudflared\\cloudflared.exe")
        self._append_output("")
        self._append_output("[ESPDevLink] Starting host...")
        self._append_output("")
        self._append_output("[ESPDevLink] Starting Windows host...")
        self._append_output("[ESPDevLink] Full host and Cloudflare output follows below.")
        self._append_output("")

        py = self._python()
        tunnel = self._start([py, "-u", "tools/remote_share.py"], "Cloudflare Quick Tunnel")
        host = self._start([py, "-u", "-m", "host.host_server"], "Windows host")
        return tunnel + "\n" + host

    def _run(self, args, label):
        try:
            result = subprocess.run(
                args,
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=120,
            )
            out = (result.stdout + result.stderr).strip()
            message = f"{label}: exit {result.returncode}\n{out[-7000:]}"
            self._append_output(message)
            return message
        except Exception as exc:
            message = f"{label} failed: {exc}"
            self._append_output(message)
            return message

    def action(self, name):
        py = self._python()
        if name == "start":
            return self._start_host_stack()
        if name == "stop":
            stopped = 0
            for process in list(self.processes):
                if process.poll() is None:
                    try:
                        if os.name == "nt":
                            subprocess.run(
                                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                capture_output=True,
                                text=True,
                                timeout=10,
                            )
                        else:
                            process.terminate()
                    except Exception:
                        try:
                            process.terminate()
                        except Exception:
                            pass
                    stopped += 1
            self._append_output(f"[Control Center] Stopped {stopped} tracked process(es).")
            return f"Stopped {stopped} tracked process(es)."
        if name == "heartbeat":
            return self._start([py, "-u", "-m", "host.network.heartbeat"], "Network heartbeat")
        if name == "simulator":
            return self._start([py, "-u", "simulator/esp_link_simulator.py"], "Simulator")
        if name == "tests":
            return self._run([py, "-u", "-m", "pytest"], "Tests")
        if name == "deps":
            return self._run([py, "-u", "-m", "pip", "install", "-r", "host/requirements.txt"], "Dependency install")
        if name == "venv":
            return self._run([sys.executable, "-m", "venv", str(ROOT / ".venv")], "Virtual environment")
        if name == "diagnostics":
            return self._run([py, "-u", "-m", "host.run_host"], "Diagnostics")
        if name == "streamStart":
            return self._post("/api/host/stream/start", "Start stream")
        if name == "streamStop":
            return self._post("/api/host/stream/stop", "Stop stream")
        return f"Unknown action: {name}"

    def _ensure_host_session(self):
        if self.host_session:
            return self.host_session
        secrets_path = ROOT / "include" / "espdevlink_secrets.py"
        if not secrets_path.exists():
            raise RuntimeError(
                "Private include/espdevlink_secrets.py was not found. "
                "Create it from the project example before using host controls."
            )

        spec = importlib.util.spec_from_file_location(
            "_espdevlink_runtime_secrets",
            secrets_path,
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not load private ESPDevLink credentials.")

        secrets = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(secrets)
        authorization_code = str(getattr(secrets, "ACCESS_CODE", "")).strip()
        if not authorization_code:
            raise RuntimeError("ACCESS_CODE is missing from include/espdevlink_secrets.py.")

        payload = json.dumps({"code": authorization_code, "client_id": "host-control-center"}).encode("utf-8")
        request = urllib.request.Request(
            HOST_URL + "/api/auth",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=3) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not result.get("ok") or not result.get("session_id"):
            raise RuntimeError(result.get("error", "Host authorization failed"))
        self.host_session = str(result["session_id"])
        return self.host_session

    def _post(self, path, label):
        try:
            session = self._ensure_host_session()
            request = urllib.request.Request(
                HOST_URL + path,
                data=b"{}",
                headers={
                    "Content-Type": "application/json",
                    "X-ESPLink-Host-Session": session,
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=3) as response:
                result = f"{label}: {response.read().decode('utf-8')}"
            self._append_output(result)
            return result
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                self.host_session = ""
                try:
                    return self._post(path, label)
                except Exception:
                    pass
            result = f"{label} failed: {exc}"
            self._append_output(result)
            return result
        except Exception as exc:
            result = f"{label} failed: {exc}"
            self._append_output(result)
            return result

    def output(self):
        with self.output_lock:
            return "\n".join(self.output_lines)

    def clear_output(self):
        with self.output_lock:
            self.output_lines.clear()
        return "Output cleared."

    def status(self):
        data = {
            "host_online": False,
            "computer": socket.gethostname(),
            "ip": self._local_ip(),
            "mdns": "steamlink.local",
            "mode": os.environ.get("ESPLINK_CONNECTION_MODE", "AUTOMATIC"),
            "stream": {},
        }
        try:
            with urllib.request.urlopen(HOST_URL + "/api/host/status", timeout=1.5) as response:
                host_status = json.loads(response.read().decode("utf-8"))
            data["host_online"] = True
            data["host"] = host_status
            data["stream"] = {
                "state": host_status.get("stream_state"),
                "game": host_status.get("game"),
                "quality": host_status.get("stream_quality"),
                "health": host_status.get("stream_health"),
            }
        except Exception:
            pass
        return data

    @staticmethod
    def _local_ip():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("1.1.1.1", 80))
            ip = sock.getsockname()[0]
            sock.close()
            return ip
        except OSError:
            return "127.0.0.1"

    def open_web(self):
        webbrowser.open(HOST_URL + "/")
        message = "Opened web interface."
        self._append_output("[Control Center] " + message)
        return message

    def open_esp32(self):
        webbrowser.open("http://steamlink.local/")
        message = "Opened ESP32 interface at http://steamlink.local/"
        self._append_output("[Control Center] " + message)
        return message

    def set_mode(self, mode):
        mode = mode.strip().upper()
        if mode not in {"AUTOMATIC", "REMOTE", "FORCE_REMOTE"}:
            return "Invalid connection mode."
        os.environ["ESPLINK_CONNECTION_MODE"] = mode
        self.action("stop")
        return self.action("start") + f" Mode set to {mode}."

    def schedule(self, value):
        import re
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value.strip()):
            return "Invalid time. Use HH:MM."
        bat = ROOT / "host" / "run_esp_link_host.bat"
        result = subprocess.run(
            [
                "schtasks",
                "/Create",
                "/TN",
                "ESPDevLink Host Daily Start",
                "/TR",
                f'"{bat}"',
                "/SC",
                "DAILY",
                "/ST",
                value.strip(),
                "/F",
            ],
            capture_output=True,
            text=True,
        )
        output = (result.stdout + result.stderr).strip()
        self._append_output(output)
        return output

    def cancel_schedule(self):
        result = subprocess.run(
            ["schtasks", "/Delete", "/TN", "ESPDevLink Host Daily Start", "/F"],
            capture_output=True,
            text=True,
        )
        output = (result.stdout + result.stderr).strip()
        self._append_output(output)
        return output

    def show_schedule(self):
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", "ESPDevLink Host Daily Start", "/V", "/FO", "LIST"],
            capture_output=True,
            text=True,
        )
        output = (result.stdout + result.stderr).strip() or "No schedule found."
        self._append_output(output)
        return output


def main():
    api = HostControlAPI()
    atexit.register(api.job.close)
    webview.create_window(
        "ESPDevLink Host Control Center",
        str(HTML),
        width=1200,
        height=800,
        min_size=(900, 650),
        resizable=True,
        js_api=api,
        background_color="#080a0f",
    )
    webview.start(gui="edgechromium", icon=str(ICON))


if __name__ == "__main__":
    main()
