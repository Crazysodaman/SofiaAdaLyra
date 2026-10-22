"""B06: internal dilemma resolution and anticipation/surprise ledger."""
from datetime import datetime, timedelta, timezone

import pytest

from sofia.agency import (
    AgencyService,
    AnticipationStore,
    ConcurrencyError,
    DilemmaStore,
    DilemmaStatus,
)
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.principals import local_sparks_principal
from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite

NOW = datetime(2026, 6, 10, 8, 15, tzinfo=timezone.utc)


def test_dilemmas_start_open_and_reconcile_with_evidence(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    dilemmas = DilemmaStore(tmp_path / "sofia.db")
    service = AgencyService(dilemmas, AnticipationStore(tmp_path / "sofia.db"))
    principal = local_sparks_principal()
    origin = service.record_dilemma(
        principal,
        question=(
            "Point out the owner's git mistake now, or wait for a natural "
            "pause in the session?"
        ),
        options=(
            "intervene now",
            "wait for a natural pause",
        ),
        reasoning=(
            "Interrupting risks breaking flow; waiting risks a wasted "
            "checkpoint. Restraint first, then decide with better evidence."
        ),
        evidence_refs=("conversation:turn-4",),
        audience_id="local:text",
        recorded_at=NOW,
    )
    assert origin.status is DilemmaStatus.OPEN
    assert origin.chosen is None
    assert dilemmas.current(origin.dilemma_id) == origin
    with pytest.raises(
        ValueError, match="resolved dilemmas choose an option",
    ):
        service.resolve_dilemma(
            principal,
            dilemma_id=origin.dilemma_id,
            expected_revision=origin.revision,
            chosen="delete the repo",
            reasoning="Out of impatience.",
            recorded_at=NOW + timedelta(hours=1),
        )
    with pytest.raises(ConcurrencyError, match="revision changed"):
        service.resolve_dilemma(
            principal,
            dilemma_id=origin.dilemma_id,
            expected_revision=9,
            chosen="wait for a natural pause",
            reasoning="The safer read of the owner's own guidance.",
            recorded_at=NOW + timedelta(hours=2),
        )
    resolved = service.resolve_dilemma(
        principal,
        dilemma_id=origin.dilemma_id,
        expected_revision=origin.revision,
        chosen="wait for a natural pause",
        reasoning="The safer read of the owner's own guidance.",
        evidence_refs=("conversation:turn-9",),
        recorded_at=NOW + timedelta(hours=2),
    )
    assert resolved.status is DilemmaStatus.RESOLVED
    assert resolved.revision == 2
    assert resolved.evidence_refs == ("conversation:turn-9",)
    assert [
        record.revision for record in dilemmas.history(origin.dilemma_id)
    ] == [1, 2]
    with pytest.raises(ConcurrencyError, match="revision changed"):
        service.resolve_dilemma(
            principal,
            dilemma_id=origin.dilemma_id,
            expected_revision=origin.revision,
            chosen="wait for a natural pause",
            reasoning="Stale CAS.",
            recorded_at=NOW + timedelta(hours=3),
        )
    assert service.dilemmas.open_dilemmas(audience_id="local:text") == ()


def test_dilemma_retirement_and_open_queries(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    service = AgencyService(
        DilemmaStore(tmp_path / "sofia.db"),
        AnticipationStore(tmp_path / "sofia.db"),
    )
    principal = local_sparks_principal()
    origin = service.record_dilemma(
        principal,
        question="Should the nightly journal summarization change its cadence?",
        options=("keep the cadence", "try a lighter cadence"),
        reasoning="The nightly cadence fits current evidence.",
        audience_id="local:text",
        recorded_at=NOW,
    )
    retired = service.retire_dilemma(
        principal,
        dilemma_id=origin.dilemma_id,
        expected_revision=origin.revision,
        reasoning="Not urgent anymore; reopen if the state changes.",
        recorded_at=NOW + timedelta(days=1),
    )
    assert retired.chosen is None
    assert retired.status is DilemmaStatus.RETIRED
    open_rows = service.dilemmas.open_dilemmas(audience_id="local:text")
    assert open_rows == ()
    open_origin = service.record_dilemma(
        principal,
        question="Do I claim unknown provenance or guard this turn silently?",
        options=("state unknown provenance", "hold the turn"),
        reasoning="Honesty wins even when the evidence gap is awkward.",
        audience_id="local:text",
        recorded_at=NOW + timedelta(days=1, seconds=1),
    )
    assert len(
        service.dilemmas.open_dilemmas(audience_id="local:text")
    ) == 1
    assert open_origin is not None
    with pytest.raises(LookupError):
        service.resolve_dilemma(
            principal,
            dilemma_id="dilemma:missing",
            expected_revision=1,
            chosen="state unknown provenance",
            reasoning="n/a",
        )


def test_anticipations_settle_and_surprise(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    anticipations = AnticipationStore(tmp_path / "sofia.db")
    service = AgencyService(
        DilemmaStore(tmp_path / "sofia.db"), anticipations,
    )
    principal = local_sparks_principal()
    pending = service.anticipate(
        principal,
        expectation="The owner will run pytest before the next checkpoint.",
        about="workflow",
        basis_refs=("goal:g-1", "habit.patterns"),
        audience_id="local:text",
        recorded_at=NOW,
    )
    assert anticipations.current(pending.anticipation_id) == pending
    assert len(anticipations.pending(audience_id="local:text")) == 1
    confirmed = service.settle(
        principal,
        anticipation_id=pending.anticipation_id,
        expected_revision=pending.revision,
        outcome_note="They ran the suite as expected.",
        recorded_at=NOW + timedelta(hours=1),
    )
    assert confirmed.status.value == "confirmed"
    assert confirmed.outcome_note == "They ran the suite as expected."
    with pytest.raises(
        ValueError, match="only pending anticipations can settle",
    ):
        service.settle(
            principal,
            anticipation_id=pending.anticipation_id,
            expected_revision=confirmed.revision,
            outcome_note="twice is impossible",
            recorded_at=NOW + timedelta(hours=2),
        )
    surprise = service.anticipate(
        principal,
        expectation="The lint review will stay calm this time.",
        about="person:sparks",
        audience_id="local:text",
        recorded_at=NOW + timedelta(hours=3),
    )
    settled = service.settle(
        principal,
        anticipation_id=surprise.anticipation_id,
        expected_revision=surprise.revision,
        outcome_note="not as expected: the argument flared up again.",
        recorded_at=NOW + timedelta(hours=4),
    )
    assert settled.status.value == "surprised"
    assert len(anticipations.recent_surprises(audience_id="local:text")) == 1
    with pytest.raises(LookupError):
        service.withdraw_anticipation(
            principal,
            anticipation_id="anticipation:missing",
            expected_revision=1,
        )
    withdrawn_pending = service.anticipate(
        principal,
        expectation="The build will finish before lunch.",
        about="ops",
        audience_id="local:text",
        recorded_at=NOW + timedelta(hours=5),
    )
    withdrawn = service.withdraw_anticipation(
        principal,
        anticipation_id=withdrawn_pending.anticipation_id,
        expected_revision=withdrawn_pending.revision,
        recorded_at=NOW + timedelta(hours=6),
    )
    assert withdrawn.status.value == "withdrawn"
    assert withdrawn.outcome_note is None


def test_agency_writes_are_owner_gated(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    service = AgencyService(
        DilemmaStore(tmp_path / "sofia.db"),
        AnticipationStore(tmp_path / "sofia.db"),
    )
    foreign = PrincipalContext(
        "person:other", "local:text", AudienceKind.PRIVATE, "Other"
    )
    with pytest.raises(PermissionError, match="authenticated Sparks principal"):
        service.record_dilemma(
            foreign,
            question="Who should close the milestone first?",
            options=("close it now", "close it later"),
            reasoning="Not their session.",
            audience_id="local:text",
        )
    with pytest.raises(PermissionError, match="authenticated Sparks principal"):
        service.anticipate(
            foreign,
            expectation="They will approve the checkpoint.",
            about="workflow",
            audience_id="local:text",
        )
    with pytest.raises(TypeError, match="PrincipalContext"):
        service.resolve_dilemma(
            "not-a-principal",  # type: ignore[arg-type]
            dilemma_id="dilemma:x",
            expected_revision=1,
            chosen="close it now",
            reasoning="n/a",
        )


def test_agency_store_reload_reads_the_same_current_rows(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    dilemmas = DilemmaStore(tmp_path / "sofia.db")
    anticipations = AnticipationStore(tmp_path / "sofia.db")
    service = AgencyService(dilemmas, anticipations)
    principal = local_sparks_principal()
    origin = service.record_dilemma(
        principal,
        question="Speak about the milestone risk directly or soften it?",
        options=("state it plainly", "soften the framing"),
        reasoning="Plain speech fits this audience.",
        audience_id="local:text",
        recorded_at=NOW,
    )
    pending = service.anticipate(
        principal,
        expectation="The fleet notice will go out today.",
        about="ops",
        audience_id="local:text",
        recorded_at=NOW,
    )
    reopened_dilemmas = DilemmaStore(tmp_path / "sofia.db")
    reopened_anticipations = AnticipationStore(tmp_path / "sofia.db")
    assert reopened_dilemmas.current(origin.dilemma_id) == origin
    assert (
        reopened_anticipations.current(pending.anticipation_id) == pending
    )
    resolved = service.resolve_dilemma(
        principal,
        dilemma_id=origin.dilemma_id,
        expected_revision=origin.revision,
        chosen="state it plainly",
        reasoning="The risk is concrete and the audience requested honesty.",
        recorded_at=NOW + timedelta(hours=1),
    )
    assert reopened_dilemmas.current(
        origin.dilemma_id,
    ) == resolved
    assert resolved.revision == 2
