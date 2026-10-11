"""CA-6807 read-only state-home preflight, regression cases deferred."""
from pathlib import Path

import pytest

import sofia.ops.state_mobility as mobility


def _paths(tmp_path):
    origin = tmp_path / "current"
    origin.mkdir()
    canonical = origin / "sofia.db"
    canonical.write_bytes(b"SQLite format 3\x00fixture")
    target = tmp_path / "approved-staging"
    return canonical, target


def test_reject_network_destination_without_attempting_any_relocation(
    tmp_path, monkeypatch,
):
    source, dest = _paths(tmp_path)
    monkeypatch.setattr(
        mobility, "_filesystem_kind",
        lambda path: "remote" if path == dest else "local",
    )
    proof = mobility.inspect_state_relocation(source, dest)
    assert proof.ready_for_automatic_cutover is False
    assert not proof.eligible_for_review
    assert "destination_filesystem_not_proven_local:remote" in proof.blockers
    assert not dest.exists()
    assert source.exists()


def test_reject_unverified_source_or_destination_media(tmp_path, monkeypatch):
    source, dest = _paths(tmp_path)
    monkeypatch.setattr(
        mobility, "_filesystem_kind",
        lambda path: "unknown" if path == source else "local",
    )
    proof = mobility.inspect_state_relocation(source, dest)
    assert "canonical_source_filesystem_not_proven_local:unknown" in proof.blockers


def test_reject_dotdot_path_even_if_it_resolves_to_existing_database(tmp_path):
    source, dest = _paths(tmp_path)
    equivalent = source.parent / "subdir" / ".." / "sofia.db"
    with pytest.raises(ValueError, match="cannot traverse parent"):
        mobility.inspect_state_relocation(equivalent, dest)


def test_host_local_preflight_still_cannot_promote_active_writer(tmp_path, monkeypatch):
    source, dest = _paths(tmp_path)
    monkeypatch.setattr(mobility, "_filesystem_kind", lambda path: "local")
    proof = mobility.inspect_state_relocation(source, dest)
    assert proof.ready_for_automatic_cutover is False
    assert source.exists() and not dest.exists()
