"""Voice runtime, speech input/output, and expression planning."""

from .stt import (
    SpeechInputProbe,
    SpeechInputReceipt,
    SpeechInputReceiptStore,
    SpeechInputService,
    SpeechInputState,
    WindowsSpeechRecognitionBackend,
)

from .factory import (
    create_stt_service_from_settings,
    create_tts_service_from_environment,
)
from .prosody_matrix import VoiceProsodyMatrix, VoiceProsodyPlan, VoiceProsodyProfile, VoiceUrgency
from .sapi import WindowsSapiBackend
from .tts import (
    TTSBackendProbe,
    TTSPlaybackReceipt,
    TTSPlaybackState,
    TTSStatus,
    TextToSpeechService,
    prepare_spoken_text,
)

__all__ = [
    "TTSBackendProbe",
    "TTSPlaybackReceipt",
    "TTSPlaybackState",
    "TTSStatus",
    "TextToSpeechService",
    "SpeechInputProbe",
    "SpeechInputReceipt",
    "SpeechInputReceiptStore",
    "SpeechInputService",
    "SpeechInputState",
    "VoiceProsodyMatrix",
    "VoiceProsodyPlan",
    "VoiceProsodyProfile",
    "VoiceUrgency",
    "WindowsSapiBackend",
    "WindowsSpeechRecognitionBackend",
    "create_stt_service_from_settings",
    "create_tts_service_from_environment",
    "prepare_spoken_text",
]
