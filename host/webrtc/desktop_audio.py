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
        self._stats_lock = threading.Lock()
        self._capture_frames = 0
        self._capture_samples = 0
        self._non_silent_frames = 0
        self._peak = 0.0
        self._rms = 0.0
        self._queue_drops = 0
        self._device_name = ""
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
            self._device_name = speaker.name
            print(f"[Audio] Windows output capture device: {speaker.name}")
            print(f"[Audio] Default speaker object: {speaker!r}")
            loopback = sc.get_microphone(speaker.name, include_loopback=True)
            print(f"[Audio] WASAPI loopback device: {loopback.name}")
            self._started.set()
            with loopback.recorder(samplerate=self.sample_rate, channels=[0, 1], blocksize=self.block_frames) as recorder:
                while not self._stop_event.is_set():
                    data = recorder.record(numframes=self.block_frames)
                    if data is None or len(data) == 0:
                        print("[Audio] Capture returned an empty block")
                        continue
                    array = np.asarray(data, dtype=np.float32)
                    if array.ndim == 1:
                        array = np.column_stack((array, array))
                    elif array.shape[1] == 1:
                        array = np.repeat(array, 2, axis=1)
                    elif array.shape[1] > 2:
                        array = array[:, :2]
                    # SoundCard provides normalized float samples, while the
                    # aiortc/PyAV Opus path is most reliably fed with signed
                    # 16-bit PCM. Convert here so the encoder receives an
                    # explicit, interleaved stereo s16 frame instead of a
                    # float-planar frame that can negotiate successfully but
                    # produce silence in the browser.
                    pcm = np.clip(array, -1.0, 1.0)
                    pcm = (pcm * 32767.0).astype(np.int16)
                    peak = float(np.max(np.abs(array))) if array.size else 0.0
                    rms = float(np.sqrt(np.mean(np.square(array)))) if array.size else 0.0
                    with self._stats_lock:
                        self._capture_frames += 1
                        self._capture_samples += int(array.shape[0])
                        if peak > 0.001:
                            self._non_silent_frames += 1
                        self._peak = peak
                        self._rms = rms
                    # PyAV expects s16 stereo input as (channels, samples)
                    # for a planar AudioFrame; aiortc handles the RTP/Opus
                    # encoding from this canonical PCM representation.
                    frame = AudioFrame.from_ndarray(pcm.T, format="s16", layout="stereo")
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
                        with self._stats_lock:
                            self._queue_drops += 1
                        try:
                            self._queue.put_nowait(frame)
                        except queue.Full:
                            pass
        except Exception as exc:
            self._error = exc
            print(f"[Audio] Capture failed: {exc!r}")
            self._started.set()
            try:
                self._queue.put_nowait(None)
            except queue.Full:
                pass

    def stats(self) -> dict:
        with self._stats_lock:
            return {
                "enabled": True,
                "device": self._device_name,
                "capture_frames": self._capture_frames,
                "capture_samples": self._capture_samples,
                "non_silent_frames": self._non_silent_frames,
                "peak": round(self._peak, 6),
                "rms": round(self._rms, 6),
                "queue_size": self._queue.qsize(),
                "queue_drops": self._queue_drops,
                "error": str(self._error) if self._error else None,
            }

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
