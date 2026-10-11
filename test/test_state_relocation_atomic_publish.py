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
