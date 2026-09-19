"""ESPDevLink Windows desktop control center.

The GUI is the primary Windows control surface for the ESPDevLink host.
Existing launcher operations remain available while the dashboard adds live
host health, connection, streaming, and activity information.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk

# Make Tk render natively on Windows high-DPI displays instead of letting
# Windows bitmap-scale the entire application (which makes text and shapes fuzzy).
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass
import urllib.error
import urllib.request
import webbrowser
import socket
from pathlib import Path
from tkinter import messagebox, ttk


REPO_ROOT = Path(__file__).resolve().parents[1]
HOST_URL = "http://127.0.0.1:8765/"
HOST_STATUS_URL = HOST_URL + "api/host/status"
HOST_HEALTH_URL = HOST_URL + "api/host/health"

PYTHON = sys.executable
if (REPO_ROOT / ".venv" / "Scripts" / "python.exe").exists():
    PYTHON = str(REPO_ROOT / ".venv" / "Scripts" / "python.exe")

BG = "#080a0f"
SIDEBAR = "#0d1018"
CARD = "#11151f"
CARD_ALT = "#0c1017"
BORDER = "#2a2f3a"
TEXT = "#f5f7fb"
MUTED = "#8995ad"
BLUE = "#6d7cff"
PURPLE = "#9257ff"
GREEN = "#49e39b"
YELLOW = "#f4c84a"
RED = "#ff6475"
FONT = "Inter"


class SteamButton(tk.Canvas):
    """ESPDevLink-style rounded button with matching colors and typography."""

    def __init__(self, parent, text="", command=None, accent=False, **kwargs):
        self._label = text
        self._command = command
        self._accent = accent
        self._disabled = False
        self._hover = False
        width = kwargs.pop("width", max(150, len(text) * 8 + 36))
        height = kwargs.pop("height", 44)
        super().__init__(
            parent,
            width=width,
            height=height,
            bd=0,
            highlightthickness=0,
            relief="flat",
            bg=kwargs.pop("bg", parent.cget("bg")),
            cursor="hand2",
            **kwargs,
        )
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self._draw()

    @staticmethod
    def _mix(a, b, t):
        a = a.lstrip("#")
        b = b.lstrip("#")
        return "#{:02x}{:02x}{:02x}".format(
            int(int(a[0:2], 16) * (1 - t) + int(b[0:2], 16) * t),
            int(int(a[2:4], 16) * (1 - t) + int(b[2:4], 16) * t),
            int(int(a[4:6], 16) * (1 - t) + int(b[4:6], 16) * t),
        )

    def _rounded_rect(self, x1, y1, x2, y2, radius, fill):
        self.create_rectangle(x1 + radius, y1, x2 - radius, y2, fill=fill, outline="")
        self.create_rectangle(x1, y1 + radius, x2, y2 - radius, fill=fill, outline="")
        for box, start in (
            ((x1, y1, x1 + 2 * radius, y1 + 2 * radius), 90),
            ((x2 - 2 * radius, y1, x2, y1 + 2 * radius), 0),
            ((x1, y2 - 2 * radius, x1 + 2 * radius, y2), 180),
            ((x2 - 2 * radius, y2 - 2 * radius, x2, y2), 270),
        ):
            self.create_arc(*box, start=start, extent=90, fill=fill, outline="")

    def _draw(self):
        w = max(40, self.winfo_width())
        h = max(30, self.winfo_height())
        self.delete("all")
        radius = min(14, h // 2 - 1)
        x1, y1, x2, y2 = 1, 1, w - 1, h - 1

        if self._accent and not self._disabled:
            left, right = "#6476ff", "#9257ff"
            if self._hover:
                left, right = "#6d7cff", "#9b5dff"
            # The web client uses a left-to-right indigo/purple gradient.
            # Paint the rounded body first, then the interior gradient.
            self._rounded_rect(x1, y1, x2, y2, radius, left)
            for x in range(x1 + radius, x2 - radius + 1):
                t = (x - (x1 + radius)) / max(1, (x2 - x1) - 2 * radius)
                self.create_line(x, y1 + 1, x, y2 - 1, fill=self._mix(left, right, t))
            # Fill the curved end caps with the matching endpoint colors.
            self.create_arc(x1, y1, x1 + 2 * radius, y2, start=90, extent=180, fill=left, outline=left)
            self.create_arc(x2 - 2 * radius, y1, x2, y2, start=270, extent=180, fill=right, outline=right)
            text_color = "#ffffff"
            font = ("Inter", 10, "bold")
        else:
            fill = "#151922" if not self._disabled else "#10131a"
            if self._hover and not self._disabled:
                fill = "#1b2030"
            self._rounded_rect(x1, y1, x2, y2, radius, fill)
            # Subtle border in the same translucent style as .secondary.
            self.create_arc(x1, y1, x1 + 2 * radius, y2, start=90, extent=180, outline="#252a36")
            self.create_arc(x2 - 2 * radius, y1, x2, y2, start=270, extent=180, outline="#252a36")
            text_color = "#727d91" if self._disabled else "#c8cfdd"
            font = ("Inter", 10, "bold")
        self.create_text(w / 2, h / 2, text=self._label, fill=text_color, font=font)

    def _on_enter(self, _event):
        self._hover = True
        self._draw()

    def _on_leave(self, _event):
        self._hover = False
        self._draw()

    def _on_click(self, _event):
        if not self._disabled and self._command:
            self._command()

    def configure(self, cnf=None, **kwargs):
        state = kwargs.pop("state", None)
        text = kwargs.pop("text", None)
        if text is not None:
            self._label = text
        if state is not None:
            self._disabled = state == "disabled"
            super().configure(cursor="arrow" if self._disabled else "hand2")
        if kwargs or cnf:
            super().configure(cnf or {}, **kwargs)
        self._draw()

    config = configure


class ESPDevLinkGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ESPDevLink Host")
        self.geometry("1120x760")
        self.minsize(940, 650)
        self.configure(bg=BG)

        self.process: subprocess.Popen[str] | None = None
        self.output_queue: queue.Queue[str] = queue.Queue()
        self.nav_buttons: dict[str, tk.Button] = {}
        self.connection_mode = tk.StringVar(value=os.environ.get("ESPLINK_CONNECTION_MODE", "AUTOMATIC").upper())

        self._setup_style()
        self._build_ui()
        self.after(100, self._poll_output)
        self.after(1000, self._refresh_dashboard)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "TProgressbar",
            troughcolor="#07090e",
            background=BLUE,
            bordercolor="#0b1420",
            lightcolor=BLUE,
            darkcolor=BLUE,
        )
        style.configure(
            "Action.TButton",
            font=("Inter", 10),
            padding=(14, 9),
        )
        style.configure(
            "Accent.TButton",
            font=("Inter", 10, "bold"),
            padding=(16, 10),
        )
        style.map("TButton", background=[("active", "#202a43")])

    def _build_ui(self) -> None:
        self._build_header()

        shell = tk.Frame(self, bg=BG)
        shell.pack(fill="both", expand=True)

        self.sidebar = tk.Frame(shell, bg=SIDEBAR, width=210)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self._build_sidebar()

        self.content = tk.Frame(shell, bg=BG)
        self.content.pack(side="left", fill="both", expand=True)

        self.pages: dict[str, tk.Frame] = {}
        self._build_dashboard_page()
        self._build_operations_page()
        self._build_diagnostics_page()
        self._build_connection_page()
        self._build_network_page()
        self._build_scheduler_page()
        self._build_streaming_page()
        self.show_page("Dashboard")

        self._build_footer()

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=BG, height=82)
        header.pack(fill="x")
        header.pack_propagate(False)

        glow = tk.Canvas(header, bg=BG, bd=0, highlightthickness=0)
        glow.place(relx=0, rely=0, relwidth=1, relheight=1)
        for cx, cy, r, alpha_steps in ((0.82, 0.25, 70, 8), (0.94, 0.78, 52, 7)):
            for i in range(alpha_steps, 0, -1):
                rr = r * i / alpha_steps
                glow.create_oval(
                    1120*cx-rr, 82*cy-rr, 1120*cx+rr, 82*cy+rr,
                    fill="#17132a" if i > alpha_steps//2 else "#111329", outline=""
                )

        brand = tk.Frame(header, bg=BG)
        brand.pack(side="left", padx=24, fill="y")
        self.header_logo = tk.Canvas(brand, width=42, height=42, bg=BG, bd=0, highlightthickness=0)
        self.header_logo.pack(side="left", padx=(0, 12))

        # Rounded gradient tile. Keep geometry vector-based so Windows can
        # render it cleanly at the monitor's native DPI.
        self.header_logo.create_rectangle(10, 0, 32, 42, fill="#7a69ff", outline="")
        self.header_logo.create_rectangle(0, 10, 42, 32, fill="#756eff", outline="")
        self.header_logo.create_oval(0, 0, 21, 21, fill="#6d7cff", outline="")
        self.header_logo.create_oval(21, 0, 42, 21, fill="#8660ff", outline="")
        self.header_logo.create_oval(0, 21, 21, 42, fill="#706fff", outline="")
        self.header_logo.create_oval(21, 21, 42, 42, fill="#9257ff", outline="")

        # Four connector strokes and rounded-square center mark from favicon.svg.
        self.header_logo.create_line(21, 6.6, 21, 12.5, fill="white", width=3, capstyle="round")
        self.header_logo.create_line(21, 29.5, 21, 35.4, fill="white", width=3, capstyle="round")
        self.header_logo.create_line(6.6, 21, 12.5, 21, fill="white", width=3, capstyle="round")
        self.header_logo.create_line(29.5, 21, 35.4, 21, fill="white", width=3, capstyle="round")

        x1, y1, x2, y2, r = 12.5, 12.5, 29.5, 29.5, 5.25
        self.header_logo.create_line(x1 + r, y1, x2 - r, y1, fill="white", width=3.2)
        self.header_logo.create_line(x1 + r, y2, x2 - r, y2, fill="white", width=3.2)
        self.header_logo.create_line(x1, y1 + r, x1, y2 - r, fill="white", width=3.2)
        self.header_logo.create_line(x2, y1 + r, x2, y2 - r, fill="white", width=3.2)
        self.header_logo.create_arc(x1, y1, x1 + 2*r, y1 + 2*r, start=90, extent=90, outline="white", width=3.2)
        self.header_logo.create_arc(x2 - 2*r, y1, x2, y1 + 2*r, start=0, extent=90, outline="white", width=3.2)
        self.header_logo.create_arc(x1, y2 - 2*r, x1 + 2*r, y2, start=180, extent=90, outline="white", width=3.2)
        self.header_logo.create_arc(x2 - 2*r, y2 - 2*r, x2, y2, start=270, extent=90, outline="white", width=3.2)
        titles = tk.Frame(brand, bg=BG)
        titles.pack(side="left", pady=13)
        tk.Label(
            titles,
            text="ESPDevLink Host",
            bg=BG,
            fg=TEXT,
            font=("Inter", 18, "bold"),
        ).pack(anchor="w")
        tk.Label(
            titles,
            text="Windows host control center",
            bg=BG,
            fg=MUTED,
            font=("Inter", 9),
        ).pack(anchor="w")

        self.header_status = tk.Label(
            header,
            text="● HOST STOPPED",
            bg=BG,
            fg=RED,
            font=("Inter", 10, "bold"),
        )
        self.header_status.pack(side="right", padx=24)

    def _build_sidebar(self) -> None:
        tk.Label(
            self.sidebar,
            text="CONTROL CENTER",
            bg=SIDEBAR,
            fg=MUTED,
            font=("Inter", 8, "bold"),
        ).pack(anchor="w", padx=20, pady=(24, 10))

        for name, icon in (
            ("Dashboard", "⌂"),
            ("Operations", "⚡"),
            ("Diagnostics", "◉"),
            ("Connection", "⇄"),
            ("Network", "⌁"),
            ("Scheduler", "◷"),
            ("Streaming", "▶"),
        ):
            button = tk.Button(
                self.sidebar,
                text=f"  {icon}   {name}",
                anchor="w",
                bd=0,
                relief="flat",
                bg=SIDEBAR,
                fg=MUTED,
                activebackground="#17365a",
                activeforeground=TEXT,
                font=("Inter", 10),
                padx=12,
                pady=11,
                cursor="hand2",
                command=lambda n=name: self.show_page(n),
            )
            button.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[name] = button

        tk.Frame(self.sidebar, bg=BORDER, height=1).pack(fill="x", padx=18, pady=18)

        tk.Label(
            self.sidebar,
            text="QUICK ACCESS",
            bg=SIDEBAR,
            fg=MUTED,
            font=("Inter", 8, "bold"),
        ).pack(anchor="w", padx=20, pady=(0, 8))

        for label, command in (
            ("Open Web Interface", self.open_web),
            ("Run Tests", self.run_tests),
            ("Create Virtual Environment", self.create_venv),
        ):
            tk.Button(
                self.sidebar,
                text=label,
                anchor="w",
                bd=0,
                bg=SIDEBAR,
                fg=TEXT,
                activebackground="#17365a",
                activeforeground=TEXT,
                font=("Inter", 9),
                padx=20,
                pady=7,
                cursor="hand2",                command=command,
            ).pack(fill="x")

    def _build_dashboard_page(self) -> None:
        page = tk.Frame(self.content, bg=BG)
        self.pages["Dashboard"] = page
        ambient = tk.Canvas(page, bg=BG, bd=0, highlightthickness=0)
        ambient.place(relx=0, rely=0, relwidth=1, relheight=1)
        for cx, cy, r in ((0.92, 0.10, 95), (0.70, 0.92, 70)):
            for i in range(7, 0, -1):
                rr = r * i / 7
                ambient.create_oval(
                    1120*cx-rr, 760*cy-rr, 1120*cx+rr, 760*cy+rr,
                    fill="#11122a" if i > 3 else "#17102d", outline=""
                )

        title = tk.Frame(page, bg=BG)
        title.pack(fill="x", padx=26, pady=(24, 16))
        tk.Label(
            title,
            text="Dashboard",
            bg=BG,
            fg=TEXT,
            font=("Inter", 22, "bold"),
        ).pack(side="left")
        tk.Label(
            title,
            text="Live ESPDevLink host overview",
            bg=BG,
            fg=MUTED,
            font=("Inter", 10),
        ).pack(side="left", padx=14, pady=(8, 0))

        self.host_card = self._status_card(page, "HOST SERVER", "Stopped", RED)
        self.esp_card = self._status_card(page, "ESP32", "Not connected", MUTED)
        self.webrtc_card = self._status_card(page, "WEBRTC", "Waiting", MUTED)
        self.stream_card = self._status_card(page, "STREAMING", "Stopped", MUTED)

        cards = tk.Frame(page, bg=BG)
        cards.pack(fill="x", padx=20)
        for card in (self.host_card, self.esp_card, self.webrtc_card, self.stream_card):
            card.pack(in_=cards, side="left", fill="both", expand=True, padx=6)

        middle = tk.Frame(page, bg=BG)
        middle.pack(fill="both", expand=True, padx=20, pady=12)

        left = self._panel(middle, "CONNECTION & HOST")
        left.pack(side="left", fill="both", expand=True, padx=(6, 6))
        self.connection_vars = {}
        for key, label in (
            ("mode", "Connection Mode"),
            ("computer", "Computer"),
            ("ip", "Host IP"),
            ("mdns", "mDNS"),
            ("game", "Game"),
            ("uptime", "Host Uptime"),
        ):
            self.connection_vars[key] = self._info_row(left, label, "—")

        right = self._panel(middle, "STREAM HEALTH")
        right.pack(side="left", fill="both", expand=True, padx=(6, 6))
        self.stream_vars = {}
        for key, label in (
            ("state", "State"),
            ("quality", "Quality"),
            ("fps", "FPS"),
            ("resolution", "Resolution"),
            ("bitrate", "Bitrate"),
            ("health", "Health"),
        ):
            self.stream_vars[key] = self._info_row(right, label, "—")

        actions = tk.Frame(page, bg=BG)
        actions.pack(fill="x", padx=26, pady=(0, 12))
        self.dashboard_start = self._steam_button(
            actions, text="▶  START HOST", style="Accent.TButton", command=self.start_host
        )
        self.dashboard_start.pack(side="left", padx=(0, 8))
        self.dashboard_stop = self._steam_button(
            actions, text="■  STOP HOST", style="Action.TButton", command=self.stop_host
        )
        self.dashboard_stop.pack(side="left", padx=8)
        self._steam_button(
            actions, text="↗  OPEN WEB INTERFACE", style="Action.TButton", command=self.open_web
        ).pack(side="left", padx=8)
        self.last_update = tk.Label(
            actions, text="Waiting for host...", bg=BG, fg=MUTED, font=("Inter", 9)
        )
        self.last_update.pack(side="right")

    def _build_operations_page(self) -> None:
        page = tk.Frame(self.content, bg=BG)
        self.pages["Operations"] = page

        tk.Label(
            page, text="Operations", bg=BG, fg=TEXT, font=("Inter", 22, "bold")
        ).pack(anchor="w", padx=26, pady=(24, 4))
        tk.Label(
            page,
            text="Everything from the original ESPDevLink launcher, now in one place.",
            bg=BG,
            fg=MUTED,
            font=("Inter", 10),
        ).pack(anchor="w", padx=26, pady=(0, 18))

        columns = tk.Frame(page, bg=BG)
        columns.pack(fill="x", padx=20)

        host_panel = self._panel(columns, "HOST CONTROL")
        host_panel.pack(side="left", fill="both", expand=True, padx=6)
        for text, command in (
            ("▶  Start Host Server", self.start_host),
            ("■  Stop Current Process", self.stop_host),
            ("♥  Start Network Heartbeat", self.start_heartbeat),
            ("▣  Start ESPLink Simulator", self.start_simulator),
            ("↗  Open Local Web Interface", self.open_web),
        ):
            self._steam_button(host_panel, text=text, command=command, style="Action.TButton").pack(
                fill="x", pady=5
            )

        tools_panel = self._panel(columns, "TOOLS")
        tools_panel.pack(side="left", fill="both", expand=True, padx=6)
        for text, command in (
            ("◉  Run Diagnostics", self.run_diagnostics),
            ("✓  Run Tests", self.run_tests),
            ("↓  Install Host Dependencies", self.install_dependencies),
            ("🐍  Create Virtual Environment", self.create_venv),
        ):
            self._steam_button(tools_panel, text=text, command=command, style="Action.TButton").pack(
                fill="x", pady=5
            )

        log_panel = self._panel(page, "ACTIVITY")
        log_panel.pack(fill="both", expand=True, padx=26, pady=18)
        self._build_log(log_panel)

    def _build_diagnostics_page(self) -> None:
        page = tk.Frame(self.content, bg=BG)
        self.pages["Diagnostics"] = page

        tk.Label(
            page, text="Diagnostics", bg=BG, fg=TEXT, font=("Inter", 22, "bold")
        ).pack(anchor="w", padx=26, pady=(24, 4))
        tk.Label(
            page,
            text="Live checks are read from the local host API when the server is running.",
            bg=BG,
            fg=MUTED,
            font=("Inter", 10),
        ).pack(anchor="w", padx=26, pady=(0, 16))

        panel = self._panel(page, "HEALTH CHECKS")
        panel.pack(fill="x", padx=26)

        self.diagnostic_vars: dict[str, tk.StringVar] = {}
        for key, label in (
            ("host", "Host Server"),
            ("stream", "Stream"),
            ("game", "Game"),
            ("quality", "Stream Quality"),
            ("health", "Stream Health"),
        ):
            row = tk.Frame(panel, bg=CARD)
            row.pack(fill="x", pady=5)
            tk.Label(row, text=label, bg=CARD, fg=TEXT, font=("Inter", 10)).pack(side="left")
            var = tk.StringVar(value="Waiting...")
            self.diagnostic_vars[key] = var
            tk.Label(
                row, textvariable=var, bg=CARD, fg=MUTED, font=("Inter", 10, "bold")
            ).pack(side="right")

        self._steam_button(
            page,
            text="◉  RUN FULL DIAGNOSTICS",
            style="Accent.TButton",
            command=self.run_diagnostics,
        ).pack(anchor="w", padx=26, pady=16)

        log_panel = self._panel(page, "DIAGNOSTIC OUTPUT")
        log_panel.pack(fill="both", expand=True, padx=26, pady=(0, 20))
        self.diag_text = tk.Text(
            log_panel,
            height=12,
            bg="#08111b",
            fg="#b9c9da",
            insertbackground=TEXT,
            relief="flat",
            font=("Consolas", 9),            wrap="word",
        )
        self.diag_text.pack(fill="both", expand=True)
        self.diag_text.insert("end", "Live health results will appear here.\n")
        self.diag_text.configure(state="disabled")

    def _build_connection_page(self) -> None:
        page = tk.Frame(self.content, bg=BG)
        self.pages["Connection"] = page

        tk.Label(
            page, text="Connection", bg=BG, fg=TEXT, font=("Inter", 22, "bold")
        ).pack(anchor="w", padx=26, pady=(24, 4))
        tk.Label(
            page,
            text="Choose how the browser client should route its next connection.",
            bg=BG,
            fg=MUTED,
            font=("Inter", 10),
        ).pack(anchor="w", padx=26, pady=(0, 18))

        panel = self._panel(page, "CONNECTION MODE")
        panel.pack(fill="x", padx=26)

        tk.Label(
            panel,
            text="The selected mode is passed to the web interface as a connection-mode parameter.\n"
                 "Changing the host process mode affects its heartbeat display; it does not change ESP32 firmware settings.",
            bg=CARD, fg=MUTED, justify="left", font=("Inter", 9),
        ).pack(anchor="w", padx=16, pady=(0, 14))

        modes = (
            ("AUTOMATIC", "Try the normal connection routing."),
            ("REMOTE", "Request the remote Quick Tunnel route."),
            ("FORCE_REMOTE", "Always request the remote route for testing."),
        )
        for mode, description in modes:
            row = tk.Frame(panel, bg=CARD)
            row.pack(fill="x", padx=12, pady=4)
            tk.Radiobutton(
                row, text=mode, variable=self.connection_mode, value=mode,
                bg=CARD, fg=TEXT, activebackground=CARD, activeforeground=TEXT,
                selectcolor=SIDEBAR, font=("Inter", 10, "bold"),
            ).pack(side="left")
            tk.Label(row, text=description, bg=CARD, fg=MUTED, font=("Inter", 9)).pack(
                side="left", padx=12
            )

        actions = tk.Frame(panel, bg=CARD)
        actions.pack(fill="x", padx=12, pady=(14, 12))
        self._steam_button(actions, text="Open Selected Mode", style="Accent.TButton", command=self.open_selected_mode).pack(side="left")
        self._steam_button(actions, text="Restart Host With Mode", style="Action.TButton", command=self.restart_host_with_mode).pack(side="left", padx=8)

        status = self._panel(page, "CURRENT HOST SETTING")
        status.pack(fill="x", padx=26, pady=18)
        self.connection_mode_status = tk.StringVar(value="AUTOMATIC")
        tk.Label(status, textvariable=self.connection_mode_status, bg=CARD, fg=TEXT,
                 font=("Inter", 15, "bold")).pack(anchor="w", padx=16, pady=(2, 4))
        tk.Label(status, text="This is the mode that will be inherited by newly started host processes.",
                 bg=CARD, fg=MUTED, font=("Inter", 9)).pack(anchor="w", padx=16, pady=(0, 14))
        self._sync_connection_mode_status()

    def _build_network_page(self) -> None:
        page = tk.Frame(self.content, bg=BG)
        self.pages["Network"] = page

        tk.Label(page, text="Network", bg=BG, fg=TEXT,
                 font=("Inter", 22, "bold")).pack(anchor="w", padx=26, pady=(24, 4))
        tk.Label(page, text="Windows host and ESP32 network information.",
                 bg=BG, fg=MUTED, font=("Inter", 10)).pack(anchor="w", padx=26, pady=(0, 18))

        panel = self._panel(page, "HOST NETWORK")
        panel.pack(fill="x", padx=26)
        self.network_vars = {}
        for key, label in (("hostname", "Computer Name"), ("ip", "LAN IP"), ("mdns", "mDNS"),
                           ("esp32", "ESP32 Target"), ("mode", "Connection Mode")):
            self.network_vars[key] = self._info_row(panel, label, "—")

        actions = tk.Frame(panel, bg=CARD)
        actions.pack(fill="x", padx=14, pady=(12, 14))
        self._steam_button(actions, text="↻  REFRESH NETWORK", command=self.refresh_network_page).pack(side="left")
        self._steam_button(actions, text="↗  OPEN ESP32 INTERFACE", command=self.open_esp32).pack(side="left", padx=8)

        note = self._panel(page, "NETWORK NOTES")
        note.pack(fill="x", padx=26, pady=18)
        tk.Label(note,
                 text="The ESP32 manages its own Wi-Fi connection. This page shows the Windows host's view of the network and the configured ESP32 target; Wi-Fi credentials remain in the ESP32 configuration.",
                 bg=CARD, fg=MUTED, justify="left", wraplength=850,
                 font=("Inter", 9)).pack(anchor="w", padx=16, pady=(2, 14))
        self.refresh_network_page()

    def _build_scheduler_page(self) -> None:
        page = tk.Frame(self.content, bg=BG)
        self.pages["Scheduler"] = page

        tk.Label(page, text="Scheduler", bg=BG, fg=TEXT,
                 font=("Inter", 22, "bold")).pack(anchor="w", padx=26, pady=(24, 4))
        tk.Label(page, text="Manage the existing Windows daily ESPDevLink host task.",
                 bg=BG, fg=MUTED, font=("Inter", 10)).pack(anchor="w", padx=26, pady=(0, 18))

        panel = self._panel(page, "DAILY START")
        panel.pack(fill="x", padx=26)
        row = tk.Frame(panel, bg=CARD)
        row.pack(fill="x", padx=14, pady=8)
        tk.Label(row, text="Start time (24-hour HH:MM)", bg=CARD, fg=MUTED,
                 font=("Inter", 9)).pack(side="left")
        self.schedule_time = tk.StringVar(value="08:00")
        ttk.Entry(row, textvariable=self.schedule_time, width=10).pack(side="left", padx=12)

        actions = tk.Frame(panel, bg=CARD)
        actions.pack(fill="x", padx=14, pady=(8, 14))
        self._steam_button(actions, text="◷  SCHEDULE DAILY START", style="Accent.TButton",
                   command=self.schedule_host).pack(side="left")
        self._steam_button(actions, text="■  CANCEL SCHEDULE", command=self.cancel_schedule).pack(side="left", padx=8)
        self._steam_button(actions, text="◉  SHOW SCHEDULE", command=self.show_schedule).pack(side="left")

        self.schedule_output = tk.Text(panel, height=8, bg="#08111b", fg="#b9c9da",
                                       relief="flat", font=("Consolas", 9), wrap="word")
        self.schedule_output.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.schedule_output.insert("end", "No schedule query run yet.\n")
        self.schedule_output.configure(state="disabled")

    def _build_streaming_page(self) -> None:
        page = tk.Frame(self.content, bg=BG)
        self.pages["Streaming"] = page

        tk.Label(page, text="Streaming", bg=BG, fg=TEXT,
                 font=("Inter", 22, "bold")).pack(anchor="w", padx=26, pady=(24, 4))
        tk.Label(page, text="Monitor the active WebRTC stream and control its lifecycle.",
                 bg=BG, fg=MUTED, font=("Inter", 10)).pack(anchor="w", padx=26, pady=(0, 18))

        panel = self._panel(page, "STREAM CONTROL")
        panel.pack(fill="x", padx=26)
        self.stream_control_vars = {}
        for key, label in (("state", "State"), ("game", "Game"), ("quality", "Quality"),
                           ("fps", "FPS"), ("resolution", "Resolution"), ("bitrate", "Bitrate"),
                           ("health", "Health")):
            self.stream_control_vars[key] = self._info_row(panel, label, "—")
        actions = tk.Frame(panel, bg=CARD)
        actions.pack(fill="x", padx=14, pady=(12, 14))
        self._steam_button(actions, text="▶  START STREAM", style="Accent.TButton",
                   command=self.start_stream).pack(side="left")
        self._steam_button(actions, text="■  STOP STREAM", command=self.stop_stream).pack(side="left", padx=8)
        self._steam_button(actions, text="↻  REFRESH", command=self.refresh_stream_page).pack(side="left")

        panel2 = self._panel(page, "WEBRTC")
        panel2.pack(fill="x", padx=26, pady=18)
        self.webrtc_vars = {}
        for key, label in (("peer", "Peer"), ("connection", "Connection"), ("ice", "ICE"),
                           ("audio", "Audio"), ("input", "Input")):
            self.webrtc_vars[key] = self._info_row(panel2, label, "—")
        self.refresh_stream_page()

    def _steam_button(self, parent, text, command, style="", **kwargs):
        accent = style == "Accent.TButton" or kwargs.pop("accent", False)
        return SteamButton(parent, text=text, command=command, accent=accent, **kwargs)

    def _build_footer(self) -> None:
        footer = tk.Frame(self, bg="#080a0f", height=30)
        footer.pack(fill="x")
        footer.pack_propagate(False)
        self.footer_status = tk.Label(
            footer, text="●  Ready", bg=BG, fg=GREEN, font=("Inter", 8)
        )
        self.footer_status.pack(side="left", padx=18)
        tk.Label(
            footer,
            text="ESPDevLink Host Control Center",
            bg=BG,
            fg=MUTED,
            font=("Inter", 8),
        ).pack(side="right", padx=18)

    def _panel(self, parent: tk.Widget, title: str) -> tk.Frame:
        panel = tk.Frame(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        tk.Label(
            panel,
            text=title,
            bg=CARD,
            fg=MUTED,
            font=("Inter", 8, "bold"),
        ).pack(anchor="w", padx=16, pady=(13, 9))
        return panel

    def _status_card(self, parent: tk.Widget, title: str, value: str, color: str) -> tk.Frame:
        card = tk.Frame(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1, height=96)
        card.pack_propagate(False)
        tk.Label(
            card, text=title, bg=CARD, fg=MUTED, font=("Inter", 8, "bold")
        ).pack(anchor="w", padx=14, pady=(13, 5))
        var = tk.StringVar(value=f"●  {value}")
        label = tk.Label(
            card, textvariable=var, bg=CARD, fg=color, font=("Inter", 11, "bold")
        )
        label.pack(anchor="w", padx=14)
        card.status_var = var  # type: ignore[attr-defined]
        card.status_label = label  # type: ignore[attr-defined]
        return card

    def _info_row(self, parent: tk.Frame, label: str, value: str) -> tk.StringVar:
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x", padx=14, pady=5)
        tk.Label(row, text=label, bg=CARD, fg=MUTED, font=("Inter", 9)).pack(side="left")
        var = tk.StringVar(value=value)
        tk.Label(row, textvariable=var, bg=CARD, fg=TEXT, font=("Inter", 9, "bold")).pack(
            side="right"
        )
        return var

    def _build_log(self, parent: tk.Frame) -> None:
        top = tk.Frame(parent, bg=CARD)
        top.pack(fill="x", padx=14, pady=(0, 6))
        self._steam_button(top, text="Clear", command=self.clear_log).pack(side="right")
        self.log = tk.Text(
            parent,
            height=10,
            bg="#08111b",
            fg="#b9c9da",
            insertbackground=TEXT,
            relief="flat",
            font=("Consolas", 9),
            wrap="word",
        )
        self.log.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.log.insert("end", "ESPDevLink Host Control Center ready.\n")
        self.log.configure(state="disabled")

    def show_page(self, name: str) -> None:
        for page in self.pages.values():
            page.pack_forget()
        self.pages[name].pack(fill="both", expand=True)
        for button_name, button in self.nav_buttons.items():
            button.configure(
                bg="#1a1f35" if button_name == name else SIDEBAR,
                fg=TEXT if button_name == name else MUTED,
            )

    def _set_status_card(self, card: tk.Frame, value: str, color: str) -> None:
        card.status_var.set(f"●  {value}")  # type: ignore[attr-defined]
        card.status_label.configure(fg=color)  # type: ignore[attr-defined]

    def _set_diagnostic(self, key: str, value: str, color: str = MUTED) -> None:
        var = self.diagnostic_vars.get(key)
        if var:
            var.set(value)

    def _refresh_dashboard(self) -> None:
        def worker() -> None:
            try:
                with urllib.request.urlopen(HOST_STATUS_URL, timeout=1.5) as response:
                    status = json.loads(response.read().decode("utf-8"))
                try:
                    with urllib.request.urlopen(HOST_HEALTH_URL, timeout=1.5) as response:
                        health = json.loads(response.read().decode("utf-8"))
                except (urllib.error.URLError, TimeoutError, OSError, ValueError):
                    health = {}
                self.after(0, lambda: self._apply_dashboard_status(status, health))
            except (urllib.error.URLError, TimeoutError, OSError, ValueError):
                self.after(0, self._apply_dashboard_offline)

        threading.Thread(target=worker, daemon=True).start()
        self.after(2000, self._refresh_dashboard)

    def _apply_dashboard_offline(self) -> None:
        self._set_status_card(self.host_card, "Stopped / Offline", RED)
        self._set_status_card(self.esp_card, "Not connected", MUTED)
        self._set_status_card(self.webrtc_card, "Waiting", MUTED)
        self._set_status_card(self.stream_card, "Stopped", MUTED)
        self.header_status.configure(text="● HOST STOPPED", fg=RED)
        self.footer_status.configure(text="●  Host server offline", fg=RED)
        self.dashboard_start.configure(state="normal")
        self.dashboard_stop.configure(state="disabled")
        self.last_update.configure(text="Host API unavailable")
        for var in self.connection_vars.values():
            var.set("—")
        for var in self.stream_vars.values():
            var.set("—")
        for key in self.diagnostic_vars:
            self.diagnostic_vars[key].set("Offline")

    def _apply_dashboard_status(self, status: dict, health: dict) -> None:
        host = status.get("host", {})
        network = status.get("network", {})
        stream = status.get("stream", {})
        runtime = stream.get("runtime", {}) if isinstance(stream, dict) else {}
        quality = runtime.get("quality", {}) if isinstance(runtime, dict) else {}
        stream_health = runtime.get("health", {}) if isinstance(runtime, dict) else {}

        host_online = bool(host.get("online"))
        stream_state = str(host.get("stream") or stream.get("state") or "stopped")
        network_host = str(network.get("host") or "—")
        mdns = str(network.get("mdns_name") or "—")
        mode = str(os.environ.get("ESPLINK_CONNECTION_MODE", "AUTOMATIC")).upper()
        if mode not in {"AUTOMATIC", "REMOTE", "FORCE_REMOTE"}:
            mode = "AUTOMATIC"
        self.connection_mode.set(mode)
        self._sync_connection_mode_status()

        self._set_status_card(self.host_card, "Running" if host_online else "Offline", GREEN if host_online else RED)
        self._set_status_card(self.esp_card, "Connected" if network_host not in {"—", ""} else "Unknown", GREEN if network_host not in {"—", ""} else MUTED)
        self._set_status_card(self.webrtc_card, "Available" if stream_state not in {"stopped", "idle"} else "Waiting", GREEN if stream_state not in {"stopped", "idle"} else MUTED)
        self._set_status_card(self.stream_card, stream_state.title(), GREEN if stream_state not in {"stopped", "idle"} else MUTED)

        self.header_status.configure(
            text="● HOST RUNNING" if host_online else "● HOST OFFLINE",
            fg=GREEN if host_online else RED,
        )
        self.footer_status.configure(
            text="●  Host API connected" if host_online else "●  Host API responding",
            fg=GREEN if host_online else YELLOW,
        )
        self.dashboard_start.configure(state="disabled" if self.process and self.process.poll() is None else "normal")
        self.dashboard_stop.configure(state="normal" if self.process and self.process.poll() is None else "disabled")
        self.last_update.configure(text="Updated just now")

        values = {
            "mode": mode,
            "computer": str(host.get("name") or "—"),
            "ip": network_host,
            "mdns": mdns,
            "game": str(host.get("game") or "Desktop"),
            "uptime": self._format_seconds(health.get("uptime_seconds")),
        }
        for key, value in values.items():
            self.connection_vars[key].set(value)

        fps = quality.get("fps", quality.get("frame_rate", "—"))
        resolution = quality.get("resolution", "—")
        bitrate = quality.get("bitrate", "—")
        health_value = "OK" if stream_health else "—"
        stream_values = {
            "state": stream_state.title(),
            "quality": str(quality.get("preset") or quality.get("profile") or "Auto"),
            "fps": str(fps),
            "resolution": str(resolution),
            "bitrate": str(bitrate),
            "health": health_value,
        }
        for key, value in stream_values.items():
            self.stream_vars[key].set(value)

        self._set_diagnostic("host", "Online" if host_online else "Offline")
        self._set_diagnostic("stream", stream_state.title())
        self._set_diagnostic("game", str(host.get("game") or "Desktop"))
        self._set_diagnostic("quality", json.dumps(quality, separators=(",", ":")) if quality else "No runtime data")
        self._set_diagnostic("health", json.dumps(stream_health, separators=(",", ":")) if stream_health else "No runtime data")

    @staticmethod
    def _format_seconds(value: object) -> str:
        try:
            seconds = max(0, int(value or 0))
        except (TypeError, ValueError):
            return "—"
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}h {minutes}m"
        if minutes:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"

    def _log(self, text: str) -> None:
        if not hasattr(self, "log"):
            return
        self.log.configure(state="normal")
        self.log.insert("end", text.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def clear_log(self) -> None:
        if not hasattr(self, "log"):
            return
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

        self.footer_status.configure(text=f"●  {label}", fg=YELLOW)
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
                    self.footer_status.configure(text=f"●  Process exited ({self.process.returncode})", fg=YELLOW)
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
        self.show_page("Diagnostics")
        self._start_process([PYTHON, "-m", "host.run_host"], "Running host diagnostics")

    def open_web(self) -> None:
        webbrowser.open(HOST_URL)
        self._log(f"Opened {HOST_URL}")

    def stop_host(self) -> None:
        if not self.process or self.process.poll() is not None:
            self.dashboard_stop.configure(state="disabled")
            return
        self._log("Stopping current operation...")
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
        self.process = None
        self.footer_status.configure(text="●  Host operation stopped", fg=MUTED)

    def _sync_connection_mode_status(self) -> None:
        mode = self.connection_mode.get().upper()
        self.connection_mode_status.set(mode)

    def open_selected_mode(self) -> None:
        mode = self.connection_mode.get().upper()
        if mode not in {"AUTOMATIC", "REMOTE", "FORCE_REMOTE"}:
            mode = "AUTOMATIC"
        self.connection_mode.set(mode)
        self._sync_connection_mode_status()
        url = HOST_URL
        if mode != "AUTOMATIC":
            url += "?mode=" + mode
        webbrowser.open(url)
        self._log(f"Opened web interface with mode: {mode}")

    def restart_host_with_mode(self) -> None:
        mode = self.connection_mode.get().upper()
        if mode not in {"AUTOMATIC", "REMOTE", "FORCE_REMOTE"}:
            mode = "AUTOMATIC"
            self.connection_mode.set(mode)
        if self.process and self.process.poll() is None:
            self.stop_host()
        env = os.environ.copy()
        env["ESPLINK_CONNECTION_MODE"] = mode
        self._log(f"Starting host with connection mode: {mode}")
        try:
            self.process = subprocess.Popen(
                [PYTHON, "-m", "host.host_server"],
                cwd=REPO_ROOT,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            threading.Thread(target=self._read_process, args=(self.process,), daemon=True).start()
            self.footer_status.configure(text=f"●  Host mode: {mode}", fg=YELLOW)
        except OSError as exc:
            self._log(f"ERROR: {exc}")
            messagebox.showerror("ESPDevLink", str(exc))

    def refresh_network_page(self) -> None:
        hostname = socket.gethostname()
        addresses = []
        try:
            for info in socket.getaddrinfo(hostname, None, family=socket.AF_INET):
                address = info[4][0]
                if address not in addresses and not address.startswith("127."):
                    addresses.append(address)
        except OSError:
            pass
        ip = ", ".join(addresses) if addresses else "—"
        try:
            from .config import ESP32_URL
            esp32_url = ESP32_URL
        except ImportError:
            esp32_url = ""
        mode = self.connection_mode.get().upper()
        self.network_vars["hostname"].set(hostname)
        self.network_vars["ip"].set(ip)
        self.network_vars["mdns"].set(f"{hostname}.local")
        self.network_vars["esp32"].set(esp32_url)
        self.network_vars["mode"].set(mode)

    def open_esp32(self) -> None:
        try:
            from .config import ESP32_URL
            url = ESP32_URL
        except ImportError:
            url = ""
        webbrowser.open(url)
        self._log(f"Opened ESP32 interface: {url}")

    def _write_schedule_output(self, text: str) -> None:
        self.schedule_output.configure(state="normal")
        self.schedule_output.delete("1.0", "end")
        self.schedule_output.insert("end", text)
        self.schedule_output.configure(state="disabled")

    def schedule_host(self) -> None:
        import re
        value = self.schedule_time.get().strip()
        if not re.fullmatch(r"(?:[01]\\d|2[0-3]):[0-5]\\d", value):
            messagebox.showerror("ESPDevLink Scheduler", "Use 24-hour HH:MM format, for example 08:30.")
            return
        task_name = "ESPDevLink Host Daily Start"
        command = str(REPO_ROOT / "host" / "run_esp_link_host.bat")
        result = subprocess.run(
            ["schtasks", "/Create", "/TN", task_name, "/TR", f'cmd /c ""{command}""',
             "/SC", "DAILY", "/ST", value, "/F"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        self._write_schedule_output((result.stdout or "") + (result.stderr or ""))
        if result.returncode == 0:
            self._log(f"Scheduled daily host start at {value}.")
        else:
            self._log(f"Schedule failed with code {result.returncode}.")

    def cancel_schedule(self) -> None:
        task_name = "ESPDevLink Host Daily Start"
        result = subprocess.run(
            ["schtasks", "/Delete", "/TN", task_name, "/F"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        self._write_schedule_output((result.stdout or "") + (result.stderr or ""))
        self._log("Daily host schedule cancelled." if result.returncode == 0 else f"Cancel schedule returned {result.returncode}.")

    def show_schedule(self) -> None:
        task_name = "ESPDevLink Host Daily Start"
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", task_name, "/FO", "LIST", "/V"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        output = (result.stdout or "") + (result.stderr or "")
        self._write_schedule_output(output if output.strip() else "No schedule found.")
        self._log("Displayed current schedule.")

    def _on_close(self) -> None:
        if self.process and self.process.poll() is None:
            if not messagebox.askyesno("Exit ESPDevLink", "Stop the running process and exit?"):
                return
            self.stop_host()
        self.destroy()

    def _host_request_json(self, path: str, method: str = "GET") -> dict:
        request = urllib.request.Request(HOST_URL.rstrip("/") + path, method=method)
        with urllib.request.urlopen(request, timeout=2) as response:
            return json.loads(response.read().decode("utf-8"))

    def refresh_stream_page(self) -> None:
        try:
            status = self._host_request_json("/api/host/status")
            health = self._host_request_json("/api/host/health")
            host = status.get("host", {})
            stream = status.get("stream", {})
            runtime = stream.get("runtime", {}) if isinstance(stream, dict) else {}
            quality = runtime.get("quality", {}) if isinstance(runtime, dict) else {}
            health_data = runtime.get("health", {}) if isinstance(runtime, dict) else {}
            state = str(host.get("stream") or stream.get("state") or "stopped")
            values = {
                "state": state.title(),
                "game": str(host.get("game") or "Desktop"),
                "quality": str(quality.get("preset") or quality.get("profile") or "Auto"),
                "fps": str(quality.get("fps", quality.get("frame_rate", "—"))),
                "resolution": str(quality.get("resolution", "—")),
                "bitrate": str(quality.get("bitrate", "—")),
                "health": "OK" if health_data else "No runtime data",
            }
            for key, value in values.items():
                self.stream_control_vars[key].set(value)
            self.webrtc_vars["peer"].set(str(status.get("webrtc", {}).get("peer_id", "—")) if isinstance(status.get("webrtc"), dict) else "—")
            self.webrtc_vars["connection"].set(str(status.get("webrtc", {}).get("connection_state", "—")) if isinstance(status.get("webrtc"), dict) else "—")
            self.webrtc_vars["ice"].set(str(status.get("webrtc", {}).get("ice_state", "—")) if isinstance(status.get("webrtc"), dict) else "—")
            self.webrtc_vars["audio"].set("Enabled" if status.get("audio", {}).get("enabled") else "—" if not isinstance(status.get("audio"), dict) else str(status.get("audio", {}).get("error") or "Disabled"))
            self.webrtc_vars["input"].set("Enabled" if status.get("input", {}).get("enabled") else "Disabled")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, AttributeError) as exc:
            for var in self.stream_control_vars.values():
                var.set("Offline")
            for var in self.webrtc_vars.values():
                var.set("Unavailable")
            self._log(f"Streaming monitor unavailable: {exc}")

    def _post_host_control(self, path: str, label: str) -> None:
        def worker() -> None:
            try:
                request = urllib.request.Request(
                    HOST_URL.rstrip("/") + path,
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=3) as response:
                    result = json.loads(response.read().decode("utf-8"))
                self.after(0, lambda: self._log(f"{label}: {json.dumps(result)}"))
                self.after(0, self.refresh_stream_page)
            except Exception as exc:
                self.after(0, lambda: self._log(f"{label} failed: {exc}"))
        threading.Thread(target=worker, daemon=True).start()

    def start_stream(self) -> None:
        self._post_host_control("/api/host/stream/start", "Start stream")

    def stop_stream(self) -> None:
        self._post_host_control("/api/host/stream/stop", "Stop stream")


def main() -> None:
    """Launch the ESPDevLink desktop control center."""
    app = ESPDevLinkGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
