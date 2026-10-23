"""Local-only, score-count MENTOR history. Not Sofia's canonical memory.

Stores no text, transcripts, prompt hashes, user IDs, emotion journal entries,
channels or exact conversation timestamps. Never within the public Git checkout.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from .personality_review import CRITERIA
from .behavior_monitor import EMOTION_CRITERIA  # imported at call time from monitor

SCHEMA = "sofia.core.mentor.behavior-aggregate.v1"
MAX_FILE_BYTES = 8_192


def default_local_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_STATE_HOME")
    if not base:
        base = str(Path.home() / ".local" / "state")
    return (Path(base) / "Sofia" / "mentor" / "behavior_scores.json").resolve()


def _validate_counts(value: object) -> dict:
    if (not isinstance(value, dict) or set(value) != {
        "schema", "reviewed_turns", "personality", "emotion"
    } or value.get("schema") != SCHEMA):
        raise ValueError("invalid local score history")
    n = value.get("reviewed_turns")
    if type(n) is not int or not 0 <= n <= 1_000_000:
        raise ValueError("invalid review count")
    for name, keys in (("personality", CRITERIA), ("emotion", EMOTION_CRITERIA)):
        cat = value.get(name)
        if not isinstance(cat, dict) or set(cat) != set(keys):
            raise ValueError("incomplete category counts")
        for row in cat.values():
            if not isinstance(row, dict) or set(row) != {"sum", "count"}:
                raise ValueError("unexpected count fields")
            if any(type(row[k]) is not int or row[k] < 0 for k in ("sum", "count")):
                raise ValueError("invalid count values")
            if row["count"] > n or row["sum"] > row["count"] * 4:
                raise ValueError("invalid score totals")
    return value


def empty_counts() -> dict:
    return {
        "schema": SCHEMA, "reviewed_turns": 0,
        "personality": {k: {"sum": 0, "count": 0} for k in CRITERIA},
        "emotion": {k: {"sum": 0, "count": 0} for k in EMOTION_CRITERIA},
    }


def read_counts(path: Path | str) -> dict:
    target = Path(path)
    if not target.exists():
        return empty_counts()
    if target.is_symlink() or not target.is_file() or target.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("unsafe local history file")
    try:
        doc = json.loads(target.read_text(encoding="utf-8"))
    except (ValueError, OSError, UnicodeDecodeError) as exc:
        raise ValueError("invalid local score-history JSON") from exc
    return _validate_counts(doc)


def merge_scores(counts: dict, personality: dict, emotion: dict) -> dict:
    _validate_counts(counts)
    if set(personality) != set(CRITERIA) or set(emotion) != set(EMOTION_CRITERIA):
        raise ValueError("incomplete reviewer dimensions")
    fresh = json.loads(json.dumps(counts))
    fresh["reviewed_turns"] += 1
    for family, scores in (("personality", personality), ("emotion", emotion)):
        for k, score in scores.items():
            if score is None and family == "emotion" and k == "expression_coherence":
                continue
            if type(score) is not int or not 0 <= score <= 4:
                raise ValueError("invalid local score")
            fresh[family][k]["sum"] += score
            fresh[family][k]["count"] += 1
    return _validate_counts(fresh)


def save_counts(path: Path | str, data: dict, *, repo: Path | str) -> None:
    """Atomic score-only file, explicitly outside the repository."""
    _validate_counts(data)
    root = Path(repo).resolve(strict=True)
    dest = Path(path).expanduser().absolute()
    if root == dest or root in dest.parents:
        raise ValueError("never store local behavior history under public Git")
    if dest.is_symlink() or dest.parent.is_symlink():
        raise ValueError("local history destination redirected")
    encoded = json.dumps(data, sort_keys=True, indent=2) + "\n"
    if len(encoded.encode("utf-8")) > MAX_FILE_BYTES:
        raise ValueError("local history exceeds size limit")
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tempname = tempfile.mkstemp(prefix=".behavior-", dir=str(dest.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.chmod(tempname, 0o600)
            stream.write(encoded)
        os.replace(tempname, dest)
    finally:
        if os.path.exists(tempname):
            os.unlink(tempname)


def public_free_summary(data: dict) -> dict:
    """Numeric-only convenience view, never automatically published."""
    source = _validate_counts(data)
    return {
        "schema": "sofia.core.mentor.behavior-summary.v1",
        "total_local_reviews": source["reviewed_turns"],
        "grades": {
            family: {
                k: (None if record["count"] == 0
                    else round(record["sum"] / record["count"], 2))
                for k, record in source[family].items()
            }
            for family in ("personality", "emotion")
        },
        "self_certified": False,
        "emotion_means_modelled_expression_not_felt_state": True,
        "voice_and_avatar_delivery_unverified": True,
        "local_only": True,
    }
