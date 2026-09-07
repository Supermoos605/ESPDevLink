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
        self.capture.start()

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        image = self.capture.read()
        while image is None:
            await asyncio.sleep(0.002)
            image = self.capture.read()
        frame = VideoFrame.from_ndarray(image, format="rgb24")
        frame.pts = pts
        frame.time_base = time_base
        return frame

    def stop(self) -> None:
        self.capture.stop()
        super().stop()
