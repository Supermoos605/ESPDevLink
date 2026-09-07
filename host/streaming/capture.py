"""Windows desktop capture backend abstraction for ESPLink."""
from dataclasses import dataclass
import platform
_DXCAM_IMPORT_ERROR = ""

import sys

# DXcam/comtypes must use the same COM mode as the host's Windows threads.
sys.coinit_flags = 0

try:
    import dxcam
except ImportError:
    dxcam = None

try:
    import dxcam
except ImportError:
    dxcam = None


@dataclass(frozen=True)
class CaptureInfo:
    backend: str
    available: bool
    display_count: int = 0
    note: str = ""


def get_capture_info() -> CaptureInfo:
    if platform.system() != "Windows":
        return CaptureInfo("dxcam", False, note="Windows host required")
    if dxcam is None:
        return CaptureInfo(
            "dxcam",
            False,
            note="DXcam is unavailable: " + _DXCAM_IMPORT_ERROR,
        )
    try:
        cameras = dxcam.device_info()
        display_count = len(cameras) if cameras else 1
    except Exception:
        display_count = 1
    return CaptureInfo("dxcam", True, display_count=display_count,
                       note="DirectX desktop capture backend available")


class WindowsCaptureSource:
    """Capture the selected Windows display as RGB frames using DXcam."""

    def __init__(self, display_index: int = 0, target_fps: int = 60) -> None:
        if display_index < 0:
            raise ValueError("Display index cannot be negative")
        if target_fps <= 0:
            raise ValueError("Target FPS must be positive")
        self.display_index = display_index
        self.target_fps = target_fps
        self.running = False
        self._camera = None

    def start(self) -> None:
        if platform.system() != "Windows":
            raise RuntimeError("Windows desktop capture requires Windows")
        if dxcam is None:
            raise RuntimeError("DXcam is not installed")
        if self.running:
            return
        self._camera = dxcam.create(output_idx=self.display_index, output_color="RGB")
        self._camera.start(target_fps=self.target_fps, video_mode=True)
        self.running = True

    def read(self):
        """Return the newest RGB frame as a NumPy array, or None when unavailable."""
        if not self.running or self._camera is None:
            return None
        return self._camera.get_latest_frame()

    def stop(self) -> None:
        if self._camera is not None:
            self._camera.stop()
        self._camera = None
        self.running = False

    def describe(self) -> dict:
        return {
            "backend": "dxcam",
            "display_index": self.display_index,
            "target_fps": self.target_fps,
            "running": self.running,
        }
