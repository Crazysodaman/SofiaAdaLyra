"""TTS worker drain/unload regression on an interruptible fake backend."""
from threading import Event

import pytest

from sofia.modules.voice.tts import (
    TextToSpeechService, TTSBackendProbe, TTSPlaybackReceipt, TTSPlaybackState,
)

pytestmark = [pytest.mark.pkg_voice]


class DrainBackend:
    name = "fake-neural-drain"

    def __init__(self):
        self.active = Event()
        self.release = Event()
        self.unloads = 0

    def probe(self, *, voice_hint=None):
        return TTSBackendProbe(backend_name=self.name, available=True,
                               healthy=True, reason="fake backend ready")

    def speak(self, *, utterance_id, text, profile, voice_hint=None, cancel=None):
        self.active.set()
        self.release.wait(3)
        return TTSPlaybackReceipt(
            utterance_id=utterance_id,
            state=TTSPlaybackState.CANCELLED if cancel.is_set() else TTSPlaybackState.SPOKEN,
            backend_name=self.name,
        )

    def unload(self):
        self.unloads += 1


def test_stop_preserves_gpu_worker_ownership_until_drain_and_unloads_after():
    backend = DrainBackend()
    service = TextToSpeechService(backend, enabled=True)
    service.start()
    service.submit("hello")
    assert backend.active.wait(2)
    service.stop(timeout=.01)
    assert service.status().started
    assert backend.unloads == 0
    backend.release.set()
    service.stop(timeout=2)
    assert not service.status().started
    assert backend.unloads == 1
