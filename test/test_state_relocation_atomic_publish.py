"""Deferred atomic absence-only state-home publication contracts.

No production writer, Hyper-V VM or protected state directory is touched.
"""
import sys

import pytest

from sofia.ops.state_relocation import _publish_new_home_without_replacing


@pytest.mark.skipif(
    not (sys.platform.startswith("linux") or sys.platform == "win32"),
    reason="unsupported platforms explicitly fail closed",
)
def test_publish_new_staging_home_uses_same_directory_and_preserves_assets(tmp_path):
    staging = tmp_path / ".sofia.restore-synthetic"
    destination = tmp_path / "sofia"
    staging.mkdir()
    (staging / "sofia.db").write_bytes(b"immutable-synthetic-state")
    protected = staging / "protected"
    protected.mkdir()
    (protected / "identity.json").write_bytes(b"owner-fixture")

    _publish_new_home_without_replacing(staging, destination)

    assert not staging.exists()
    assert (destination / "sofia.db").read_bytes() == b"immutable-synthetic-state"
    assert (destination / "protected" / "identity.json").read_bytes() == (
        b"owner-fixture"
    )


@pytest.mark.skipif(
    not (sys.platform.startswith("linux") or sys.platform == "win32"),
    reason="unsupported platforms explicitly fail closed",
)
def test_atomic_publish_never_overwrites_existing_owner_home(tmp_path):
    staging = tmp_path / ".sofia.restore-synthetic"
    staging.mkdir()
    (staging / "sofia.db").write_bytes(b"candidate")
    destination = tmp_path / "sofia"
    destination.mkdir()
    (destination / "operator-owned").write_bytes(b"must-survive")

    with pytest.raises(FileExistsError, match="already exists"):
        _publish_new_home_without_replacing(staging, destination)

    assert (destination / "operator-owned").read_bytes() == b"must-survive"
    assert (staging / "sofia.db").read_bytes() == b"candidate"


@pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="Linux RENAME_NOREPLACE race handling is platform-specific",
)
def test_linux_kernel_eexist_is_not_downgraded_to_replace(tmp_path, monkeypatch):
    import ctypes
    import errno

    staging = tmp_path / ".sofia.restore-synthetic"
    destination = tmp_path / "sofia"
    staging.mkdir()
    (staging / "sofia.db").write_bytes(b"candidate")

    def os_renameat2(src_dir, src, dest_dir, dst, flags):
        assert src_dir == -100
        assert dest_dir == -100
        assert flags == 1
        assert bytes(dst).decode() == str(destination)
        destination.mkdir()
        (destination / "operator-owned").write_bytes(b"must-survive")
        ctypes.set_errno(errno.EEXIST)
        return -1

    class FakeLibc:
        pass

    fake = FakeLibc()
    fake.renameat2 = os_renameat2
    monkeypatch.setattr(ctypes, "CDLL", lambda *_a, **_kw: fake)

    with pytest.raises(FileExistsError, match="atomic publication"):
        _publish_new_home_without_replacing(staging, destination)

    assert (destination / "operator-owned").read_bytes() == b"must-survive"
    assert (staging / "sofia.db").read_bytes() == b"candidate"


@pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="Linux directory fsync and /proc descriptor inspection are required",
)
def test_linux_publication_flushes_restored_tree_and_renamed_parent(tmp_path, monkeypatch):
    import os

    staging = tmp_path / ".sofia.restore-synthetic"
    destination = tmp_path / "sofia"
    (staging / "protected").mkdir(parents=True)
    (staging / "sofia.db").write_bytes(b"synthetic-database")
    (staging / "protected" / "identity.json").write_bytes(b"synthetic-identity")

    flushed = []
    original_fsync = os.fsync

    def record_flush(descriptor):
        flushed.append(os.readlink(f"/proc/self/fd/{descriptor}"))
        return original_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", record_flush)
    _publish_new_home_without_replacing(staging, destination)

    assert str(staging / "sofia.db") in flushed
    assert str(staging / "protected" / "identity.json") in flushed
    assert str(staging / "protected") in flushed
    assert str(staging) in flushed
    # At least one parent sync before rename, another after publication.
    assert flushed.count(str(tmp_path)) >= 2
    assert flushed.index(str(tmp_path)) < flushed.index(str(tmp_path), flushed.index(str(tmp_path)) + 1)
    assert not staging.exists()
    assert (destination / "protected" / "identity.json").read_bytes() == b"synthetic-identity"


@pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="Linux directory fsync behavior is required",
)
def test_linux_publication_refuses_pre_rename_fsync_failure(tmp_path, monkeypatch):
    import os

    staging = tmp_path / ".sofia.restore-synthetic"
    destination = tmp_path / "sofia"
    staging.mkdir()
    (staging / "sofia.db").write_bytes(b"synthetic-database")

    def unavailable_fsync(_descriptor):
        raise OSError("synthetic durable-write failure")

    monkeypatch.setattr(os, "fsync", unavailable_fsync)
    with pytest.raises(OSError, match="synthetic durable-write failure"):
        _publish_new_home_without_replacing(staging, destination)

    assert (staging / "sofia.db").read_bytes() == b"synthetic-database"
    assert not destination.exists()


@pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="Linux directory fsync behavior is required",
)
def test_linux_post_rename_fsync_failure_is_explicitly_uncertain(tmp_path, monkeypatch):
    import os

    from sofia.ops.state_relocation import StateHomePublicationUncertain

    staging = tmp_path / ".sofia.restore-synthetic"
    destination = tmp_path / "sofia"
    staging.mkdir()
    (staging / "sofia.db").write_bytes(b"synthetic-database")

    original_fsync = os.fsync
    parent_flushes = 0

    def fail_final_parent_flush(descriptor):
        nonlocal parent_flushes
        current = os.readlink(f"/proc/self/fd/{descriptor}")
        if current == str(tmp_path):
            parent_flushes += 1
            if parent_flushes == 2:
                raise OSError("synthetic parent sync failure")
        return original_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", fail_final_parent_flush)
    with pytest.raises(StateHomePublicationUncertain, match="do not activate"):
        _publish_new_home_without_replacing(staging, destination)

    assert parent_flushes == 2
    assert not staging.exists()
    assert (destination / "sofia.db").read_bytes() == b"synthetic-database"


@pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="Linux O_NOFOLLOW directory sync is required",
)
def test_linux_publication_rejects_symlink_inside_restored_tree(tmp_path):
    staging = tmp_path / ".sofia.restore-synthetic"
    destination = tmp_path / "sofia"
    foreign = tmp_path / "outside"
    foreign.mkdir()
    staging.mkdir()
    (staging / "sofia.db").write_bytes(b"synthetic-database")
    (staging / "substituted").symlink_to(foreign, target_is_directory=True)

    with pytest.raises(OSError):
        _publish_new_home_without_replacing(staging, destination)

    assert (staging / "sofia.db").exists()
    assert not destination.exists()
