"""Windows SAPI text-to-speech backend."""
from __future__ import annotations

import sys
from threading import Event

from .prosody_matrix import VoiceProsodyProfile
from .tts import (
    TTSBackendProbe,
    TTSPlaybackReceipt,
    TTSPlaybackState,
)


def sapi_rate(rate_scale: float) -> int:
    """Map normalized Sofía rate to SAPI's -10..10 range."""
    value = round((float(rate_scale) - 1.0) * 16.0)
    return max(-10, min(10, value))


def sapi_volume(volume_scale: float) -> int:
    """Map normalized volume to SAPI's 0..100 range."""
    value = round(float(volume_scale) * 100.0)
    return max(0, min(100, value))


def choose_voice(
    descriptions: tuple[str, ...],
    hint: str | None,
) -> str | None:
    if not descriptions:
        return None
    if hint:
        folded = hint.casefold()
        for description in descriptions:
            if folded in description.casefold():
                return description
    for preferred in ("zira", "aria", "jenny"):
        for description in descriptions:
            if preferred in description.casefold():
                return description
    return descriptions[0]


class WindowsSapiBackend:
    name = "windows-sapi"

    @staticmethod
    def _create_voice():
        if sys.platform != "win32":
            raise RuntimeError("Windows SAPI is available only on Windows")
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        try:
            voice = win32com.client.Dispatch("SAPI.SpVoice")
        except Exception:
            pythoncom.CoUninitialize()
            raise
        return pythoncom, voice

    @staticmethod
    def _tokens(voice):
        collection = voice.GetVoices()
        return tuple(
            (
                collection.Item(index),
                collection.Item(index).GetDescription(),
            )
            for index in range(collection.Count)
        )

    def probe(
        self,
        *,
        voice_hint: str | None = None,
    ) -> TTSBackendProbe:
        if sys.platform != "win32":
            return TTSBackendProbe(
                backend_name=self.name,
                available=False,
                healthy=False,
                reason="Windows SAPI backend requires Windows",
            )
        pythoncom = None
        try:
            pythoncom, voice = self._create_voice()
            tokens = self._tokens(voice)
            descriptions = tuple(
                description for _, description in tokens
            )
            selected = choose_voice(
                descriptions,
                voice_hint,
            )
            return TTSBackendProbe(
                backend_name=self.name,
                available=True,
                healthy=bool(descriptions),
                voices=descriptions,
                selected_voice=selected,
                supported_controls=("rate", "volume"),
                reason=(
                    "Windows SAPI voice engine is ready"
                    if descriptions
                    else "Windows SAPI reported no installed voices"
                ),
            )
        except Exception as exc:
            return TTSBackendProbe(
                backend_name=self.name,
                available=False,
                healthy=False,
                reason=f"{type(exc).__name__}: {exc}",
            )
        finally:
            if pythoncom is not None:
                pythoncom.CoUninitialize()

    def speak(
        self,
        *,
        utterance_id: str,
        text: str,
        profile: VoiceProsodyProfile,
        voice_hint: str | None = None,
        cancel: Event | None = None,
    ) -> TTSPlaybackReceipt:
        if not isinstance(profile, VoiceProsodyProfile):
            raise TypeError("profile must be VoiceProsodyProfile")
        pythoncom, voice = self._create_voice()
        try:
            tokens = self._tokens(voice)
            descriptions = tuple(
                description for _, description in tokens
            )
            selected = choose_voice(
                descriptions,
                voice_hint,
            )
            if selected is not None:
                for token, description in tokens:
                    if description == selected:
                        voice.Voice = token
                        break

            voice.Rate = sapi_rate(profile.rate_scale)
            voice.Volume = sapi_volume(profile.volume_scale)
            voice.Speak(text, 1)  # asynchronous so barge-in can be honored
            while not voice.WaitUntilDone(100):
                if cancel is not None and cancel.is_set():
                    voice.Speak("", 3)  # async + purge pending speech
                    return TTSPlaybackReceipt(
                        utterance_id=utterance_id,
                        state=TTSPlaybackState.CANCELLED,
                        backend_name=self.name,
                        voice_name=selected,
                        applied_controls=("rate", "volume"),
                        error="speech interrupted",
                    )

            return TTSPlaybackReceipt(
                utterance_id=utterance_id,
                state=TTSPlaybackState.SPOKEN,
                backend_name=self.name,
                voice_name=selected,
                applied_controls=("rate", "volume"),
            )
        finally:
            pythoncom.CoUninitialize()
