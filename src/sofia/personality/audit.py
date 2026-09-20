"""Read-only, content-free evidence for supervised Batch G idle-reflection checks.

Usage: python -m sofia.personality.audit
This does not start Sofía, create reflections, read out private text or send mail.
A completed attempt with no thought can be a valid model abstention.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from urllib.parse import quote


def _sqlite_uri_for_path(raw: str) -> str:
    """Build a no-create SQLite URI, including a Windows UNC pathname.

    An empty URI authority followed by //server/share keeps the network path
    in the path portion instead of treating 'server' as a forbidden URI host.
    """
    encoded = quote(raw, safe="/:")
    if raw.startswith("//"):
        return "file://" + encoded + "?mode=ro"
    if len(raw) >= 2 and raw[1] == ":":
        return "file:///" + encoded + "?mode=ro"
    return "file:" + encoded + "?mode=ro"


def reflection_audit(state_path: Path) -> dict[str, object]:
    """Report actual persisted rows, never infer idle thinking from prose.

    No database is created when the configured state does not exist. Missing
    schema is reported explicitly rather than pretending empty tables exist.
    """
    if not isinstance(state_path, Path):
        raise TypeError("The state path must be a Path.")
    if not state_path.is_file():
        return {"database": "missing", "idle_worker": "unknown",
                "model_thoughts": "unknown", "pending_unsent": "unknown"}
    uri = _sqlite_uri_for_path(state_path.absolute().as_posix())
    with sqlite3.connect(uri, uri=True, timeout=5) as db:
        db.execute("PRAGMA query_only = ON")
        tables = {row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        result: dict[str, object] = {"database": "present"}
        thoughts: set[str] | None = None
        if "reflection_thoughts" in tables:
            rows = db.execute(
                "SELECT thought_id, created_at FROM reflection_thoughts "
                "WHERE thought_id LIKE 'model-reflection:%'"
            ).fetchall()
            thoughts = {row[0] for row in rows}
            result["model_thoughts"] = len(rows)
            result["last_model_thought_at"] = max((row[1] for row in rows), default=None)
        else:
            result["model_thoughts"] = "unknown"
            result["last_model_thought_at"] = None
        if "idle_reflection_attempts" in tables:
            attempts = db.execute(
                "SELECT event_id, status, claimed_at, last_error_type "
                "FROM idle_reflection_attempts"
            ).fetchall()
            status = Counter(row[1] for row in attempts)
            result["idle_worker"] = "installed"
            result["idle_attempts"] = dict(sorted(status.items()))
            result["last_idle_attempt_at"] = max((row[2] for row in attempts), default=None)
            result["last_error_type"] = next((row[3] for row in sorted(
                attempts, key=lambda row: row[2], reverse=True
            ) if row[3] is not None), None)
            if thoughts is None:
                result["completed_with_model_thought"] = "unknown"
                result["completed_without_model_thought"] = "unknown"
            else:
                matched = sum(
                    f"model-reflection:{sha256(row[0].encode('utf-8')).hexdigest()[:32]}" in thoughts
                    for row in attempts if row[1] == "done"
                )
                result["completed_with_model_thought"] = matched
                result["completed_without_model_thought"] = status["done"] - matched
        else:
            result.update({"idle_worker": "not_installed", "idle_attempts": "unknown",
                           "last_idle_attempt_at": None, "last_error_type": None,
                           "completed_with_model_thought": "unknown",
                           "completed_without_model_thought": "unknown"})
        if "reflection_outbox" in tables:
            result["pending_unsent"] = db.execute(
                "SELECT COUNT(*) FROM reflection_outbox WHERE status='pending'"
            ).fetchone()[0]
        else:
            result["pending_unsent"] = "unknown"
    return result


def main() -> int:
    from sofia.config.defaults import create_default_configuration
    path = create_default_configuration().state_path
    try:
        result = reflection_audit(path)
    except (OSError, sqlite3.Error) as exc:
        # No raw file paths, SQL, or conversation content in diagnostics.
        print(json.dumps({"database": "unreadable", "error_type": type(exc).__name__}))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["database"] == "present" else 2


if __name__ == "__main__":
    raise SystemExit(main())
