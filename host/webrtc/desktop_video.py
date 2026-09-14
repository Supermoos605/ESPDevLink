"""WebRTC video track backed by Windows desktop capture."""
import asyncio

from ..streaming.capture import WindowsCaptureSource

try:
    from av import VideoFrame
    from aiortc import VideoStreamTrack
except ImportError:
    VideoFrame = None
    VideoStreamTrack = None


class DesktopVideoTrack(VideoStreamTrack if VideoStreamTrack is not None else object):
    """Expose the newest DXcam RGB frame as an aiortc video track."""

    def __init__(self, display_index: int = 0, target_fps: int = 30) -> None:
        if VideoStreamTrack is None or VideoFrame is None:
            raise RuntimeError("aiortc and PyAV are required for desktop WebRTC video")
        super().__init__()
        self.capture = WindowsCaptureSource(display_index=display_index, target_fps=target_fps)
        self._stopped = False
        self.frames_sent = 0
        self.frames_empty = 0
        self.last_frame_shape = None
        try:
            self.capture.start()
        except Exception:
            # DXcam may return an existing capture object before reporting that
            # it is already running. Always release that object on failure so a
            # browser reconnect cannot inherit a stuck capture session.
            self.capture.stop()
            raise

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        image = self.capture.read()
        while image is None:
            self.frames_empty += 1
            await asyncio.sleep(0.002)
            image = self.capture.read()
        self.frames_sent += 1
        self.last_frame_shape = list(image.shape) if hasattr(image, "shape") else None
        frame = VideoFrame.from_ndarray(image, format="rgb24")
        frame.pts = pts
        frame.time_base = time_base
        return frame


    def stats(self) -> dict:
        return {
            "frames_sent": self.frames_sent,
            "empty_reads": self.frames_empty,
            "frame_shape": self.last_frame_shape,
            "target_fps": self.capture.target_fps if hasattr(self.capture, "target_fps") else None,
        }

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        self.capture.stop()
        super().stop()
