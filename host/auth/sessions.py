"""Authentication and client-session management for ESPLink."""
from dataclasses import dataclass
from time import time
import hmac


class SessionAuthorizer:
    def __init__(self, authorization_code: str):
        if not authorization_code:
            raise ValueError("authorization_code must not be empty")
        self._code = authorization_code

    def authorize(self, supplied_code: str) -> bool:
        return isinstance(supplied_code, str) and hmac.compare_digest(supplied_code, self._code)

    def status(self) -> dict:
        return {"authorization_required": True}


@dataclass
class ClientSession:
    session_id: str
    client_id: str
    connected_at: float
    last_seen: float = 0.0
    state: str = "connected"


class SessionManager:
    def __init__(self, authorization_code: str):
        self.authorizer = SessionAuthorizer(authorization_code)
        self.sessions: dict[str, ClientSession] = {}

    def authorize_and_connect(self, supplied_code: str, session_id: str, client_id: str) -> ClientSession:
        if not self.authorizer.authorize(supplied_code):
            raise PermissionError("Invalid authorization code")
        return self.connect(session_id, client_id)

    def connect(self, session_id: str, client_id: str) -> ClientSession:
        if not session_id or not client_id:
            raise ValueError("session_id and client_id are required")
        now = time()
        session = ClientSession(session_id, client_id, now, now)
        self.sessions[session_id] = session
        return session

    def get(self, session_id: str) -> ClientSession:
        try:
            return self.sessions[session_id]
        except KeyError as exc:
            raise KeyError("Unknown session") from exc

    def touch(self, session_id: str) -> ClientSession:
        session = self.get(session_id)
        session.last_seen = time()
        return session

    def cleanup_expired(self, max_age: float = 1800.0) -> int:
        now = time()
        expired = [sid for sid, session in self.sessions.items()
                   if now - session.last_seen > max_age]
        for sid in expired:
            self.disconnect(sid)
        return len(expired)

    def set_state(self, session_id: str, state: str) -> None:
        if not state:
            raise ValueError("state is required")
        self.get(session_id).state = state

    def disconnect(self, session_id: str) -> None:
        session = self.sessions.pop(session_id, None)
        if session is not None:
            session.state = "closed"

    def snapshot(self) -> list[dict]:
        return [{"session_id": s.session_id, "client_id": s.client_id,
                 "connected_at": s.connected_at, "last_seen": s.last_seen, "state": s.state}
                for s in self.sessions.values()]

    def status(self) -> dict:
        return {"authorization": self.authorizer.status(), "sessions": self.snapshot()}


class ConnectionManager(SessionManager):
    """Session-only compatibility name retained during the API cleanup."""
    def __init__(self, authorization_code: str | None = None):
        super().__init__(authorization_code or "disabled")


class AuthenticatedHost:
    """Compatibility facade backed by the consolidated session manager."""
    def __init__(self, authorization_code: str):
        self._sessions = SessionManager(authorization_code)

    def authorize_and_connect(self, supplied_code: str, session_id: str, client_id: str) -> dict:
        session = self._sessions.authorize_and_connect(supplied_code, session_id, client_id)
        return {"authorized": True, "session_id": session.session_id,
                "client_id": session.client_id, "state": session.state}

    def disconnect(self, session_id: str) -> None:
        self._sessions.disconnect(session_id)

    def status(self) -> dict:
        return self._sessions.status()
