"""Owner-private, content-verified voice profile import for the Aegis Voice module.

No source WAV, reference transcript, biometric sample or owner-specific path is
stored in Git. Import is explicit, local, atomic and tied to reviewed Voice Lab
provenance. Profiles are not authority grants.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import shutil
import stat
import wave
from uuid import uuid4

PROFILE_FILENAME = "profile.json"
VOICE_PROFILE_ID = "voice:sofia:rook-bluehour-r9-medium"
VOICE_PROFILE_REVISION = 1
MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
_EXPECTED_WAV = "sofia_r9_bluehour_REFERENCE_AIR_medium.wav"
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}\Z")
_MAX_WAV_BYTES = 40 * 1024 * 1024


def file_sha256(path: Path) -> str:
    value = sha256()
    with path.open("rb") as reader:
        for block in iter(lambda: reader.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def validate_wav(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError("voice reference must be a regular WAV file, not a symlink")
    size = path.stat().st_size
    if size < 44 or size > _MAX_WAV_BYTES:
        raise ValueError("voice reference WAV is empty or unreasonably large")
    try:
        with wave.open(str(path), "rb") as reader:
            if reader.getnchannels() not in (1, 2):
                raise ValueError("voice reference must be mono/stereo PCM")
            if reader.getsampwidth() not in (2, 3, 4):
                raise ValueError("voice reference must be 16/24/32-bit PCM")
            if not 8_000 <= reader.getframerate() <= 192_000:
                raise ValueError("voice reference has unsupported sample rate")
            if reader.getnframes() < 1 or reader.getnframes() > reader.getframerate() * 120:
                raise ValueError("voice reference must contain 0-120 seconds of audio")
            if size < 44 + reader.getnframes() * reader.getnchannels() * reader.getsampwidth():
                raise ValueError("voice reference WAV is truncated")
    except (OSError, EOFError, wave.Error) as exc:
        raise ValueError("voice reference WAV cannot be decoded") from exc


def _json_file(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 128_000:
        raise ValueError(f"missing, unsafe, or oversized metadata: {path.name}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError, OSError) as exc:
        raise ValueError(f"invalid JSON metadata: {path.name}") from exc
    if not isinstance(data, dict):
        raise ValueError("voice metadata must be a JSON object")
    return data


@dataclass(frozen=True, slots=True)
class InstalledVoiceProfile:
    profile_id: str
    revision: int
    core_identity_id: str
    model_id: str
    wav_path: Path
    wav_sha256: str
    reference_text: str
    source_sha256: str

    def verify(self) -> None:
        if self.profile_id != VOICE_PROFILE_ID or self.revision != VOICE_PROFILE_REVISION:
            raise ValueError("unknown voice profile/revision")
        if self.model_id != MODEL_ID:
            raise ValueError("unexpected voice model")
        if _SAFE_ID.fullmatch(self.core_identity_id) is None:
            raise ValueError("invalid bound Core identity")
        if not isinstance(self.reference_text, str) or not self.reference_text.strip() or len(self.reference_text) > 4000:
            raise ValueError("actual reference transcript is required")
        for digest in (self.wav_sha256, self.source_sha256):
            if not isinstance(digest, str) or re.fullmatch(r"[a-f0-9]{64}", digest) is None:
                raise ValueError("invalid reference audio hash")
        validate_wav(self.wav_path)
        if file_sha256(self.wav_path) != self.wav_sha256:
            raise ValueError("voice reference was modified after installation")


def load_voice_profile(directory: Path | str, *, expected_core_identity_id: str | None = None) -> InstalledVoiceProfile:
    folder = Path(directory).expanduser()
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("installed voice profile directory is missing or unsafe")
    record = _json_file(folder / PROFILE_FILENAME)
    if set(record) != {"schema", "profile_id", "revision", "core_identity_id", "model_id",
                       "wav_filename", "wav_sha256", "source_sha256", "reference_text"}:
        raise ValueError("installed voice profile has missing or extra fields")
    if record["schema"] != "aegis.voice.profile.v1":
        raise ValueError("unsupported profile schema")
    if record["wav_filename"] != _EXPECTED_WAV:
        raise ValueError("unexpected voice reference filename")
    if type(record["revision"]) is not int:
        raise ValueError("voice revision must be an integer")
    if expected_core_identity_id is not None and record["core_identity_id"] != expected_core_identity_id:
        raise PermissionError("voice reference is bound to a different Core")
    profile = InstalledVoiceProfile(
        profile_id=record["profile_id"], revision=record["revision"],
        core_identity_id=record["core_identity_id"], model_id=record["model_id"],
        wav_path=folder / _EXPECTED_WAV, wav_sha256=record["wav_sha256"],
        reference_text=record["reference_text"], source_sha256=record["source_sha256"],
    )
    profile.verify()
    return profile


def import_round9_medium(
    round9_wav: Path | str, round6_metadata: Path | str, destination: Path | str,
    *, core_identity_id: str,
) -> InstalledVoiceProfile:
    """Import the *exact* owner-selected R9 Medium WAV, not a generated stand-in.

    The matching Round 9 JSON proves source/proc provenance and Round 6 JSON
    supplies the original accurate reference transcript. Never auto-download a
    personal voice sample and never silently replace an installed profile.
    """
    wav = Path(round9_wav).expanduser()
    round6_meta = Path(round6_metadata).expanduser()
    target = Path(destination).expanduser()
    if wav.name != _EXPECTED_WAV:
        raise ValueError(f"expected the approved {_EXPECTED_WAV}")
    if _SAFE_ID.fullmatch(core_identity_id) is None:
        raise ValueError("invalid canonical Core identity")
    validate_wav(wav)
    r9 = _json_file(wav.with_suffix(".json"))
    r6 = _json_file(round6_meta)
    actual_sha = file_sha256(wav)
    if (r9.get("round") != 9 or r9.get("level") != "medium"
            or r9.get("filter") != "voiced-upper-air-softmask-v1"
            or r9.get("audio_sha256") != actual_sha):
        raise ValueError("Round 9 Medium metadata and audio digest do not match")
    if (r6.get("round") != 6 or r6.get("variant") != "03_rook_bluehour"
            or r9.get("source_sha256") != r6.get("audio_sha256")):
        raise ValueError("Round 9 reference does not match original Round 6 Bluehour")
    # Require the actual original Round 6 bytes as provenance, not metadata alone.
    original_wav = round6_meta.with_suffix(".wav")
    if original_wav.name != "sofia_03_rook_bluehour.wav":
        raise ValueError("unexpected original Round 6 reference name")
    validate_wav(original_wav)
    if file_sha256(original_wav) != r6.get("audio_sha256"):
        raise ValueError("original Round 6 WAV digest does not match metadata")
    ref_text = r6.get("text")
    if not isinstance(ref_text, str) or not ref_text.strip() or len(ref_text) > 4000:
        raise ValueError("original Round 6 transcript is required")
    if target.is_symlink() or target.exists():
        raise FileExistsError("voice profile destination already exists; never overwrite owner voice assets")
    if target.parent.is_symlink():
        raise ValueError("voice profile parent must not be a symlink")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(f".{target.name}.import-{uuid4().hex}")
    record = {
        "schema": "aegis.voice.profile.v1", "profile_id": VOICE_PROFILE_ID,
        "revision": VOICE_PROFILE_REVISION, "core_identity_id": core_identity_id,
        "model_id": MODEL_ID, "wav_filename": _EXPECTED_WAV,
        "wav_sha256": actual_sha, "source_sha256": r9["source_sha256"],
        "reference_text": ref_text,
    }
    try:
        staging.mkdir(mode=0o700)
        copied = staging / _EXPECTED_WAV
        with wav.open("rb") as source, copied.open("xb") as out:
            shutil.copyfileobj(source, out, length=1024 * 1024)
        if file_sha256(copied) != actual_sha:
            raise RuntimeError("voice reference changed during copy")
        (staging / PROFILE_FILENAME).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        os.chmod(staging / PROFILE_FILENAME, stat.S_IRUSR | stat.S_IWUSR)
        os.chmod(copied, stat.S_IRUSR | stat.S_IWUSR)
        staging.rename(target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return load_voice_profile(target, expected_core_identity_id=core_identity_id)
