"""Game listing and launch service for the ESPLink host."""
from pathlib import Path
import subprocess
import os

from .manager import discover_games, games_payload, Game


class GameService:
    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path)
        self.running: dict[str, int] = {}
        self._processes: dict[str, subprocess.Popen] = {}

    def list(self) -> list[dict]:
        return games_payload(discover_games(self.config_path))

    def get(self, game_id: str) -> Game:
        for game in discover_games(self.config_path):
            if game.id == game_id:
                return game
        raise KeyError("Unknown game")

    def _refresh_processes(self) -> None:
        for game_id, process in list(self._processes.items()):
            if process.poll() is None:
                continue
            self._processes.pop(game_id, None)
            self.running.pop(game_id, None)

    def launch(self, game_id: str) -> dict:
        self._refresh_processes()
        game = self.get(game_id)
        if game.id == "desktop":
            raise RuntimeError("Desktop is not a launchable game")
        if game.launcher.lower() == "steam" and not game.steam_app_id:
            raise RuntimeError("Steam game is missing its App ID")
        if game.launcher.lower() != "steam" and not game.executable:
            raise RuntimeError("This game does not have a launchable executable configured")
        if game.id in self._processes:
            raise RuntimeError("This game is already running")
        if game.launcher.lower() == "steam":
            if not game.steam_app_id:
                raise RuntimeError("Steam game is missing its App ID")
            if os.name != "nt":
                raise RuntimeError("Steam launching is supported on Windows only")
            process = subprocess.Popen(["cmd", "/c", "start", "", f"steam://rungameid/{game.steam_app_id}"])
        else:
            process = subprocess.Popen([game.executable])
        self._processes[game.id] = process
        self.running[game.id] = process.pid
        return {"id": game.id, "name": game.name, "pid": process.pid, "state": "launched"}

    def stop(self, game_id: str) -> dict:
        self._refresh_processes()
        game = self.get(game_id)
        process = self._processes.get(game.id)
        if process is None:
            raise RuntimeError("This game is not running")
        process.terminate()
        self._processes.pop(game.id, None)
        self.running.pop(game.id, None)
        return {"id": game.id, "name": game.name, "pid": process.pid, "state": "stopped"}

    def status(self) -> dict:
        self._refresh_processes()
        return {"games": self.list(), "running": dict(self.running)}
