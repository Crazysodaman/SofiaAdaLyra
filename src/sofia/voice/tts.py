"""Asynchronous text-to-speech service and engine-neutral contracts."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from queue import Empty, Full, Queue
from threading import Lock, Thread
from time import monotonic, sleep
from typing import Protocol
from uuid import uuid4

from .model import VoiceProsodyProfile


class TTSPlaybackState(str, Enum):
    QUEUED = "queued"
    SPOKEN = "spoken"
    FAILED = "failed"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class TTSBackendProbe:
    backend_name: str
    available: bool
    healthy: bool
    voices: tuple[str, ...] = ()
    selected_voice: str | None = None
    supported_controls: tuple[str, ...] = ()
    reason: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.backend_name, str) or not self.backend_name.strip():
            raise ValueError("backend_name must be nonempty")
        for name in ("available", "healthy"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be bool")
        if not isinstance(self.voices, tuple):
            raise TypeError("voices must be a tuple")
        if any(not isinstance(value, str) or not value.strip() for value in self.voices):
            raise ValueError("voices must contain nonempty strings")
        if self.selected_voice is not None and (
            not isinstance(self.selected_voice, str)
            or not self.selected_voice.strip()
        ):
            raise ValueError("selected_voice must be nonempty or None")
        if not isinstance(self.supported_controls, tuple):
            raise TypeError("supported_controls must be a tuple")
        if any(
            not isinstance(value, str) or not value.strip()
            for value in self.supported_controls
        ):
            raise ValueError("supported_controls must contain nonempty strings")
        if not isinstance(self.reason, str):
            raise TypeError("reason must be a string")


@dataclass(frozen=True, slots=True)
class TTSPlaybackReceipt:
    utterance_id: str
    state: TTSPlaybackState
    backend_name: str
    voice_name: str | None = None
    applied_controls: tuple[str, ...] = ()
    error: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.utterance_id, str) or not self.utterance_id.strip():
            raise ValueError("utterance_id must be nonempty")
        if not isinstance(self.state, TTSPlaybackState):
            raise TypeError("state must be TTSPlaybackState")
        if not isinstance(self.backend_name, str) or not self.backend_name.strip():
            raise ValueError("backend_name must be nonempty")


@dataclass(frozen=True, slots=True)
class TTSStatus:
    enabled: bool
    started: bool
    backend_name: str
    available: bool | None
    healthy: bool | None
    selected_voice: str | None
    voices: tuple[str, ...]
    supported_controls: tuple[str, ...]
    reason: str
    evidence_ref: str

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool or type(self.started) is not bool:
            raise TypeError("enabled and started must be bool")
        if not isinstance(self.backend_name, str) or not self.backend_name.strip():
            raise ValueError("backend_name must be nonempty")
        for name in ("available", "healthy"):
            value = getattr(self, name)
            if value is not None and type(value) is not bool:
                raise TypeError(f"{name} must be bool or None")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be nonempty")
        if not isinstance(self.evidence_ref, str) or not self.evidence_ref.strip():
            raise ValueError("evidence_ref must be nonempty")

    def prompt(self) -> str:
        def shown(value: bool | None) -> str:
            return "unknown" if value is None else ("yes" if value else "no")

        return "\n".join((
            "TRUSTED VOICE RUNTIME EVIDENCE",
            (
                "This is host-owned TTS runtime state. It does not prove "
                "microphone or STT state."
            ),
            f"TTS enabled: {'yes' if self.enabled else 'no'}",
            f"TTS service started: {'yes' if self.started else 'no'}",
            f"TTS backend: {self.backend_name}",
            f"TTS backend available: {shown(self.available)}",
            f"TTS backend healthy: {shown(self.healthy)}",
            f"Selected voice: {self.selected_voice or 'unknown'}",
            (
                "Supported prosody controls: "
                + (
                    ", ".join(self.supported_controls)
                    if self.supported_controls
                    else "none"
                )
            ),
            "Microphone/STT/listening state: not established by this evidence.",
            f"Evidence ref: {self.evidence_ref}",
        ))


@dataclass(frozen=True, slots=True)
class _Utterance:
    utterance_id: str
    text: str
    profile: VoiceProsodyProfile
    voice_hint: str | None


class TTSBackend(Protocol):
    name: str

    def probe(self, *, voice_hint: str | None = None) -> TTSBackendProbe: ...

    def speak(
        self,
        *,
        utterance_id: str,
        text: str,
        profile: VoiceProsodyProfile,
        voice_hint: str | None = None,
    ) -> TTSPlaybackReceipt: ...


def prepare_spoken_text(text: str) -> str:
    """Remove common Markdown noise while preserving natural sentence text."""
    import re

    if not isinstance(text, str):
        raise TypeError("text must be a string")
    value = text.strip()
    if not value:
        raise ValueError("text must not be blank")
    value = re.sub(
        r"```.*?```",
        " Code block omitted from speech. ",
        value,
        flags=re.DOTALL,
    )
    value = re.sub(
        r"\[([^\]]+)\]\([^\)]+\)",
        r"\1",
        value,
    )
    value = value.replace("`", "")
    value = value.replace("**", "").replace("__", "")
    value = value.replace("*", "").replace("_", "")
    value = " ".join(value.split())
    if not value:
        raise ValueError("text contains no speakable content")
    return value


class TextToSpeechService:
    """Non-blocking speech queue. Backend work never runs on the UI thread."""

    def __init__(
        self,
        backend: TTSBackend,
        *,
        enabled: bool = False,
        voice_hint: str | None = None,
        queue_size: int = 8,
    ) -> None:
        if not callable(getattr(backend, "probe", None)) or not callable(
            getattr(backend, "speak", None)
        ):
            raise TypeError("backend must implement probe() and speak()")
        if type(enabled) is not bool:
            raise TypeError("enabled must be bool")
        if voice_hint is not None and (
            not isinstance(voice_hint, str) or not voice_hint.strip()
        ):
            raise ValueError("voice_hint must be nonempty or None")
        if type(queue_size) is not int or queue_size < 1:
            raise ValueError("queue_size must be a positive int")
        self._backend = backend
        self._enabled = enabled
        self._voice_hint = None if voice_hint is None else voice_hint.strip()
        self._queue: Queue[_Utterance | None] = Queue(maxsize=queue_size)
        self._thread: Thread | None = None
        self._lock = Lock()
        self._probe: TTSBackendProbe | None = None
        self._last_receipt: TTSPlaybackReceipt | None = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def last_receipt(self) -> TTSPlaybackReceipt | None:
        with self._lock:
            return self._last_receipt

    def start(self) -> TTSStatus:
        if self._thread is not None:
            raise RuntimeError("TTS service already started")
        if not self._enabled:
            return self.status()

        probe = self._backend.probe(voice_hint=self._voice_hint)
        with self._lock:
            self._probe = probe
        if not probe.available or not probe.healthy:
            return self.status()

        self._thread = Thread(
            target=self._run,
            name="sofia-tts",
            daemon=True,
        )
        self._thread.start()
        return self.status()

    def status(self) -> TTSStatus:
        with self._lock:
            probe = self._probe
        if not self._enabled:
            return TTSStatus(
                enabled=False,
                started=False,
                backend_name=self._backend.name,
                available=None,
                healthy=None,
                selected_voice=None,
                voices=(),
                supported_controls=(),
                reason="TTS is disabled by runtime configuration",
                evidence_ref=f"voice:tts:{self._backend.name}:disabled",
            )
        if probe is None:
            return TTSStatus(
                enabled=True,
                started=False,
                backend_name=self._backend.name,
                available=None,
                healthy=None,
                selected_voice=None,
                voices=(),
                supported_controls=(),
                reason="TTS has not been probed yet",
                evidence_ref=f"voice:tts:{self._backend.name}:unprobed",
            )
        return TTSStatus(
            enabled=True,
            started=self._thread is not None and self._thread.is_alive(),
            backend_name=probe.backend_name,
            available=probe.available,
            healthy=probe.healthy,
            selected_voice=probe.selected_voice,
            voices=probe.voices,
            supported_controls=probe.supported_controls,
            reason=probe.reason or (
                "TTS backend is ready"
                if probe.healthy
                else "TTS backend is not healthy"
            ),
            evidence_ref=(
                f"voice:tts:{probe.backend_name}:"
                + ("ready" if probe.healthy else "unavailable")
            ),
        )

    def submit(
        self,
        text: str,
        *,
        profile: VoiceProsodyProfile | None = None,
    ) -> TTSPlaybackReceipt:
        spoken = prepare_spoken_text(text)
        profile = profile or VoiceProsodyProfile()
        if not isinstance(profile, VoiceProsodyProfile):
            raise TypeError("profile must be VoiceProsodyProfile")

        utterance_id = str(uuid4())
        status = self.status()
        if (
            not status.enabled
            or not status.started
            or status.available is not True
            or status.healthy is not True
        ):
            receipt = TTSPlaybackReceipt(
                utterance_id=utterance_id,
                state=TTSPlaybackState.REJECTED,
                backend_name=self._backend.name,
                voice_name=status.selected_voice,
                error=status.reason,
            )
            with self._lock:
                self._last_receipt = receipt
            return receipt

        try:
            self._queue.put_nowait(
                _Utterance(
                    utterance_id=utterance_id,
                    text=spoken,
                    profile=profile,
                    voice_hint=self._voice_hint,
                )
            )
        except Full:
            receipt = TTSPlaybackReceipt(
                utterance_id=utterance_id,
                state=TTSPlaybackState.REJECTED,
                backend_name=self._backend.name,
                voice_name=status.selected_voice,
                error="TTS queue is full",
            )
            with self._lock:
                self._last_receipt = receipt
            return receipt

        receipt = TTSPlaybackReceipt(
            utterance_id=utterance_id,
            state=TTSPlaybackState.QUEUED,
            backend_name=self._backend.name,
            voice_name=status.selected_voice,
        )
        with self._lock:
            self._last_receipt = receipt
        return receipt

    def wait_until_idle(self, *, timeout: float = 5.0) -> bool:
        if not isinstance(timeout, (int, float)) or timeout < 0:
            raise ValueError("timeout must be nonnegative")
        deadline = monotonic() + float(timeout)
        while monotonic() <= deadline:
            if self._queue.unfinished_tasks == 0:
                return True
            sleep(0.01)
        return self._queue.unfinished_tasks == 0

    def stop(
        self,
        *,
        cancel_pending: bool = True,
        timeout: float = 0.5,
    ) -> None:
        if cancel_pending:
            while True:
                try:
                    item = self._queue.get_nowait()
                except Empty:
                    break
                else:
                    self._queue.task_done()
                    if item is None:
                        break
        thread = self._thread
        if thread is None:
            return
        try:
            self._queue.put_nowait(None)
        except Full:
            pass
        thread.join(timeout=timeout)
        self._thread = None

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is None:
                    return
                try:
                    receipt = self._backend.speak(
                        utterance_id=item.utterance_id,
                        text=item.text,
                        profile=item.profile,
                        voice_hint=item.voice_hint,
                    )
                except Exception as exc:
                    receipt = TTSPlaybackReceipt(
                        utterance_id=item.utterance_id,
                        state=TTSPlaybackState.FAILED,
                        backend_name=self._backend.name,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                with self._lock:
                    self._last_receipt = receipt
            finally:
                self._queue.task_done()
