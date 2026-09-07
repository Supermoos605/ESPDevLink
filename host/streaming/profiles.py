"""Streaming profile negotiation and manifest generation."""
from .config import EncoderProfile, StreamConfig
from .capture import get_capture_info


def negotiate_profile(config: StreamConfig, encoder: EncoderProfile, client: dict | None = None) -> dict:
    client = client or {}
    codecs = {str(c).upper() for c in client.get("video_codecs", [])}
    chosen = encoder.codec.upper()
    if codecs and chosen not in codecs:
        for candidate in ("H264", "VP8", "VP9", "AV1"):
            if candidate in codecs:
                chosen = candidate
                break
        else:
            raise ValueError("No compatible video codec")
    return {"codec": chosen,
            "width": min(config.width, int(client.get("max_width", config.width))),
            "height": min(config.height, int(client.get("max_height", config.height))),
            "fps": min(config.fps, int(client.get("max_fps", config.fps))),
            "video_bitrate_kbps": config.video_bitrate_kbps,
            "audio_bitrate_kbps": config.audio_bitrate_kbps}


def build_manifest(config: StreamConfig | None = None, encoder: EncoderProfile | None = None) -> dict:
    config = config or StreamConfig()
    encoder = encoder or EncoderProfile()
    encoder.validate(config)
    capture = get_capture_info()
    return {"version": 1,
            "capture": {"backend": capture.backend, "available": capture.available, "note": capture.note},
            "video": config.as_dict(), "encoder": encoder.as_dict(),
            "audio": {"supported": True, "source": "Windows Default Audio"}, "transport": "WebRTC"}
