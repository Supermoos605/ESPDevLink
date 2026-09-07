"""Streaming health, adaptation, and runtime state."""
from dataclasses import dataclass
from time import monotonic
from .config import StreamConfig, EncoderProfile


@dataclass
class StreamHealth:
    state: str = "ready"
    frames_sent: int = 0
    bytes_sent: int = 0
    last_frame_at: float | None = None
    errors: int = 0

    def frame_sent(self, byte_count: int = 0) -> None:
        self.frames_sent += 1
        self.bytes_sent += max(0, int(byte_count))
        self.last_frame_at = monotonic()

    def error(self) -> None:
        self.errors += 1

    def snapshot(self) -> dict:
        age = None if self.last_frame_at is None else max(0.0, monotonic() - self.last_frame_at)
        return {"state": self.state, "frames_sent": self.frames_sent, "bytes_sent": self.bytes_sent,
                "seconds_since_frame": age, "errors": self.errors}


@dataclass
class AdaptiveStream:
    config: StreamConfig
    min_fps: int = 15
    min_bitrate_kbps: int = 1000

    def __post_init__(self):
        self.current_fps = self.config.fps
        self.current_bitrate_kbps = self.config.video_bitrate_kbps

    def report(self, packet_loss_percent: float = 0.0, rtt_ms: float = 0.0) -> dict:
        loss, rtt = max(0.0, float(packet_loss_percent)), max(0.0, float(rtt_ms))
        if loss >= 5.0 or rtt >= 180.0:
            self.current_bitrate_kbps = max(self.min_bitrate_kbps, int(self.current_bitrate_kbps * 0.8))
            self.current_fps = max(self.min_fps, self.current_fps - 5)
        elif loss <= 1.0 and rtt <= 80.0:
            self.current_bitrate_kbps = min(self.config.video_bitrate_kbps, int(self.current_bitrate_kbps * 1.1))
            self.current_fps = min(self.config.fps, self.current_fps + 5)
        return self.snapshot(loss, rtt)

    def snapshot(self, loss: float = 0.0, rtt: float = 0.0) -> dict:
        return {"fps": self.current_fps, "video_bitrate_kbps": self.current_bitrate_kbps,
                "packet_loss_percent": loss, "rtt_ms": rtt}


class StreamRuntime:
    def __init__(self, config=None, encoder=None):
        self.config = config or StreamConfig()
        self.encoder = encoder or EncoderProfile()
        self.encoder.validate(self.config)
        self.health = StreamHealth()
        self.adaptive = AdaptiveStream(self.config)

    def frame_sent(self, byte_count=0):
        self.health.frame_sent(byte_count)

    def report_network(self, packet_loss_percent=0.0, rtt_ms=0.0):
        return self.adaptive.report(packet_loss_percent, rtt_ms)

    def start(self):
        self.health.state = "streaming"

    def stop(self):
        self.health.state = "ready"

    def status(self):
        return {"state": self.health.state, "health": self.health.snapshot(),
                "quality": self.adaptive.snapshot(), "encoder": self.encoder.as_dict(),
                "config": self.config.as_dict()}
