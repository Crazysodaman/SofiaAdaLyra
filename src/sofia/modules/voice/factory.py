"""Production TTS/STT composition. Voice modules remain opt-in and Core-free."""
from __future__ import annotations

import os

from sofia.platform.config.user_settings import RuntimeUserSettings

from .sapi import WindowsSapiBackend
from .tts import TextToSpeechService
from .stt import SpeechInputService, WindowsSpeechRecognitionBackend


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


def create_tts_service_from_environment(
    settings: RuntimeUserSettings | None = None,
) -> TextToSpeechService:
    if settings is not None and not isinstance(settings, RuntimeUserSettings):
        raise TypeError("settings must be RuntimeUserSettings or None")
    backend_name = os.environ.get("SOFIA_TTS_BACKEND", "sapi").strip().casefold()
    if backend_name not in {"sapi", "windows-sapi", "qwen3-local-bluehour"}:
        raise ValueError("SOFIA_TTS_BACKEND supports 'sapi' and 'qwen3-local-bluehour'")
    voice_hint = os.environ.get("SOFIA_TTS_VOICE")
    if voice_hint is not None:
        voice_hint = voice_hint.strip() or None
    elif settings is not None:
        voice_hint = settings.voice_output_name
    enabled = (
        _env_bool("SOFIA_TTS_ENABLED", False)
        if "SOFIA_TTS_ENABLED" in os.environ
        else bool(settings is not None and settings.voice_output_enabled and not settings.voice_muted)
    )
    if settings is not None and settings.voice_muted:
        enabled = False
    if backend_name == "qwen3-local-bluehour":
        from .qwen_local import QwenLocalBluehourBackend
        from .voice_asset import VOICE_PROFILE_ID
        location = os.environ.get("AEGIS_VOICE_PROFILE_DIR", "").strip()
        core_id = os.environ.get("AEGIS_VOICE_CORE_ID", "").strip()
        if not location or not core_id:
            raise ValueError("AEGIS_VOICE_PROFILE_DIR and AEGIS_VOICE_CORE_ID required for neural voice")
        if voice_hint not in (None, VOICE_PROFILE_ID):
            raise ValueError("requested TTS voice is not the approved Bluehour profile")
        backend = QwenLocalBluehourBackend(
            location, core_identity_id=core_id,
            allow_model_download=_env_bool("AEGIS_VOICE_ALLOW_DOWNLOAD", False),
            keep_model_warm=_env_bool("AEGIS_VOICE_KEEP_MODEL_WARM", False),
            playback_device=os.environ.get("AEGIS_VOICE_OUTPUT_DEVICE") or None,
        )
        voice_hint = VOICE_PROFILE_ID
    else:
        backend = WindowsSapiBackend()
    return TextToSpeechService(backend, enabled=enabled, voice_hint=voice_hint)


def create_stt_service_from_settings(
    settings: RuntimeUserSettings,
) -> SpeechInputService:
    if not isinstance(settings, RuntimeUserSettings):
        raise TypeError("settings must be RuntimeUserSettings")
    return SpeechInputService(
        WindowsSpeechRecognitionBackend(), enabled=settings.voice_input_enabled,
        muted=settings.voice_muted, device_id=settings.voice_input_device,
    )
