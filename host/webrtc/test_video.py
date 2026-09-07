"""Synthetic video track used to validate the ESPLink WebRTC media path."""
import asyncio

try:
    from av import VideoFrame
    from aiortc import VideoStreamTrack
except ImportError:
    VideoFrame = None
    VideoStreamTrack = None


class TestVideoTrack(VideoStreamTrack if VideoStreamTrack is not None else object):
    """Generate a lightweight static test pattern until Windows capture is ready."""

    width = 640
    height = 360

    def __init__(self) -> None:
        if VideoStreamTrack is None or VideoFrame is None:
            raise RuntimeError("aiortc and PyAV are required for the test video track")
        super().__init__()
        template = VideoFrame(width=self.width, height=self.height, format="rgb24")
        plane = template.planes[0]
        data = bytearray(plane.buffer_size)
        for y in range(self.height):
            for x in range(self.width):
                i = y * plane.line_size + x * 3
                data[i] = x % 256
                data[i + 1] = y % 256
                data[i + 2] = 160
        plane.update(data)
        self._template = bytes(plane)
        self._line_size = plane.line_size

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        frame = VideoFrame(width=self.width, height=self.height, format="rgb24")
        frame.planes[0].update(self._template)
        frame.pts = pts
        frame.time_base = time_base
        await asyncio.sleep(0)
        return frame
