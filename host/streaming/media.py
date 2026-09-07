"""Host media source registry."""
from ..webrtc.media import MediaPipeline, MediaSource


class HostMediaRegistry:
    def __init__(self) -> None:
        self.pipeline = MediaPipeline()

    def configure_defaults(self) -> None:
        self.pipeline.register(MediaSource("video", "Windows Desktop"))
        self.pipeline.register(MediaSource("audio", "Windows Default Audio"))

    def status(self) -> dict:
        return self.pipeline.describe()
