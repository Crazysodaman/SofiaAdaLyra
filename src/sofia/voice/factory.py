"""Production TTS composition from environment configuration."""
from __future__ import annotations

import os

from .sapi import WindowsSapiBackend
from .tts import TextToSpeechService


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = raw.strip().casefold()
    if value in {"1", "true", "on", "yes"}:
        return True
    if value in {"0", "false", "off", "no"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def create_tts_service_from_environment() -> TextToSpeechService:
    backend_name = os.environ.get(
        "SOFIA_TTS_BACKEND",
        "sapi",
    ).strip().casefold()
    if backend_name not in {"sapi", "windows-sapi"}:
        raise ValueError(
            "SOFIA_TTS_BACKEND currently supports only 'sapi'"
        )
    voice_hint = os.environ.get("SOFIA_TTS_VOICE")
    if voice_hint is not None:
        voice_hint = voice_hint.strip() or None
    return TextToSpeechService(
        WindowsSapiBackend(),
        enabled=_env_bool("SOFIA_TTS_ENABLED", False),
        voice_hint=voice_hint,
    )
