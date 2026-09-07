"""Optional Windows input sink for ESPLink browser streaming sessions."""
from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes

from .input import InputEvent


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]


class _INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


class WindowsInputBackend:
    """Translate validated browser input events into Windows SendInput calls.

    The backend is disabled by default. Set ``ESPLINK_INPUT_ENABLED=1`` on the
    Windows host before starting the server to allow events to reach Windows.
    Gamepad events are intentionally left for a future virtual-controller
    backend; keyboard and mouse are handled without third-party packages.
    """

    _INPUT_KEYBOARD = 1
    _INPUT_MOUSE = 0
    _KEYEVENTF_KEYUP = 0x0002
    _MOUSEEVENTF_MOVE = 0x0001
    _MOUSEEVENTF_LEFTDOWN = 0x0002
    _MOUSEEVENTF_LEFTUP = 0x0004
    _MOUSEEVENTF_RIGHTDOWN = 0x0008
    _MOUSEEVENTF_RIGHTUP = 0x0010
    _MOUSEEVENTF_MIDDLEDOWN = 0x0020
    _MOUSEEVENTF_MIDDLEUP = 0x0040
    _MOUSEEVENTF_XDOWN = 0x0080
    _MOUSEEVENTF_XUP = 0x0100
    _MOUSEEVENTF_WHEEL = 0x0800
    _MOUSEEVENTF_HWHEEL = 0x1000
    _MOUSEEVENTF_ABSOLUTE = 0x8000
    _MOUSEEVENTF_VIRTUALDESK = 0x4000
    _XBUTTON1 = 0x0001
    _XBUTTON2 = 0x0002

    _KEYBDINPUT = _KEYBDINPUT
    _MOUSEINPUT = _MOUSEINPUT
    _INPUTUNION = _INPUTUNION
    _INPUT = _INPUT

    _CODES = {
        "Backspace": 0x08, "Tab": 0x09, "Enter": 0x0D, "ShiftLeft": 0xA0,
        "ShiftRight": 0xA1, "ControlLeft": 0xA2, "ControlRight": 0xA3,
        "AltLeft": 0xA4, "AltRight": 0xA5, "Pause": 0x13, "CapsLock": 0x14,
        "Escape": 0x1B, "Space": 0x20, "PageUp": 0x21, "PageDown": 0x22,
        "End": 0x23, "Home": 0x24, "ArrowLeft": 0x25, "ArrowUp": 0x26,
        "ArrowRight": 0x27, "ArrowDown": 0x28, "Insert": 0x2D, "Delete": 0x2E,
        "MetaLeft": 0x5B, "MetaRight": 0x5C, "ContextMenu": 0x5D,
        "Numpad0": 0x60, "Numpad1": 0x61, "Numpad2": 0x62, "Numpad3": 0x63,
        "Numpad4": 0x64, "Numpad5": 0x65, "Numpad6": 0x66, "Numpad7": 0x67,
        "Numpad8": 0x68, "Numpad9": 0x69, "NumpadMultiply": 0x6A,
        "NumpadAdd": 0x6B, "NumpadSubtract": 0x6D, "NumpadDecimal": 0x6E,
        "NumpadDivide": 0x6F, "F1": 0x70, "F2": 0x71, "F3": 0x72,
        "F4": 0x73, "F5": 0x74, "F6": 0x75, "F7": 0x76, "F8": 0x77,
        "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
        "NumLock": 0x90, "ScrollLock": 0x91, "Semicolon": 0xBA,
        "Equal": 0xBB, "Comma": 0xBC, "Minus": 0xBD, "Period": 0xBE,
        "Slash": 0xBF, "Backquote": 0xC0, "BracketLeft": 0xDB,
        "Backslash": 0xDC, "BracketRight": 0xDD, "Quote": 0xDE,
    }
    _MOUSE_BUTTONS = {
        "left": (_MOUSEEVENTF_LEFTDOWN, _MOUSEEVENTF_LEFTUP),
        "right": (_MOUSEEVENTF_RIGHTDOWN, _MOUSEEVENTF_RIGHTUP),
        "middle": (_MOUSEEVENTF_MIDDLEDOWN, _MOUSEEVENTF_MIDDLEUP),
        "x1": (_MOUSEEVENTF_XDOWN, _MOUSEEVENTF_XUP),
        "x2": (_MOUSEEVENTF_XDOWN, _MOUSEEVENTF_XUP),
    }

    def __init__(self, enabled: bool | None = None, sender=None) -> None:
        self.platform_supported = sys.platform == "win32"
        self.enabled = bool(os.environ.get("ESPLINK_INPUT_ENABLED")) if enabled is None else bool(enabled)
        self.enabled = self.enabled and self.platform_supported
        self._user32 = ctypes.windll.user32 if self.platform_supported else None
        self._sender = sender or (self._user32.SendInput if self._user32 is not None else None)
        self._width = 65535
        self._height = 65535

    @property
    def status(self) -> dict:
        return {
            "enabled": self.enabled,
            "platform_supported": self.platform_supported,
            "keyboard": self.enabled,
            "mouse": self.enabled,
            "gamepad": False,
        }

    def handle(self, event: InputEvent | dict) -> bool:
        if not self.enabled:
            return False
        if isinstance(event, dict):
            event = InputEvent(
                type=str(event.get("type", "")),
                action=str(event.get("action", "")),
                data=dict(event.get("data", {})),
                created_at=float(event.get("created_at", 0)),
            )
        if event.type == "key":
            return self._keyboard(event)
        if event.type == "mouse":
            return self._mouse(event)
        return False

    def _make_keyboard(self, vk: int, flags: int) -> _INPUT:
        value = self._INPUT()
        value.type = self._INPUT_KEYBOARD
        value.ki = self._KEYBDINPUT(vk, 0, flags, 0, 0)
        return value

    def _keyboard(self, event: InputEvent) -> bool:
        if event.action not in {"down", "up"}:
            return False
        code = str(event.data.get("code", ""))
        key = str(event.data.get("key", ""))
        vk = self._CODES.get(code)
        if vk is None and len(code) == 4 and code[:3] == "Key" and code[3].isalpha():
            vk = ord(code[3].upper())
        if vk is None and len(code) == 6 and code[:5] == "Digit" and code[5].isdigit():
            vk = ord(code[5])
        if vk is None and len(key) == 1 and self._user32 is not None:
            scanned = self._user32.VkKeyScanW(ord(key))
            if scanned != -1:
                vk = scanned & 0xFF
        if vk is None or not 0 <= vk <= 0xFF:
            return False
        flags = 0 if event.action == "down" else self._KEYEVENTF_KEYUP
        value = self._make_keyboard(vk, flags)
        return self._sender(1, ctypes.byref(value), ctypes.sizeof(value)) == 1

    def _mouse(self, event: InputEvent) -> bool:
        action = event.action
        data = event.data
        if action == "move":
            try:
                x = min(1.0, max(0.0, float(data.get("x", 0))))
                y = min(1.0, max(0.0, float(data.get("y", 0))))
            except (TypeError, ValueError):
                return False
            value = self._INPUT()
            value.type = self._INPUT_MOUSE
            value.mi = self._MOUSEINPUT(
                int(x * self._width), int(y * self._height), 0,
                self._MOUSEEVENTF_MOVE | self._MOUSEEVENTF_ABSOLUTE | self._MOUSEEVENTF_VIRTUALDESK,
                0, 0,
            )
            return self._sender(1, ctypes.byref(value), ctypes.sizeof(value)) == 1

        if action in {"down", "up"}:
            button = str(data.get("button", "left")).lower()
            flags = self._MOUSE_BUTTONS.get(button)
            if flags is None:
                return False
            mouse_flags = flags[0] if action == "down" else flags[1]
            mouse_data = self._XBUTTON1 if button == "x1" else self._XBUTTON2 if button == "x2" else 0
            value = self._INPUT()
            value.type = self._INPUT_MOUSE
            value.mi = self._MOUSEINPUT(0, 0, mouse_data, mouse_flags, 0, 0)
            return self._sender(1, ctypes.byref(value), ctypes.sizeof(value)) == 1

        if action in {"wheel", "scroll"}:
            try:
                delta_y = int(float(data.get("deltaY", 0)))
                delta_x = int(float(data.get("deltaX", 0)))
            except (TypeError, ValueError):
                return False
            if not delta_y and not delta_x:
                return False
            if delta_y and not self._send_wheel(delta_y, horizontal=False):
                return False
            if delta_x and not self._send_wheel(delta_x, horizontal=True):
                return False
            return True
        return False

    def _send_wheel(self, delta: int, horizontal: bool) -> bool:
        value = self._INPUT()
        value.type = self._INPUT_MOUSE
        flags = self._MOUSEEVENTF_HWHEEL if horizontal else self._MOUSEEVENTF_WHEEL
        value.mi = self._MOUSEINPUT(0, 0, delta & 0xFFFFFFFF, flags, 0, 0)
        return self._sender(1, ctypes.byref(value), ctypes.sizeof(value)) == 1
