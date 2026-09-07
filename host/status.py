"""Stable status model exposed to the ESPLink dashboard."""
from dataclasses import dataclass, field
from time import time


@dataclass
class HostStatus:
    name: str = "ESPLink Host"
    online: bool = True
    game: str = ""
    stream_state: str = "ready"
    updated_at: float = field(default_factory=time)

    def update(self, **values) -> None:
        for key in ("name", "online", "game", "stream_state"):
            if key in values and values[key] is not None:
                setattr(self, key, values[key])
        self.updated_at = time()

    def snapshot(self) -> dict:
        return {
            "name": self.name,
            "online": self.online,
            "game": self.game,
            "stream": self.stream_state,
            "updated_at": self.updated_at,
        }
