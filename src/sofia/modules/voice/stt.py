"""Privacy-first push-to-talk speech input with typed host receipts."""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import closing
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import sqlite3
from threading import Event, Lock, Thread
from typing import Callable, Protocol
from uuid import uuid4


class SpeechInputState(str, Enum):
    DISABLED = "disabled"
    IDLE = "idle"
    LISTENING = "listening"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class SpeechInputProbe:
    backend_name: str
    available: bool
    healthy: bool
    devices: tuple[str, ...]
    selected_device: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class SpeechInputReceipt:
    capture_id: str
    state: SpeechInputState
    backend_name: str
    device_id: str | None
    transcript: str | None = None
    confidence: float | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if not self.capture_id.strip() or not self.backend_name.strip():
            raise ValueError("capture and backend identifiers are required")
        if self.transcript is not None and len(self.transcript) > 16_000:
            raise ValueError("speech transcript is too large")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in 0..1")


class SpeechInputBackend(Protocol):
    name: str
    def probe(self, *, device_id: str | None = None) -> SpeechInputProbe: ...
    def transcribe(
        self, *, capture_id: str, device_id: str | None,
        timeout_seconds: float, cancel: Event,
    ) -> SpeechInputReceipt: ...


_POWERSHELL_RECOGNIZE = r"""
Add-Type -AssemblyName System.Speech
$engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine
$engine.SetInputToDefaultAudioDevice()
$engine.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))
$result = $engine.Recognize([TimeSpan]::FromMilliseconds([int]$args[0]))
if ($null -eq $result) {
  @{ transcript = $null; confidence = $null; error = 'no_speech_recognized' } | ConvertTo-Json -Compress
} else {
  @{ transcript = $result.Text; confidence = [double]$result.Confidence; error = $null } | ConvertTo-Json -Compress
}
""".strip()


class WindowsSpeechRecognitionBackend:
    """Windows System.Speech one-shot recognizer using the default input."""

    name = "windows-system-speech"

    @staticmethod
    def _executable() -> str | None:
        return shutil.which("powershell.exe") or shutil.which("powershell")

    def probe(self, *, device_id: str | None = None) -> SpeechInputProbe:
        selected = device_id or "default"
        if selected != "default":
            return SpeechInputProbe(
                self.name, False, False, ("default",), selected,
                "System.Speech currently supports only the Windows default input",
            )
        executable = self._executable()
        available = sys.platform == "win32" and executable is not None
        return SpeechInputProbe(
            self.name, available, available, ("default",), selected,
            "Windows default microphone is selectable"
            if available else "Windows PowerShell/System.Speech is unavailable",
        )

    def transcribe(
        self, *, capture_id: str, device_id: str | None,
        timeout_seconds: float, cancel: Event,
    ) -> SpeechInputReceipt:
        probe = self.probe(device_id=device_id)
        if not probe.healthy:
            return SpeechInputReceipt(
                capture_id, SpeechInputState.REJECTED, self.name,
                probe.selected_device, error=probe.reason,
            )
        executable = self._executable()
        assert executable is not None
        milliseconds = max(1000, min(60_000, int(timeout_seconds * 1000)))
        environment = {
            key: os.environ[key]
            for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP")
            if key in os.environ
        }
        process = subprocess.Popen(
            (
                executable, "-NoLogo", "-NoProfile", "-NonInteractive",
                "-Command", _POWERSHELL_RECOGNIZE, str(milliseconds),
            ),
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL, env=environment,
            creationflags=(
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                if sys.platform == "win32" else 0
            ),
        )
        while process.poll() is None:
            if cancel.wait(0.05):
                process.kill()
                process.communicate()
                return SpeechInputReceipt(
                    capture_id, SpeechInputState.CANCELLED, self.name,
                    probe.selected_device, error="capture cancelled",
                )
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            return SpeechInputReceipt(
                capture_id, SpeechInputState.FAILED, self.name,
                probe.selected_device,
                error=(stderr.strip() or f"exit {process.returncode}")[-500:],
            )
        try:
            payload = json.loads(stdout[-16_000:])
            transcript = payload.get("transcript")
            confidence = payload.get("confidence")
            error = payload.get("error")
        except (json.JSONDecodeError, AttributeError) as exc:
            return SpeechInputReceipt(
                capture_id, SpeechInputState.FAILED, self.name,
                probe.selected_device, error=f"invalid recognizer output: {exc}",
            )
        if not isinstance(transcript, str) or not transcript.strip():
            return SpeechInputReceipt(
                capture_id, SpeechInputState.FAILED, self.name,
                probe.selected_device, error=str(error or "no speech recognized"),
            )
        return SpeechInputReceipt(
            capture_id, SpeechInputState.COMPLETED, self.name,
            probe.selected_device, transcript.strip(),
            None if confidence is None else float(confidence), None,
        )


class SpeechInputService:
    """One-shot input only; no ambient recording or model-side device access."""

    def __init__(
        self, backend: SpeechInputBackend, *, enabled: bool = False,
        muted: bool = False, device_id: str | None = None,
    ) -> None:
        if not callable(getattr(backend, "probe", None)) or not callable(
            getattr(backend, "transcribe", None)
        ):
            raise TypeError("speech input backend required")
        self.backend = backend
        self.enabled, self.muted = bool(enabled), bool(muted)
        self.device_id = device_id or "default"
        self._lock = Lock()
        self._thread: Thread | None = None
        self._cancel: Event | None = None
        self._last: SpeechInputReceipt | None = None

    @property
    def last_receipt(self) -> SpeechInputReceipt | None:
        with self._lock:
            return self._last

    def probe(self) -> SpeechInputProbe:
        return self.backend.probe(device_id=self.device_id)

    def listen(
        self, callback: Callable[[SpeechInputReceipt], None], *,
        timeout_seconds: float = 12.0,
    ) -> SpeechInputReceipt:
        if not callable(callback):
            raise TypeError("speech callback required")
        capture_id = str(uuid4())
        if not self.enabled or self.muted:
            receipt = SpeechInputReceipt(
                capture_id, SpeechInputState.REJECTED, self.backend.name,
                self.device_id,
                error="microphone input is disabled" if not self.enabled else "voice is muted",
            )
            with self._lock:
                self._last = receipt
            callback(receipt)
            return receipt
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("microphone capture is already active")
            cancel = Event()
            self._cancel = cancel
            listening = SpeechInputReceipt(
                capture_id, SpeechInputState.LISTENING, self.backend.name,
                self.device_id,
            )
            self._last = listening

            def run() -> None:
                try:
                    receipt = self.backend.transcribe(
                        capture_id=capture_id, device_id=self.device_id,
                        timeout_seconds=timeout_seconds, cancel=cancel,
                    )
                except Exception as exc:
                    receipt = SpeechInputReceipt(
                        capture_id, SpeechInputState.FAILED, self.backend.name,
                        self.device_id, error=f"{type(exc).__name__}: {exc}",
                    )
                with self._lock:
                    self._last = receipt
                    self._cancel = None
                    self._thread = None
                callback(receipt)

            thread = Thread(target=run, name="sofia-stt", daemon=True)
            self._thread = thread
        callback(listening)
        thread.start()
        return listening

    def cancel(self) -> bool:
        with self._lock:
            cancel = self._cancel
        if cancel is None:
            return False
        cancel.set()
        return True


class SpeechInputReceiptStore:
    """Content-minimal durable input diagnostics; transcripts stay in chat only."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        with closing(self._connect()) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS voice_input_receipt (
                    capture_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    backend_name TEXT NOT NULL,
                    device_id TEXT,
                    transcript_sha256 TEXT,
                    confidence REAL,
                    error TEXT,
                    occurred_at TEXT NOT NULL,
                    PRIMARY KEY(capture_id,state)
                )
            """)

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def record(self, receipt: SpeechInputReceipt, *, at: datetime | None = None) -> None:
        if not isinstance(receipt, SpeechInputReceipt):
            raise TypeError("SpeechInputReceipt required")
        moment = at or datetime.now(timezone.utc)
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("receipt timestamp must be timezone-aware")
        digest = (
            None if receipt.transcript is None
            else sha256(receipt.transcript.encode("utf-8")).hexdigest()
        )
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT OR IGNORE INTO voice_input_receipt VALUES(?,?,?,?,?,?,?,?)",
                (
                    receipt.capture_id, receipt.state.value, receipt.backend_name,
                    receipt.device_id, digest, receipt.confidence, receipt.error,
                    moment.astimezone(timezone.utc).isoformat(),
                ),
            )
