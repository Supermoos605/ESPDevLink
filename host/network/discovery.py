"""LAN endpoint discovery for the ESPLink Windows host."""
from dataclasses import dataclass
import socket


@dataclass(frozen=True)
class HostEndpoint:
    host: str
    port: int = 8765
    def as_dict(self) -> dict:
        return {"host": self.host, "port": self.port}


def local_address() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("192.0.2.1", 9))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def get_endpoint(port: int = 8765) -> HostEndpoint:
    return HostEndpoint(local_address(), port)
