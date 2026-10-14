"""Phase 00 all-65 audit and real bounded conversation retrieval regressions."""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sofia.application.conversation_service import (
    _MAX_SPECIFIC_RETRIEVAL_CHARACTERS, _retrieve_specific_conversation,
)
from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.verify.v18_phase00_full import all_phase00_snapshot, markdown_summary
from sofia.verify.v18_roadmap import RoadmapIntegrityError

pytestmark = pytest.mark.pkg_verify
ROOT = Path(__file__).resolve().parents[1]


def message(identity, content, role=ConversationRole.USER):
    return ConversationMessage(
        id=identity, session_id="session:owner",
        role=role, content=content,
        created_at=datetime(2026, 10, 14, tzinfo=timezone.utc),
    )


def test_all_65_phase00_tasks_have_authoritative_source_and_no_fabricated_gate():
    report = all_phase00_snapshot(ROOT)
    assert report["task_count"] == len(report["tasks"]) == 65
    assert len({row["id"] for row in report["tasks"]}) == 65
    assert sum(report["category_counts"].values()) == 65
    assert sum(report["ledger_status_counts"][name] for name in (
        "unassessed", "partial_wiring", "code_present_unverified", "accepted",
    )) == 65
    assert report["tasks_without_gate4"] + report["gate4_recorded"] == 65
    assert report["focused_tests_attested_by_source_report"] is False
    assert report["ci_result_attested_by_source_report"] is False
    assert report["venus_or_multi_host_acceptance_attested"] is False
    for row in report["tasks"]:
        assert row["static_paths_exist"] is True
        assert row["open_evidence"]
        assert row["requirement"].startswith("- [")
        assert row["production_accepted_in_canonical_ledger"] is (
            row["ledger_status"] == "accepted"
        )
        if row["ledger_status"] == "unassessed":
            assert not row["code_present_claimed"]
    summary = markdown_summary(report)
    assert "| CA-001 |" in summary
    assert "| CA-5408 |" in summary
    assert "not award" in summary


def test_wrong_revision_never_runs_phase00_audit():
    with pytest.raises(RoadmapIntegrityError, match="does not match"):
        all_phase00_snapshot(ROOT, expected_revision="0" * 40)


def test_source_audit_never_mutates_canonical_evidence():
    before = (ROOT / "docs/development/v18-task-evidence.json").read_bytes()
    all_phase00_snapshot(ROOT)
    assert (ROOT / "docs/development/v18-task-evidence.json").read_bytes() == before


def test_exact_retrieval_cap_for_first_large_message_without_mutating_source():
    original = message("long", "original phrase " + "a" * 50_000)
    found = _retrieve_specific_conversation(
        (original,), current_message_id="new", query="remember original phrase",
    )
    assert len(found) == 1
    assert found[0].id == original.id
    assert len(found[0].content) <= _MAX_SPECIFIC_RETRIEVAL_CHARACTERS
    assert found[0].content.endswith("[excerpt truncated]")
    assert len(original.content) > 50_000
    assert found[0] is not original


def test_exact_retrieval_multiple_messages_never_bypass_total_cap():
    values = (
        message("a", "needle " + "a" * 900),
        message("b", "needle " + "b" * 900),
        message("c", "needle " + "c" * 900),
        message("d", "needle " + "d" * 900),
    )
    found = _retrieve_specific_conversation(
        values, current_message_id="new", query="find needle",
    )
    assert sum(len(x.content) for x in found) <= _MAX_SPECIFIC_RETRIEVAL_CHARACTERS
    assert len(found) <= 4


def test_explicit_user_only_retrieval_cannot_import_assistant_content():
    values = (
        message("user", "needle " + "u" * 1800),
        message("assistant", "needle " + "a" * 5000, ConversationRole.ASSISTANT),
    )
    found = _retrieve_specific_conversation(
        values, current_message_id="new", query="what did I say about needle",
    )
    assert found and all(x.role is ConversationRole.USER for x in found)
    assert sum(len(x.content) for x in found) <= _MAX_SPECIFIC_RETRIEVAL_CHARACTERS


def test_topic_recall_without_any_source_overlap_abstains():
    prior = (
        message("prior-a", "Nothing about this observation mentions the target."),
        message("prior-b", "A separate unrelated owner conversation."),
    )
    result = _retrieve_specific_conversation(
        prior, current_message_id="new",
        query="What did I say about rare-unobserved-quartz?",
    )
    assert result == ()


def test_non_topical_recall_can_still_use_recent_bounded_source():
    prior = (message("prior-a", "I prefer carefully checked details."),)
    result = _retrieve_specific_conversation(
        prior, current_message_id="new", query="What did I say?",
    )
    assert len(result) == 1
    assert result[0].id == "prior-a"


@pytest.mark.parametrize(("context", "expected_output"), (
    (1, 1), (8, 2), (64, 21), (96, 32), (128, 42),
    (512, 170), (1024, 341),
))
def test_phase00_route_output_never_exceeds_configured_context(
    context, expected_output,
):
    from sofia.cognition.budgets import model_token_budget
    budget = model_token_budget(
        "verify", configured_context=context, configured_output=5000,
    )
    assert budget.context_tokens == context
    assert budget.output_tokens == expected_output
    assert 0 < budget.output_tokens <= budget.context_tokens


def test_all_unassessed_phase00_design_tasks_have_source_backed_review_candidates():
    report = all_phase00_snapshot(ROOT)
    unassessed = [
        row for row in report["tasks"]
        if row["ledger_status"] == "unassessed"
    ]
    assert len(unassessed) == report["candidate_unassessed_documents_verified"]
    assert len(unassessed) == 33
    assert all(row["candidate_not_independently_reviewed"] is True for row in unassessed)
    for row in unassessed:
        candidate = row["unassessed_design_review_candidate"]
        assert candidate.startswith("docs/development/")
        content = (ROOT / candidate).read_text(encoding="utf-8")
        assert row["id"] in content
        assert row["production_accepted_in_canonical_ledger"] is False
        assert row["code_present_claimed"] is False
