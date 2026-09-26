"""No renderer, network, external account, real database or production memory."""

from copy import deepcopy
from datetime import datetime, timezone, timedelta
import pytest

from sofia.ui.workbench import (
    AccessDenied, ConflictError, EntryKind, EntryStatus, ItemKind,
    Workbench, WorkbenchError,
)


NOW = datetime(2026, 9, 21, 18, 0, tzinfo=timezone.utc)


def store():
    return Workbench("sparks", clock=lambda: NOW)


def binder(w):
    return w.create_item(actor_id="sparks", operation_id="create", item_id="gaia",
                         kind=ItemKind.BINDER, title="Gaia 2.0")


def idea(w, item_revision=1):
    return w.add_entry(actor_id="sparks", operation_id="thought-1", item_id="gaia",
                       expected_revision=item_revision, entry_id="servo-timing",
                       kind=EntryKind.IDEA, content="Check command timing",
                       source_ids=("reflection-42",))


@pytest.mark.parametrize("kind", list(ItemKind))
def test_all_cognitive_object_shapes_are_supported(kind):
    w = store()
    item = w.create_item(actor_id="sparks", operation_id="op", item_id="object",
                         kind=kind, title="An object")
    assert item.kind == kind
    assert item.owner_id == "sparks"
    assert not item.archived


@pytest.mark.parametrize("actor", ["other", "Sparks", "", None, 123])
def test_all_access_paths_deny_unmatched_actor(actor):
    w = store()
    with pytest.raises(AccessDenied):
        w.items(actor_id=actor)
    with pytest.raises(AccessDenied):
        w.create_item(actor_id=actor, operation_id="op", item_id="a",
                      kind=ItemKind.PAGE, title="private")
    assert w.items(actor_id="sparks") == ()


def test_private_thought_requires_provenance():
    w = store()
    binder(w)
    with pytest.raises(WorkbenchError, match="recorded source"):
        w.add_entry(
            actor_id="sparks", operation_id="missing-source", item_id="gaia",
            expected_revision=1, entry_id="thought", kind=EntryKind.REFLECTION,
            content="I might have an idea")
    assert w.entries(actor_id="sparks", item_id="gaia") == ()
    assert w.get_item(actor_id="sparks", item_id="gaia").revision == 1


def test_idea_is_a_candidate_not_a_fact_or_a_message():
    w = store()
    binder(w)
    entry = idea(w)
    assert entry.status == EntryStatus.CANDIDATE
    assert entry.source_ids == ("reflection-42",)
    assert w.get_item(actor_id="sparks", item_id="gaia").revision == 2


def test_revision_requires_cas_and_preserves_source_ids():
    w = store()
    binder(w)
    idea(w)
    with pytest.raises(ConflictError):
        w.revise_entry(actor_id="sparks", operation_id="edit", entry_id="servo-timing",
                       expected_entry_revision=1, expected_item_revision=1,
                       content="Check servo timing and power", source_ids=("reflection-42",))
    entry = w.revise_entry(actor_id="sparks", operation_id="edit", entry_id="servo-timing",
                           expected_entry_revision=1, expected_item_revision=2,
                           content="Check timing and power", source_ids=("reflection-42", "log-7"))
    assert entry.revision == 2
    assert entry.status == EntryStatus.CANDIDATE
    assert entry.source_ids == ("reflection-42", "log-7")


def test_review_is_explicit_and_does_not_claim_verified_truth():
    w = store()
    binder(w)
    idea(w)
    entry = w.set_status(actor_id="sparks", operation_id="review", entry_id="servo-timing",
                         expected_entry_revision=1, expected_item_revision=2,
                         status=EntryStatus.REVIEWED)
    assert entry.status == EntryStatus.REVIEWED
    with pytest.raises(WorkbenchError):
        w.set_status(actor_id="sparks", operation_id="review-again", entry_id="servo-timing",
                     expected_entry_revision=2, expected_item_revision=3,
                     status=EntryStatus.REJECTED)


@pytest.mark.parametrize("status", [EntryStatus.SUPERSEDED, EntryStatus.REJECTED])
def test_finalized_entry_cannot_be_edited(status):
    w = store()
    binder(w)
    idea(w)
    w.set_status(actor_id="sparks", operation_id="finalize", entry_id="servo-timing",
                 expected_entry_revision=1, expected_item_revision=2, status=status)
    with pytest.raises(WorkbenchError):
        w.revise_entry(actor_id="sparks", operation_id="edit", entry_id="servo-timing",
                       expected_entry_revision=2, expected_item_revision=3,
                       content="something", source_ids=("reflection-42",))


def test_archived_item_is_readable_but_not_editable():
    w = store()
    binder(w)
    assert w.archive_item(actor_id="sparks", operation_id="archive", item_id="gaia",
                          expected_revision=1).archived
    with pytest.raises(WorkbenchError):
        idea(w, item_revision=2)
    assert len(w.items(actor_id="sparks")) == 1


def test_replayed_operation_does_not_duplicate_or_change_item():
    w = store()
    binder(w)
    with pytest.raises(ConflictError, match="already applied"):
        w.create_item(actor_id="sparks", operation_id="create", item_id="other",
                      kind=ItemKind.BOOK, title="other")
    assert len(w.items(actor_id="sparks")) == 1


def test_duplicate_entry_id_rejected_even_across_items():
    w = store()
    binder(w)
    idea(w)
    w.create_item(actor_id="sparks", operation_id="second-item", item_id="homelab",
                  kind=ItemKind.NOTEBOOK, title="Homelab")
    with pytest.raises(ConflictError, match="entry ID"):
        w.add_entry(actor_id="sparks", operation_id="duplicate", item_id="homelab",
                    expected_revision=1, entry_id="servo-timing", kind=EntryKind.NOTE,
                    content="bad reuse")


def test_wrong_actor_cannot_guess_item_id_or_export_snapshot():
    w = store()
    binder(w)
    idea(w)
    with pytest.raises(AccessDenied):
        w.get_item(actor_id="someone-else", item_id="gaia")
    with pytest.raises(AccessDenied):
        w.entries(actor_id="someone-else", item_id="gaia")
    with pytest.raises(AccessDenied):
        w.snapshot(actor_id="someone-else")


def test_snapshot_round_trip_preserves_provenance_and_replay_defense():
    w = store()
    binder(w)
    idea(w)
    snapshot = w.snapshot(actor_id="sparks")
    recovered = Workbench.from_snapshot(snapshot, expected_owner_id="sparks", clock=lambda: NOW)
    assert recovered.snapshot(actor_id="sparks") == snapshot
    with pytest.raises(ConflictError, match="already applied"):
        recovered.add_entry(actor_id="sparks", operation_id="thought-1", item_id="gaia",
                            expected_revision=2, entry_id="other", kind=EntryKind.NOTE,
                            content="duplicate operation")


def test_snapshot_must_match_owner():
    w = store()
    binder(w)
    with pytest.raises(AccessDenied):
        Workbench.from_snapshot(w.snapshot(actor_id="sparks"), expected_owner_id="someone-else")


@pytest.mark.parametrize("mutation", [
    lambda s: s.update(schema=99),
    lambda s: s["items"].append(dict(s["items"][0])),
    lambda s: s["items"][0].update(owner_id="other"),
    lambda s: s["entries"][0].update(item_id="missing"),
    lambda s: s["entries"][0].update(source_ids=[]),
    lambda s: s["entries"][0].update(status="imaginary"),
    lambda s: s["operation_ids"].append(s["operation_ids"][0]),
    lambda s: s["items"][0].update(created_at="2026-09-21T18:00:00"),
])
def test_malformed_snapshots_fail_closed(mutation):
    w = store()
    binder(w)
    idea(w)
    snapshot = deepcopy(w.snapshot(actor_id="sparks"))
    mutation(snapshot)
    with pytest.raises((WorkbenchError, AccessDenied)):
        Workbench.from_snapshot(snapshot, expected_owner_id="sparks")


def test_untrusted_actor_or_bad_timestamp_cannot_create_item():
    w = Workbench("sparks", clock=lambda: datetime(2026, 9, 21))
    with pytest.raises(WorkbenchError, match="timezone-aware"):
        binder(w)
    assert w.items(actor_id="sparks") == ()


def test_source_ids_reject_duplicates_or_non_identifiers():
    w = store()
    binder(w)
    for source_ids in (("x", "x"), ("hi with spaces",), ("",)):
        with pytest.raises(WorkbenchError):
            w.add_entry(actor_id="sparks", operation_id="bad", item_id="gaia",
                        expected_revision=1, entry_id="idea", kind=EntryKind.IDEA,
                        content="something", source_ids=source_ids)


def test_read_only_snapshot_is_not_live_mutable_state():
    w = store()
    binder(w)
    data = w.snapshot(actor_id="sparks")
    data["items"][0]["title"] = "hacked"
    assert w.get_item(actor_id="sparks", item_id="gaia").title == "Gaia 2.0"


def test_forged_boolean_and_revision_validation():
    w = store()
    binder(w)
    with pytest.raises(ConflictError):
        idea(w, item_revision=True)
    snapshot = w.snapshot(actor_id="sparks")
    snapshot["items"][0]["archived"] = 1
    with pytest.raises(WorkbenchError):
        Workbench.from_snapshot(snapshot, expected_owner_id="sparks")


def test_time_backwards_disallowed_for_revision():
    now = [NOW]
    w = Workbench("sparks", clock=lambda: now[0])
    binder(w)
    idea(w)
    now[0] = NOW - timedelta(hours=1)
    with pytest.raises(WorkbenchError, match="backwards"):
        w.revise_entry(actor_id="sparks", operation_id="edit", entry_id="servo-timing",
                       expected_entry_revision=1, expected_item_revision=2,
                       content="revised", source_ids=("reflection-42",))


def test_unpresented_private_reflection_is_not_a_visible_page():
    w = store()
    binder(w)
    idea(w)
    assert w.presented_entries(actor_id="sparks", item_id="gaia") == ()
    with pytest.raises(ConflictError):
        w.present_entry(actor_id="sparks", operation_id="early", entry_id="servo-timing",
                        expected_entry_revision=1, expected_item_revision=2)
    w.set_status(actor_id="sparks", operation_id="review", entry_id="servo-timing",
                 expected_entry_revision=1, expected_item_revision=2,
                 status=EntryStatus.REVIEWED)
    visible = w.present_entry(actor_id="sparks", operation_id="show", entry_id="servo-timing",
                              expected_entry_revision=2, expected_item_revision=3)
    assert visible.presented
    assert w.presented_entries(actor_id="sparks", item_id="gaia") == (visible,)
    with pytest.raises(ConflictError):
        w.present_entry(actor_id="sparks", operation_id="show-again", entry_id="servo-timing",
                        expected_entry_revision=3, expected_item_revision=4)


def test_revising_reviewed_visible_entry_retracts_presentation():
    w = store()
    binder(w)
    idea(w)
    w.set_status(actor_id="sparks", operation_id="review", entry_id="servo-timing",
                 expected_entry_revision=1, expected_item_revision=2,
                 status=EntryStatus.REVIEWED)
    w.present_entry(actor_id="sparks", operation_id="show", entry_id="servo-timing",
                    expected_entry_revision=2, expected_item_revision=3)
    w.revise_entry(actor_id="sparks", operation_id="correct", entry_id="servo-timing",
                   expected_entry_revision=3, expected_item_revision=4,
                   content="This needs more evidence", source_ids=("reflection-42",))
    assert w.presented_entries(actor_id="sparks", item_id="gaia") == ()


def test_restore_rejects_unreviewed_entry_marked_presented():
    w = store()
    binder(w)
    idea(w)
    data = w.snapshot(actor_id="sparks")
    data["entries"][0]["presented"] = True
    with pytest.raises(WorkbenchError, match="reviewed"):
        Workbench.from_snapshot(data, expected_owner_id="sparks")
