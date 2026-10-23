from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3


def evolved_preference_key(
    *,
    subject: str,
    semantic_id: str,
    region_id: str,
    context: str = "general",
) -> str:
    values = (subject, semantic_id, region_id, context)
    if subject not in ("user", "sofia"):
        raise ValueError("unknown interaction preference subject")
    for label, value in zip(
        ("subject", "semantic_id", "region_id", "context"),
        values,
    ):
        if (
            not isinstance(value, str)
            or not value.strip()
            or "/" in value
            or len(value) > 120
        ):
            raise ValueError(
                f"{label} must be a bounded slash-free canonical identifier"
            )
    return "/".join(values)


def parse_evolved_preference_key(
    key: str,
) -> tuple[str, str, str, str]:
    if not isinstance(key, str):
        raise TypeError("preference key must be text")
    parts = key.split("/")
    if len(parts) != 4:
        raise ValueError(
            "preference key must be subject/semantic_id/region_id/context"
        )
    subject, semantic_id, region_id, context = parts
    canonical = evolved_preference_key(
        subject=subject,
        semantic_id=semantic_id,
        region_id=region_id,
        context=context,
    )
    if canonical != key:
        raise ValueError("preference key is not canonical")
    return subject, semantic_id, region_id, context


def validate_evolved_preference_content(
    key: str,
    content: str,
) -> str | None:
    parse_evolved_preference_key(key)
    if not isinstance(content, str):
        raise TypeError("preference content must be text")
    try:
        document = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("reviewed preference must be JSON") from exc
    if not isinstance(document, dict) or set(document) != {"preference"}:
        raise ValueError(
            'reviewed preference must be exactly {"preference": ...}'
        )
    preference = document["preference"]
    if preference is None:
        return None
    if (
        not isinstance(preference, str)
        or not preference.strip()
        or len(preference) > 160
    ):
        raise ValueError(
            "preference must be null or bounded nonempty text"
        )
    return preference.strip()


def read_evolved_preference(
    path: str | Path,
    *,
    subject: str,
    semantic_id: str,
    region_id: str,
    context: str = "general",
) -> tuple[str | None, str] | None:
    """Read reviewed EVOLVE preference state without creating a schema."""
    state = Path(path)
    if not state.is_file():
        return None
    keys = []
    contexts = (context, "general") if context != "general" else ("general",)
    for ctx in contexts:
        for semantic, region in (
            (semantic_id, region_id),
            (semantic_id, "*"),
            ("*", region_id),
            ("*", "*"),
        ):
            keys.append(
                evolved_preference_key(
                    subject=subject,
                    semantic_id=semantic,
                    region_id=region,
                    context=ctx,
                )
            )

    with closing(sqlite3.connect(state, timeout=5)) as db:
        exists = db.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type='table' AND name='state_plane_record'
            """
        ).fetchone()
        if exists is None:
            return None
        for key in keys:
            row = db.execute(
                """
                SELECT value, source
                FROM state_plane_record
                WHERE namespace='evolve-preference'
                  AND record_key=?
                  AND principal_id=''
                  AND audience=''
                """,
                (key,),
            ).fetchone()
            if row is None:
                continue
            raw = bytes(row[0]).decode("utf-8")
            preference = validate_evolved_preference_content(key, raw)
            return preference, str(row[1])
    return None
