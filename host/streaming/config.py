"""Streaming configuration and encoder profile."""
from dataclasses import dataclass


@dataclass(frozen=True)
class StreamConfig:
    width: int = 1280
    height: int = 720
    fps: int = 60
    video_bitrate_kbps: int = 6000
    audio_bitrate_kbps: int = 128

    def __post_init__(self):
        if not 320 <= self.width <= 7680 or not 240 <= self.height <= 4320:
            raise ValueError("Unsupported stream resolution")
        if not 1 <= self.fps <= 120:
            raise ValueError("FPS must be between 1 and 120")
        if not 250 <= self.video_bitrate_kbps <= 50000:
            raise ValueError("Video bitrate is outside the supported range")
        if not 32 <= self.audio_bitrate_kbps <= 512:
            raise ValueError("Audio bitrate is outside the supported range")

    def as_dict(self) -> dict:
        return {"width": self.width, "height": self.height, "fps": self.fps,
                "video_bitrate_kbps": self.video_bitrate_kbps,
                "audio_bitrate_kbps": self.audio_bitrate_kbps}


@dataclass(frozen=True)
class EncoderProfile:
    codec: str = "H264"
    profile: str = "main"
    hardware_acceleration: bool = True
    keyframe_interval: int = 120

    def validate(self, config: StreamConfig) -> None:
        if self.codec.upper() not in {"H264", "VP8", "VP9", "AV1"}:
            raise ValueError("Unsupported video codec")
        if self.keyframe_interval < 1:
            raise ValueError("Keyframe interval must be positive")
        if config.fps > 0 and self.keyframe_interval > config.fps * 10:
            raise ValueError("Keyframe interval is too large for the configured FPS")

    def as_dict(self) -> dict:
        return {"codec": self.codec.upper(), "profile": self.profile,
                "hardware_acceleration": self.hardware_acceleration,
                "keyframe_interval": self.keyframe_interval}
