"""Unified host facade used by the HTTP and WebRTC entry points."""
from pathlib import Path

from .status import HostStatus
from .network.discovery import get_endpoint
from .auth.sessions import SessionManager
from .stream_controller import StreamController
from .games.service import GameService
from .config import COMPUTER_NAME


class ESPLinkHost:
    def __init__(self, authorization_code: str):
        self.status_model = HostStatus(name=COMPUTER_NAME)
        self.sessions = SessionManager(authorization_code)
        self.stream = StreamController()
        self.games = GameService(Path(__file__).parent / "games" / "games_config.json")

    def status(self) -> dict:
        return {
            "host": self.status_model.snapshot(),
            "network": get_endpoint().as_dict(),
            "sessions": self.sessions.status(),
            "stream": self.stream.status(),
            "games": self.games.status(),
        }

    def authorize(self, code: str, session_id: str, client_id: str) -> dict:
        session = self.sessions.authorize_and_connect(code, session_id, client_id)
        return {"authorized": True, "session_id": session.session_id, "state": session.state}

    def list_games(self) -> list[dict]:
        return self.games.list()

    def launch_game(self, game_id: str) -> dict:
        result = self.games.launch(game_id)
        self.status_model.update(game=result["name"])
        return result

    def stop_game(self, game_id: str) -> dict:
        result = self.games.stop(game_id)
        self.status_model.update(game="")
        return result

    def start_stream(self) -> None:
        self.stream.start_stream()
        self.status_model.update(stream_state="streaming")

    def stop_stream(self) -> None:
        self.stream.stop_stream()
        self.status_model.update(stream_state="ready")
