"""Opt-in, local Qwen3-TTS Base Voice module for owner-approved Bluehour.

No microphone. No paid API. No listening service or standalone Core privileges.
The Platform/TTS queue must enforce SAFE, STOP and output permissions before
calling this backend; backend is *not* a substitute for Platform authority.
"""
from __future__ import annotations

from importlib.util import find_spec
from pathlib import Path
from threading import Event, RLock
from time import sleep
from typing import Callable
import gc
import math

from .prosody_matrix import VoiceProsodyProfile
from .tts import TTSBackendProbe, TTSPlaybackReceipt, TTSPlaybackState
from .voice_asset import MODEL_ID, VOICE_PROFILE_ID, InstalledVoiceProfile, load_voice_profile


def _play_device(audio, rate: int, cancel: Event | None, device: int | str | None) -> bool:
    """Return False only when explicitly interrupted; completion is actual device playback."""
    import sounddevice as sd
    if cancel is not None and cancel.is_set():
        return False
    # The voice worker is the single owner of this device playback call.
    sd.play(audio, samplerate=rate, device=device, blocking=False)
    try:
        stream = sd.get_stream()
        while stream.active:
            if cancel is not None and cancel.is_set():
                sd.stop()
                return False
            sleep(0.02)
        return cancel is None or not cancel.is_set()
    finally:
        sd.stop()


def _shape_audio(audio, sample_rate: int, profile: VoiceProsodyProfile):
    """Apply *supported* volume/rate controls; no fake emotion synthesis.

    ``delivery:bite`` is opt-in and deliberately rare. A mild 7% rate bump
    preserves pitch via phase-vocoder. No blanket pitch shift or breath filter
    is applied because owner already selected a specific cleaned reference.
    """
    import numpy as np
    samples = np.asarray(audio, dtype=np.float32)
    if samples.ndim != 1 or samples.size == 0 or not np.all(np.isfinite(samples)):
        raise ValueError("Qwen produced invalid audio; refusing playback")
    if not isinstance(sample_rate, int) or not 8_000 <= sample_rate <= 192_000:
        raise ValueError("Qwen produced unsupported sample rate")
    controls: list[str] = []
    bite = "delivery:bite" in profile.tone_tags
    speed = min(1.15, max(0.85, float(profile.rate_scale) * (1.07 if bite else 1.0)))
    if abs(speed - 1.0) > 0.001:
        import torch
        import torchaudio.functional as taf
        frame, hop = 1024, 256
        tensor = torch.as_tensor(samples, dtype=torch.float32, device="cpu")
        window = torch.hann_window(frame)
        spec = torch.stft(tensor, n_fft=frame, hop_length=hop, window=window,
                          return_complex=True)
        phases = torch.linspace(0, math.pi * hop, spec.shape[-2])[:, None]
        # torchaudio phase_vocoder expects (freq, time), not (freq, time, 1).
        shifted = taf.phase_vocoder(spec, rate=speed, phase_advance=phases)
        tensor = torch.istft(shifted, n_fft=frame, hop_length=hop, window=window,
                             length=max(1, round(len(samples) / speed)))
        samples = tensor.numpy()
        controls.append("rate")
        if bite:
            controls.append("delivery:bite")
    if abs(float(profile.volume_scale) - 1.0) > 0.001:
        samples = samples * float(profile.volume_scale)
        controls.append("volume")
    peak = float(np.max(np.abs(samples)))
    if peak > 0.98:
        samples = samples * (0.98 / peak)
        controls.append("limiter")
    return np.ascontiguousarray(samples, dtype=np.float32), tuple(controls)


class QwenLocalBluehourBackend:
    """Qwen Base ICL clone with checked owner-local WAV and optional VRAM release.

    `probe` does not allocate the inference model. `speak` never opens a mic.
    Loading and playback happen inside TextToSpeechService's authorized worker.
    A successful receipt means the audio device finished playback, not merely
    that a file or tensor was generated.
    """
    name = "qwen3-local-bluehour"

    def __init__(
        self, profile_dir: Path | str, *, core_identity_id: str,
        allow_model_download: bool = False,
        keep_model_warm: bool = False, playback_device: int | str | None = None,
        playback: Callable | None = None, model_factory: Callable | None = None,
    ) -> None:
        if not core_identity_id or not isinstance(core_identity_id, str):
            raise ValueError("a bound Core identity is required")
        self._profile_dir = Path(profile_dir).expanduser()
        self._core_id = core_identity_id
        self._allow_download = bool(allow_model_download)
        self._keep_warm = bool(keep_model_warm)
        self._device = playback_device
        self._playback = playback or _play_device
        self._factory = model_factory
        self._model = None
        self._prompt = None
        self._model_key = None
        self._lock = RLock()

    def _profile(self) -> InstalledVoiceProfile:
        return load_voice_profile(self._profile_dir, expected_core_identity_id=self._core_id)

    def probe(self, *, voice_hint: str | None = None) -> TTSBackendProbe:
        try:
            profile = self._profile()
            if voice_hint is not None and voice_hint.strip() not in ("", VOICE_PROFILE_ID):
                raise ValueError("requested voice differs from installed Bluehour profile")
            # Test dependencies and output only, without loading a GPU model.
            if self._factory is None:
                absent = [name for name in ("torch", "qwen_tts", "sounddevice", "numpy", "torchaudio")
                          if find_spec(name) is None]
                if absent:
                    raise RuntimeError("missing optional voice dependencies: " + ", ".join(absent))
                import torch
                if not torch.cuda.is_available():
                    raise RuntimeError("Qwen local voice requires an available CUDA GPU")
                if not self._allow_download:
                    from huggingface_hub import snapshot_download
                    snapshot_download(repo_id=MODEL_ID, local_files_only=True)
                import sounddevice as sd
                sd.query_devices(self._device, "output")
            return TTSBackendProbe(
                backend_name=self.name, available=True, healthy=True,
                voices=(profile.profile_id,), selected_voice=profile.profile_id,
                supported_controls=("rate", "volume", "delivery:bite"),
                reason="Local reference/dependencies checked; actual GPU generation and device playback unverified",
            )
        except Exception as exc:
            return TTSBackendProbe(
                backend_name=self.name, available=False, healthy=False,
                reason=f"{type(exc).__name__}: {exc}",
            )

    def _ensure_model(self, profile: InstalledVoiceProfile) -> None:
        key = (profile.wav_sha256, profile.reference_text)
        if self._model is not None and self._model_key == key:
            return
        self.unload()
        if self._factory is not None:
            model = self._factory()
        else:
            import torch
            from huggingface_hub import snapshot_download
            from qwen_tts import Qwen3TTSModel
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA GPU not available")
            available, _total = torch.cuda.mem_get_info(0)
            if available < 5 * 1024**3:
                raise RuntimeError("less than 5 GiB free VRAM, refusing neural voice load")
            source = (MODEL_ID if self._allow_download
                      else snapshot_download(repo_id=MODEL_ID, local_files_only=True))
            model = Qwen3TTSModel.from_pretrained(
                source, device_map="cuda:0", dtype=torch.bfloat16,
                attn_implementation="sdpa",
            )
        try:
            prompt = model.create_voice_clone_prompt(
                ref_audio=str(profile.wav_path), ref_text=profile.reference_text,
                x_vector_only_mode=False,
            )
        except Exception:
            del model
            raise
        self._model, self._prompt, self._model_key = model, prompt, key

    def unload(self) -> None:
        """Release model on idle by default to avoid occupying Venus VRAM."""
        with self._lock:
            self._prompt = None
            self._model = None
            self._model_key = None
            gc.collect()
            if self._factory is None and find_spec("torch") is not None:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

    def speak(
        self, *, utterance_id: str, text: str, profile: VoiceProsodyProfile,
        voice_hint: str | None = None, cancel: Event | None = None,
    ) -> TTSPlaybackReceipt:
        if not isinstance(profile, VoiceProsodyProfile):
            raise TypeError("VoiceProsodyProfile required")
        installed = self._profile()   # Rehash the actual WAV before every use.
        if voice_hint is not None and voice_hint.strip() not in ("", installed.profile_id):
            raise PermissionError("voice hint is not the approved profile")
        if cancel is not None and cancel.is_set():
            return self._cancelled(utterance_id)
        with self._lock:
            try:
                self._ensure_model(installed)
                if cancel is not None and cancel.is_set():
                    return self._cancelled(utterance_id)
                if self._factory is None:
                    import torch
                    with torch.inference_mode():
                        chunks, rate = self._model.generate_voice_clone(
                            text=text, language="English", voice_clone_prompt=self._prompt,
                        )
                else:
                    chunks, rate = self._model.generate_voice_clone(
                        text=text, language="English", voice_clone_prompt=self._prompt,
                    )
                if not chunks:
                    raise RuntimeError("Qwen returned no speech")
                audio, controls = _shape_audio(chunks[0], rate, profile)
            finally:
                if not self._keep_warm:
                    self.unload()
        if cancel is not None and cancel.is_set():
            return self._cancelled(utterance_id)
        finished = self._playback(audio, rate, cancel, self._device)
        if not finished:
            return self._cancelled(utterance_id)
        return TTSPlaybackReceipt(
            utterance_id=utterance_id, state=TTSPlaybackState.SPOKEN,
            backend_name=self.name, voice_name=installed.profile_id,
            applied_controls=controls,
        )

    def _cancelled(self, utterance_id: str) -> TTSPlaybackReceipt:
        return TTSPlaybackReceipt(
            utterance_id=utterance_id, state=TTSPlaybackState.CANCELLED,
            backend_name=self.name, voice_name=VOICE_PROFILE_ID,
            error="voice playback cancelled by output policy/STOP",
        )
