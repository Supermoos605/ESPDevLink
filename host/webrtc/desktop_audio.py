"""Windows WASAPI loopback audio track for browser streaming."""
from __future__ import annotations

import asyncio
import queue
import threading
from fractions import Fraction

try:
    import numpy as np
    import soundcard as sc
    from aiortc import MediaStreamTrack
    from av import AudioFrame
except ImportError:
    np = None
    sc = None
    MediaStreamTrack = None
    AudioFrame = None


class DesktopAudioTrack(MediaStreamTrack if MediaStreamTrack is not None else object):
    """Capture the default Windows speaker mix through a WASAPI loopback device."""

    kind = "audio"
    sample_rate = 48000
    channels = 2
    block_frames = 960  # 20 ms at 48 kHz

    def __init__(self) -> None:
        if sc is None or np is None or AudioFrame is None:
            raise RuntimeError("soundcard is not installed; Windows loopback audio is unavailable")
        super().__init__()
        self._queue: queue.Queue = queue.Queue(maxsize=8)
        self._stop_event = threading.Event()
        self._started = threading.Event()
        self._error: Exception | None = None
        self._pts = 0
        self._thread = threading.Thread(target=self._capture, name="ESPLink-Audio", daemon=True)
        self._thread.start()
        if not self._started.wait(timeout=3):
            self.stop()
            raise RuntimeError("Windows loopback audio failed to start")
        if self._error is not None:
            error = self._error
            self.stop()
            raise RuntimeError(f"Windows loopback audio failed to initialize: {error}") from error

    def _capture(self) -> None:
        try:
            speaker = sc.default_speaker()
            loopback = sc.get_microphone(speaker.name, include_loopback=True)
            self._started.set()
            with loopback.recorder(samplerate=self.sample_rate, channels=[0, 1], blocksize=self.block_frames) as recorder:
                while not self._stop_event.is_set():
                    data = recorder.record(numframes=self.block_frames)
                    if data is None or len(data) == 0:
                        continue
                    array = np.asarray(data, dtype=np.float32)
                    if array.ndim == 1:
                        array = np.column_stack((array, array))
                    elif array.shape[1] == 1:
                        array = np.repeat(array, 2, axis=1)
                    elif array.shape[1] > 2:
                        array = array[:, :2]
                    # PyAV expects planar audio arrays as (channels, samples).
                    frame = AudioFrame.from_ndarray(array.T, format="fltp", layout="stereo")
                    frame.sample_rate = self.sample_rate
                    frame.pts = self._pts
                    frame.time_base = Fraction(1, self.sample_rate)
                    self._pts += frame.samples
                    try:
                        self._queue.put(frame, timeout=0.25)
                    except queue.Full:
                        try:
                            self._queue.get_nowait()
                        except queue.Empty:
                            pass
                        try:
                            self._queue.put_nowait(frame)
                        except queue.Full:
                            pass
        except Exception as exc:
            self._error = exc
            self._started.set()
            try:
                self._queue.put_nowait(None)
            except queue.Full:
                pass

    async def recv(self):
        if self._error is not None and self._queue.empty():
            raise RuntimeError(f"Windows loopback audio stopped: {self._error}") from self._error
        frame = await asyncio.to_thread(self._queue.get)
        if frame is None:
            error = self._error or RuntimeError("Windows loopback audio stopped")
            raise error
        return frame

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2)
        super().stop()
