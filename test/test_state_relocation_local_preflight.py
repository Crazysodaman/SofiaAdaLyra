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


@pytest.mark.skipif(
    mobility.sys.platform != "linux",
    reason="Linux mountinfo filesystem classification only",
)
@pytest.mark.parametrize(
    "fstype, expected",
    (
        ("ext4", "local"),
        ("xfs", "local"),
        ("btrfs", "local"),
        ("tmpfs", "volatile"),
        ("ramfs", "volatile"),
        ("overlay", "volatile"),
        ("squashfs", "volatile"),
        ("nfs4", "remote"),
        ("cifs", "remote"),
        ("fuse.unverified", "unknown"),
    ),
)
def test_linux_mountinfo_requires_positive_durable_filesystem(
    tmp_path, monkeypatch, fstype, expected,
):
    mountinfo = (
        f"36 35 0:42 / / rw,relatime - {fstype} fixture rw\\n"
    )
    original = mobility.Path.read_text
    def synthetic_mountinfo(path, *args, **kwargs):
        if str(path) == "/proc/self/mountinfo":
            return mountinfo
        return original(path, *args, **kwargs)
    monkeypatch.setattr(mobility.Path, "read_text", synthetic_mountinfo)
    assert mobility._filesystem_kind(tmp_path / "state" / "sofia.db") == expected


@pytest.mark.skipif(
    mobility.sys.platform != "linux",
    reason="Linux volatile relocation denial only",
)
def test_linux_tmpfs_candidate_state_is_not_review_eligible(tmp_path, monkeypatch):
    source, dest = _paths(tmp_path)
    monkeypatch.setattr(mobility, "_filesystem_kind", lambda _path: "volatile")
    result = mobility.inspect_state_relocation(source, dest)
    assert not result.eligible_for_review
    assert "destination_filesystem_not_proven_local:volatile" in result.blockers
    assert result.ready_for_automatic_cutover is False
