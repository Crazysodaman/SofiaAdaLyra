from datetime import datetime, timezone

from sofia.personality.reflection import RecordedThought
from sofia.personality.reflection_query import ReflectionQueryResolver


NOW = datetime(2026, 10, 3, 7, 0, tzinfo=timezone.utc)


def thought(identifier: str, content: str, minute: int) -> RecordedThought:
    return RecordedThought(
        thought_id=identifier,
        kind="observation",
        created_at=NOW.replace(minute=minute),
        subject="Observed workspace changes",
        content=content,
        evidence_refs=(f"evidence:{identifier}",),
        emotions=("curiosity",),
        period_key=None,
    )


def test_mind_query_without_recorded_reflection_refuses_invention():
    answer = ReflectionQueryResolver().resolve(
        "what's on your mind?",
        thoughts=(),
    )

    assert answer.recognized
    assert "don't have a recorded reflection" in answer.content
    assert "won't invent thoughts" in answer.content


def test_mind_query_reports_latest_recorded_reflection_conversationally():
    older = thought(
        "older",
        "Workspace comparison observed 2 added, 3 modified, and 1 removed paths. "
        "Cause, authorship, and significance are not established.",
        1,
    )
    newer = thought(
        "newer",
        "Workspace comparison observed 0 added, 5 modified, and 0 removed paths. "
        "Cause, authorship, and significance are not established.",
        2,
    )

    answer = ReflectionQueryResolver().resolve(
        "what have you been thinking about?",
        thoughts=(older, newer),
    )

    assert answer.recognized
    assert answer.content.startswith("Mostly the recent workspace changes.")
    assert "5 modified" in answer.content
    assert "who caused them" in answer.content
    assert "recorded 2026" not in answer.content
    assert older.content not in answer.content
    assert "dynamic scheduling matrix" not in answer.content.casefold()


def test_explicit_reflection_history_request_keeps_audit_detail():
    older = thought("older", "Older grounded thought.", 1)
    newer = thought("newer", "Newer grounded thought.", 2)

    answer = ReflectionQueryResolver().resolve(
        "list your recorded reflections",
        thoughts=(older, newer),
    )

    assert answer.recognized
    assert newer.content in answer.content
    assert older.content in answer.content
    assert "recorded 2026" in answer.content


def test_combined_mind_and_outfit_wording_is_recognized_as_mind_query():
    assert ReflectionQueryResolver.might_match(
        "Just wondering what's on your mind and what are you wearing"
    )
