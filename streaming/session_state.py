"""Small, dependency-free session state model for ESPLink's streaming UI.

This is deliberately independent of WebRTC and Windows capture. It gives the
host/simulator one consistent state machine to use later.
"""

from dataclasses import dataclass

STATES = ("offline", "ready", "connecting", "streaming", "stopping", "error")
TRANSITIONS = {
    "offline": {"ready", "error"},
    "ready": {"connecting", "offline", "error"},
    "connecting": {"streaming", "stopping", "ready", "error"},
    "streaming": {"stopping", "error"},
    "stopping": {"ready", "offline", "error"},
    "error": {"ready", "offline"},
}


@dataclass
class StreamSession:
    state: str = "offline"
    game: str = ""
    client_id: str = ""

    def transition(self, new_state: str) -> None:
        if new_state not in STATES:
            raise ValueError(f"Unknown stream state: {new_state}")
        if new_state not in TRANSITIONS[self.state]:
            raise ValueError(f"Invalid transition: {self.state} -> {new_state}")
        self.state = new_state

    def start(self, game: str, client_id: str = "") -> None:
        if self.state != "ready":
            raise ValueError("A stream can only be started from the ready state")
        self.game = game.strip()
        self.client_id = client_id
        self.transition("connecting")

    def begin_stream(self) -> None:
        self.transition("streaming")

    def stop(self) -> None:
        if self.state not in {"connecting", "streaming"}:
            raise ValueError("There is no active stream to stop")
        self.transition("stopping")
        self.game = ""
        self.client_id = ""
        self.transition("ready")
