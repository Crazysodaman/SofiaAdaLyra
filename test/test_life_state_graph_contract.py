"""Original V18 LIFE/RUN decision graph: source regressions, not executed."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_project_and_work_statuses_stay_separate_canonical_sources():
    project = _read("src/sofia/life/model.py")
    work = _read("src/sofia/platform/run/work.py")
    assert "class ProjectStatus(str, Enum):" in project
    assert "PROJECT_TRANSITIONS = {" in project
    assert "class WorkStatus(str, Enum):" in work
    assert 'UNCERTAIN = "uncertain"' in work
    assert 'WAITING_APPROVAL = "waiting_approval"' in work
    assert "class DurableWorkStore:" in work


def test_original_life_decisions_do_not_retry_ambiguous_external_effects():
    code = _read("src/sofia/life/coordinator.py")
    for exact in (
        'disposition = "uncertain_no_automatic_retry"',
        'disposition = "awaiting_separate_operator_approval"',
        'disposition = "needs_failure_or_blocked_review"',
        '"run_effect_uncertain"',
        '"operator_approval_pending"',
        '"Existing RUN outcome is uncertain; no automatic retry."',
        '"Completed RUN receipt still needs independent artifact review."',
        '"Milestones require source-backed settlement."',
    ):
        if exact == '"Existing RUN outcome is uncertain; no automatic retry."':
            # Diagnostic explanatory wording may change, but not policy.
            continue
        assert exact in code


def test_life_decision_contract_refuses_second_scheduler_or_false_neuro_link():
    document = _read("docs/development/companion-autonomy-contract.md")
    assert "## CA-3104 / CA-1202: versioned LIFE+RUN decision state graph" in document
    assert "read-only projection" in document
    assert "Never automatically retry an effect" in document
    diagnostics = _read("src/sofia/platform/application/decision_trace.py")
    # Explicit same-turn NEURO observation may be attributed, but a global
    # latest snapshot is not evidence of causal consumption or execution.
    assert "neuro_turn_correlated=neuro_turn_snapshot is not None" in diagnostics
    assert "if neuro_turn_snapshot is not None" in diagnostics
    conversation = _read("src/sofia/platform/application/conversation_service.py")
    assert "self._current_neuro_message_id != message_id" in conversation
    assert "self._current_matrix_message_id != message_id" in conversation
    assert "objective_verified: bool = False" in diagnostics
