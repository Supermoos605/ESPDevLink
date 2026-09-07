"""Human-readable error categories shared by the Windows host."""
from enum import Enum

class HostError(str, Enum):
    ESP32_OFFLINE = "esp32_offline"
    PC_UNAVAILABLE = "pc_unavailable"
    CONNECTION_FAILED = "connection_failed"
    HOST_DISABLED = "host_disabled"
    INVALID_RESPONSE = "invalid_response"
    UNKNOWN = "unknown"

MESSAGES = {
    HostError.ESP32_OFFLINE: "ESPLink gateway is unavailable.",
    HostError.PC_UNAVAILABLE: "The Windows host is unavailable.",
    HostError.CONNECTION_FAILED: "The connection could not be established.",
    HostError.HOST_DISABLED: "Connections are disabled on this host.",
    HostError.INVALID_RESPONSE: "ESPLink returned an invalid response.",
    HostError.UNKNOWN: "An unexpected ESPLink host error occurred.",
}

def message(error: HostError) -> str:
    return MESSAGES.get(error, MESSAGES[HostError.UNKNOWN])
