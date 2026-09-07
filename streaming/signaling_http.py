"""Small HTTP-facing adapter for the ESPLink WebRTC signaling manager.

The simulator can import these handlers directly. Keeping HTTP concerns here
means the signaling state machine remains usable by the future ESP32/host
transport without duplicating session logic.
"""

from signaling import SignalingManager

manager = SignalingManager()


def create_session(client_id: str) -> dict:
    session = manager.create(client_id)
    return {"ok": True, "peer_id": session.peer_id, "client_id": session.client_id}


def send_message(peer_id: str, message: dict) -> dict:
    session = manager.get(peer_id)
    if not isinstance(message, dict) or not message.get("type"):
        raise ValueError("WebRTC message requires a type")
    session.queue(message)
    return {"ok": True}


def receive_messages(peer_id: str) -> dict:
    session = manager.get(peer_id)
    return {"ok": True, "peer_id": peer_id, "messages": session.drain()}


def close_session(peer_id: str) -> dict:
    manager.close(peer_id)
    return {"ok": True, "peer_id": peer_id, "closed": True}
