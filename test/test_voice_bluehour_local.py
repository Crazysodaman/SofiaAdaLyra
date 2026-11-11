"""CPU-only, no microphone/GPU/no audio hardware tests for owner voice binding.

Neural synthesis and device certification require separate approved host tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from threading import Event
import wave

import numpy as np
import pytest

from sofia.modules.voice.voice_asset import (
    VOICE_PROFILE_ID, file_sha256, import_round9_medium, load_voice_profile,
)
from sofia.modules.voice.qwen_local import QwenLocalBluehourBackend, _shape_audio
from sofia.modules.voice.prosody_matrix import VoiceProsodyProfile
from sofia.modules.voice.tts import TTSPlaybackState


@pytest.fixture
def sample(tmp_path):
    round6 = tmp_path / "round6"
    round9 = tmp_path / "round9"
    round6.mkdir()
    round9.mkdir()
    old_wav = round6 / "sofia_03_rook_bluehour.wav"
    wav = round9 / "sofia_r9_bluehour_REFERENCE_AIR_medium.wav"
    for path in (old_wav, wav):
        with wave.open(str(path), "wb") as dest:
            dest.setnchannels(1)
            dest.setsampwidth(2)
            dest.setframerate(24000)
            dest.writeframes(np.zeros(24000, dtype="<i2").tobytes())
    original = {"round": 6, "variant": "03_rook_bluehour", "text": "Hello, I'm Sofia.",
                "audio_sha256": file_sha256(old_wav)}
    orig_meta = old_wav.with_suffix(".json")
    orig_meta.write_text(json.dumps(original), encoding="utf-8")
    current = {"round": 9, "level": "medium", "filter": "voiced-upper-air-softmask-v1",
               "audio_sha256": file_sha256(wav), "source_sha256": file_sha256(old_wav)}
    wav.with_suffix(".json").write_text(json.dumps(current), encoding="utf-8")
    return wav, orig_meta, tmp_path / "private" / "sofia-voice"


def test_import_reverify_and_protect_from_overwrite(sample):
    wav, original, destination = sample
    imported = import_round9_medium(wav, original, destination, core_identity_id="identity:sofia")
    assert imported.profile_id == VOICE_PROFILE_ID
    assert imported.reference_text == "Hello, I'm Sofia."
    assert imported.wav_sha256 == file_sha256(wav)
    assert load_voice_profile(destination, expected_core_identity_id="identity:sofia") == imported
    with pytest.raises(PermissionError):
        load_voice_profile(destination, expected_core_identity_id="identity:other")
    with pytest.raises(FileExistsError):
        import_round9_medium(wav, original, destination, core_identity_id="identity:sofia")
    installed = destination / wav.name
    installed.write_bytes(installed.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="modified"):
        load_voice_profile(destination, expected_core_identity_id="identity:sofia")


def test_reject_bad_round9_round6_provenance_and_no_write(sample):
    wav, original, destination = sample
    data = json.loads(wav.with_suffix(".json").read_text())
    data["source_sha256"] = "0" * 64
    wav.with_suffix(".json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="does not match"):
        import_round9_medium(wav, original, destination, core_identity_id="identity:sofia")
    assert not destination.exists()


def test_reject_symlink_reference(sample):
    wav, original, destination = sample
    link = wav.parent / "tmp_link.wav"
    try:
        link.symlink_to(wav)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    from sofia.modules.voice.voice_asset import validate_wav
    with pytest.raises(ValueError, match="symlink"):
        validate_wav(link)


class FakeModel:
    def __init__(self):
        self.prepared = 0
        self.requests = []

    def create_voice_clone_prompt(self, *, ref_audio, ref_text, x_vector_only_mode):
        self.prepared += 1
        assert Path(ref_audio).is_file()
        assert ref_text == "Hello, I'm Sofia."
        assert x_vector_only_mode is False
        return {"ref": ref_audio}

    def generate_voice_clone(self, *, text, language, voice_clone_prompt):
        self.requests.append((text, language))
        assert language == "English"
        return [np.full(2400, 0.1, dtype=np.float32)], 24000


def test_qwen_adapter_fake_model_real_profile_and_playback(sample):
    wav, original, destination = sample
    import_round9_medium(wav, original, destination, core_identity_id="identity:sofia")
    model = FakeModel()
    heard = []
    backend = QwenLocalBluehourBackend(
        destination, core_identity_id="identity:sofia",
        model_factory=lambda: model,
        playback=lambda audio, rate, cancel, device: heard.append((len(audio), rate)) or True,
    )
    assert backend.probe().healthy is True
    receipt = backend.speak(utterance_id="u1", text="Test", profile=VoiceProsodyProfile())
    assert receipt.state is TTSPlaybackState.SPOKEN
    assert receipt.voice_name == VOICE_PROFILE_ID
    assert heard == [(2400, 24000)]
    assert model.prepared == 1
    assert backend._model is None  # default releases VRAM when done
    assert receipt.applied_controls == ()
    assert model.requests == [("Test", "English")]


def test_cancellation_before_gpu_model_loading(sample):
    wav, original, destination = sample
    import_round9_medium(wav, original, destination, core_identity_id="identity:sofia")
    made = []
    backend = QwenLocalBluehourBackend(
        destination, core_identity_id="identity:sofia", model_factory=lambda: made.append(1) or FakeModel(),
    )
    cancelled = Event()
    cancelled.set()
    result = backend.speak(utterance_id="u2", text="No", profile=VoiceProsodyProfile(), cancel=cancelled)
    assert result.state is TTSPlaybackState.CANCELLED
    assert made == []


def test_bite_mild_tempo_no_pitch_shift_and_unvoiced_defaults():
    sr = 24000
    x = 0.2 * np.sin(2 * np.pi * 220 * np.arange(sr) / sr)
    unchanged, controls = _shape_audio(x, sr, VoiceProsodyProfile())
    assert len(unchanged) == len(x)
    assert controls == ()
    shaped, controls = _shape_audio(x, sr, VoiceProsodyProfile(tone_tags=("delivery:bite",)))
    assert len(shaped) < len(x)
    assert "delivery:bite" in controls and "rate" in controls
    assert np.isfinite(shaped).all()
