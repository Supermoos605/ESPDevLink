"""ESPLink game discovery and configuration."""
from .manager import Game, discover_games, games_payload
from .service import GameService

__all__ = ["Game", "GameService", "discover_games", "games_payload"]
