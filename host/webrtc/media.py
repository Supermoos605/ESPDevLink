"""Media-source interfaces for the Windows WebRTC pipeline."""
from dataclasses import dataclass
from typing import Literal

MediaKind = Literal["video", "audio"]


@dataclass(frozen=True)
class MediaSource:
    kind: MediaKind
    name: str
    enabled: bool = True


class MediaPipeline:
    def __init__(self) -> None:
        self.sources: dict[str, MediaSource] = {}
        self.running = False

    def register(self, source: MediaSource) -> None:
        if source.kind not in {"video", "audio"}:
            raise ValueError("Unsupported media kind")
        self.sources[source.kind] = source

    def start(self) -> None:
        if not self.sources:
            raise RuntimeError("No media sources registered")
        self.running = True

    def stop(self) -> None:
        self.running = False

    def describe(self) -> dict:
        return {"running": self.running, "sources": {
            kind: {"name": source.name, "enabled": source.enabled}
            for kind, source in self.sources.items()
        }}
