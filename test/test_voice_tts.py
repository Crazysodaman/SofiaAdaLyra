from sofia.voice.prosody_matrix import VoiceProsodyProfile
from sofia.voice.tts import (
    TTSBackendProbe,
    TTSPlaybackReceipt,
    TTSPlaybackState,
    TextToSpeechService,
    prepare_spoken_text,
)
from threading import Event
from dataclasses import replace
from sofia.config.user_settings import RuntimeUserSettings
from sofia.voice.factory import create_tts_service_from_environment


class FakeBackend:
    name = "fake-tts"

    def __init__(self, *, healthy=True, fail=False):
        self.healthy = healthy
        self.fail = fail
        self.calls = []

    def probe(self, *, voice_hint=None):
        return TTSBackendProbe(
            backend_name=self.name,
            available=True,
            healthy=self.healthy,
            voices=("Fake Voice",),
            selected_voice="Fake Voice",
            supported_controls=("rate", "volume"),
            reason=(
                "ready"
                if self.healthy
                else "not healthy"
            ),
        )

    def speak(
        self,
        *,
        utterance_id,
        text,
        profile,
        voice_hint=None,
    ):
        if self.fail:
            raise RuntimeError("backend boom")
        self.calls.append(
            (
                utterance_id,
                text,
                profile,
                voice_hint,
            )
        )
        return TTSPlaybackReceipt(
            utterance_id=utterance_id,
            state=TTSPlaybackState.SPOKEN,
            backend_name=self.name,
            voice_name="Fake Voice",
            applied_controls=("rate", "volume"),
        )


def test_disabled_tts_fails_closed_without_starting_worker():
    service = TextToSpeechService(
        FakeBackend(),
        enabled=False,
    )
    status = service.start()
    receipt = service.submit("hello")

    assert status.enabled is False
    assert status.started is False
    assert receipt.state is TTSPlaybackState.REJECTED
    assert "disabled" in receipt.error


def test_enabled_tts_runs_backend_off_thread_and_records_spoken_receipt():
    backend = FakeBackend()
    service = TextToSpeechService(
        backend,
        enabled=True,
        voice_hint="Fake",
    )
    status = service.start()
    try:
        assert status.started is True
        queued = service.submit(
            "Hello **Sparks**.",
            profile=VoiceProsodyProfile(
                rate_scale=1.05
            ),
        )
        assert queued.state is TTSPlaybackState.QUEUED
        assert service.wait_until_idle(timeout=2.0)
        final = service.last_receipt
        assert final is not None
        assert final.state is TTSPlaybackState.SPOKEN
        assert backend.calls[0][1] == "Hello Sparks."
        assert backend.calls[0][3] == "Fake"
    finally:
        service.stop()


def test_backend_failure_is_contained_in_tts_worker():
    service = TextToSpeechService(
        FakeBackend(fail=True),
        enabled=True,
    )
    service.start()
    try:
        service.submit("hello")
        assert service.wait_until_idle(timeout=2.0)
        final = service.last_receipt
        assert final is not None
        assert final.state is TTSPlaybackState.FAILED
        assert "backend boom" in final.error
    finally:
        service.stop()


def test_unhealthy_backend_never_starts_worker():
    service = TextToSpeechService(
        FakeBackend(healthy=False),
        enabled=True,
    )
    status = service.start()
    receipt = service.submit("hello")

    assert status.started is False
    assert status.healthy is False
    assert receipt.state is TTSPlaybackState.REJECTED


def test_tts_status_prompt_does_not_claim_microphone_or_stt():
    service = TextToSpeechService(
        FakeBackend(),
        enabled=True,
    )
    status = service.start()
    try:
        prompt = status.prompt()
        assert "TRUSTED VOICE RUNTIME EVIDENCE" in prompt
        assert "TTS backend healthy: yes" in prompt
        assert (
            "Microphone/STT/listening state: not established"
            in prompt
        )
    finally:
        service.stop()


def test_spoken_text_removes_markdown_noise_and_code_blocks():
    spoken = prepare_spoken_text(
        "Here is **bold** and "
        "[a link](https://example.com). "
        "```python\nprint('x')\n``` Done."
    )

    assert spoken == (
        "Here is bold and a link. "
        "Code block omitted from speech. Done."
    )


def test_interrupt_cancels_active_speech_and_publishes_final_receipt():
    started = Event()

    class InterruptibleBackend(FakeBackend):
        def speak(self, *, utterance_id, text, profile, voice_hint=None, cancel=None):
            started.set()
            assert cancel is not None
            cancel.wait(2)
            return TTSPlaybackReceipt(
                utterance_id=utterance_id,
                state=TTSPlaybackState.CANCELLED,
                backend_name=self.name,
                error="speech interrupted",
            )

    service = TextToSpeechService(InterruptibleBackend(), enabled=True)
    service.start()
    try:
        service.submit("A long response")
        assert started.wait(1)
        assert service.interrupt() is True
        assert service.wait_until_idle(timeout=2)
        assert service.last_receipt.state is TTSPlaybackState.CANCELLED
    finally:
        service.stop()


def test_persisted_mute_overrides_legacy_environment_enable(monkeypatch):
    monkeypatch.setenv("SOFIA_TTS_ENABLED", "true")
    settings = replace(
        RuntimeUserSettings(), voice_output_enabled=True, voice_muted=True,
    )
    assert create_tts_service_from_environment(settings).enabled is False
