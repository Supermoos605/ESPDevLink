"""ESPDevLink Windows desktop launcher.

A graphical replacement for the command-line launcher. The existing host,
heartbeat, simulator, dependency, test, and browser operations remain available.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk


REPO_ROOT = Path(__file__).resolve().parents[1]
HOST_URL = "http://127.0.0.1:8765/"
PYTHON = sys.executable
if (REPO_ROOT / ".venv" / "Scripts" / "python.exe").exists():
    PYTHON = str(REPO_ROOT / ".venv" / "Scripts" / "python.exe")


class ESPDevLinkGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ESPDevLink Host")
        self.geometry("900x620")
        self.minsize(780, 540)
        self.configure(bg="#101216")

        self.process: subprocess.Popen[str] | None = None
        self.output_queue: queue.Queue[str] = queue.Queue()

        self._setup_style()
        self._build_ui()
        self.after(100, self._poll_output)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background="#101216", foreground="#e7e9ed")
        style.configure("TFrame", background="#101216")
        style.configure("Card.TFrame", background="#181b21")
        style.configure("TLabel", background="#101216", foreground="#e7e9ed")
        style.configure("Card.TLabel", background="#181b21", foreground="#e7e9ed")
        style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"))
        style.configure("Subtitle.TLabel", foreground="#9aa1ad", font=("Segoe UI", 10))
        style.configure("CardTitle.TLabel", background="#181b21", font=("Segoe UI", 11, "bold"))
        style.configure("Status.TLabel", background="#181b21", font=("Segoe UI", 10))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), padding=(18, 10))
        style.configure("Action.TButton", font=("Segoe UI", 10), padding=(14, 8))
        style.configure("TNotebook", background="#101216", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(16, 8))
        style.map("TButton", background=[("active", "#2b3039")])

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=24)
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root)
        header.pack(fill="x")
        ttk.Label(header, text="ESPDevLink Host", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Windows host control center",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 18))

        status_card = ttk.Frame(root, style="Card.TFrame", padding=18)
        status_card.pack(fill="x", pady=(0, 14))

        left = ttk.Frame(status_card, style="Card.TFrame")
        left.pack(side="left", fill="x", expand=True)
        ttk.Label(left, text="HOST STATUS", style="CardTitle.TLabel").pack(anchor="w")
        self.status_var = tk.StringVar(value="● Stopped")
        self.status_label = ttk.Label(left, textvariable=self.status_var, style="Status.TLabel")
        self.status_label.pack(anchor="w", pady=(8, 0))
        self.detail_var = tk.StringVar(value="Ready to start ESPDevLink.")
        ttk.Label(left, textvariable=self.detail_var, style="Subtitle.TLabel").pack(anchor="w", pady=(3, 0))

        buttons = ttk.Frame(status_card, style="Card.TFrame")
        buttons.pack(side="right")
        self.start_button = ttk.Button(
            buttons, text="▶  Start Host", style="Accent.TButton", command=self.start_host
        )
        self.start_button.pack(side="left", padx=(0, 8))
        self.stop_button = ttk.Button(
            buttons, text="■  Stop", style="Action.TButton", command=self.stop_host, state="disabled"
        )
        self.stop_button.pack(side="left")

        body = ttk.Frame(root)
        body.pack(fill="both", expand=True)

        self._make_card(
            body,
            "HOST OPERATIONS",
            [
                ("Start Host Server", self.start_host),
                ("Start Network Heartbeat", self.start_heartbeat),
                ("Start ESPLink Simulator", self.start_simulator),
                ("Open Local Web Interface", self.open_web),
            ],
            side="left",
        )

        self._make_card(
            body,
            "TOOLS",
            [
                ("Run Diagnostics", self.run_diagnostics),
                ("Run Tests", self.run_tests),
                ("Install Dependencies", self.install_dependencies),
                ("Create Virtual Environment", self.create_venv),
            ],
            side="right",
        )

        log_card = ttk.Frame(root, style="Card.TFrame", padding=14)
        log_card.pack(fill="both", expand=True, pady=(14, 0))
        top = ttk.Frame(log_card, style="Card.TFrame")
        top.pack(fill="x")
        ttk.Label(top, text="ACTIVITY", style="CardTitle.TLabel").pack(side="left")
        ttk.Button(top, text="Clear", command=self.clear_log).pack(side="right")

        self.log = tk.Text(
            log_card,
            height=8,
            bg="#0c0e12",
            fg="#cbd0d8",
            insertbackground="#cbd0d8",
            relief="flat",
            font=("Consolas", 9),
            wrap="word",
        )
        self.log.pack(fill="both", expand=True, pady=(10, 0))
        self.log.insert("end", "ESPDevLink Host GUI ready.\n")
        self.log.configure(state="disabled")

    def _make_card(
        self,
        parent: ttk.Frame,
        title: str,
        actions: list[tuple[str, object]],
        side: str,
    ) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=16)
        card.pack(side=side, fill="both", expand=True, padx=(0, 7) if side == "left" else (7, 0))
        ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w", pady=(0, 10))
        for label, command in actions:
            ttk.Button(card, text=label, command=command, style="Action.TButton").pack(
                fill="x", pady=4
            )

    def _set_status(self, running: bool, detail: str = "") -> None:
        if running:
            self.status_var.set("● Running")
            self.detail_var.set(detail or "ESPDevLink host process is running.")
            self.start_button.configure(state="disabled")
            self.stop_button.configure(state="normal")
        else:
            self.status_var.set("● Stopped")
            self.detail_var.set(detail or "Ready to start ESPDevLink.")
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")

    def _log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _start_process(self, args: list[str], label: str) -> None:
        if self.process and self.process.poll() is None:
            messagebox.showinfo("ESPDevLink", "Another ESPDevLink operation is already running.")
            return

        self._log(f"> {label}")
        try:
            self.process = subprocess.Popen(
                args,
                cwd=REPO_ROOT,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except OSError as exc:
            self._log(f"ERROR: {exc}")
            messagebox.showerror("ESPDevLink", str(exc))
            return

        self._set_status(True, label)

        threading.Thread(target=self._read_process, args=(self.process,), daemon=True).start()

    def _read_process(self, process: subprocess.Popen[str]) -> None:
        if process.stdout:
            for line in process.stdout:
                self.output_queue.put(line)
        code = process.wait()
        self.output_queue.put(f"\n[process exited with code {code}]\n")

    def _poll_output(self) -> None:
        try:
            while True:
                line = self.output_queue.get_nowait()
                self._log(line)
                if self.process and self.process.poll() is not None:
                    self._set_status(False, f"Process exited with code {self.process.returncode}.")
                    self.process = None
        except queue.Empty:
            pass
        self.after(100, self._poll_output)

    def start_host(self) -> None:
        self._start_process([PYTHON, "-m", "host.host_server"], "Starting host server")

    def start_heartbeat(self) -> None:
        self._start_process([PYTHON, "-m", "host.network.heartbeat"], "Starting network heartbeat")

    def start_simulator(self) -> None:
        self._start_process([PYTHON, "simulator/esp_link_simulator.py"], "Starting ESPLink simulator")

    def run_tests(self) -> None:
        self._start_process([PYTHON, "-m", "pytest"], "Running ESPDevLink tests")

    def install_dependencies(self) -> None:
        self._start_process(
            [PYTHON, "-m", "pip", "install", "-r", "requirements.txt"],
            "Installing host dependencies",
        )

    def create_venv(self) -> None:
        if (REPO_ROOT / ".venv" / "Scripts" / "python.exe").exists():
            messagebox.showinfo("ESPDevLink", "The virtual environment already exists.")
            return
        self._start_process([PYTHON, "-m", "venv", ".venv"], "Creating virtual environment")

    def run_diagnostics(self) -> None:
        self._start_process([PYTHON, "-m", "host.run_host"], "Running host diagnostics")

    def open_web(self) -> None:
        import webbrowser
        webbrowser.open(HOST_URL)
        self._log(f"Opened {HOST_URL}")

    def stop_host(self) -> None:
        if not self.process or self.process.poll() is not None:
            self._set_status(False)
            return
        self._log("Stopping current operation...")
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
        self.process = None
        self._set_status(False, "Host operation stopped.")

    def _on_close(self) -> None:
        if self.process and self.process.poll() is None:
            if not messagebox.askyesno("Exit ESPDevLink", "Stop the running process and exit?"):
                return
            self.stop_host()
        self.destroy()


def main() -> None:
    app = ESPDevLinkGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
