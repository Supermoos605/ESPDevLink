"""Launcher-agnostic game discovery for the ESPLink host."""
from dataclasses import dataclass
from pathlib import Path
import json


@dataclass(frozen=True)
class Game:
    id: str
    name: str
    launcher: str
    executable: str = ""
    steam_app_id: str = ""


def discover_games(config_path: str | Path) -> list[Game]:
    path = Path(config_path)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("games", [])
    return [
        Game(
            id=str(item.get("id", item.get("name", ""))).strip(),
            name=str(item.get("name", "Untitled Game")).strip(),
            launcher=str(item.get("launcher", "unknown")).strip(),
            executable=str(item.get("executable", "")).strip(),
            steam_app_id=str(item.get("steam_app_id", "")).strip(),
        )
        for item in entries
        if str(item.get("name", "")).strip()
    ]


def games_payload(games: list[Game]) -> list[dict]:
    return [{"id": g.id, "name": g.name, "launcher": g.launcher} for g in games]
