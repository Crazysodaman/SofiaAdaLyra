"""Platform-local state must reject redirected parents even for the same inode."""
from contextlib import closing
from pathlib import Path
import os
import subprocess

import pytest

from sofia.platform.state.local_store import LocalStateUnavailable, PlatformLocalStore
from test.test_platform_module_host_local_state import MODULE_HOST_ROLES, local_store


def symlink_directory(link, target):
    try:
        link.symlink_to(target, target_is_directory=True)
    except PermissionError:
        pytest.skip("directory symlink privilege unavailable on this runner")


def test_existing_store_cannot_be_adopted_through_parent_symlink(tmp_path):
    store = local_store(tmp_path)
    alias = tmp_path / "alias"
    symlink_directory(alias, store.path.parent)
    with pytest.raises(LocalStateUnavailable, match="redirect"):
        PlatformLocalStore(
            alias / store.path.name, roles=MODULE_HOST_ROLES, host_identity="host:venus",
        )


def test_parent_redirection_after_open_refuses_same_file_identity(tmp_path):
    store = local_store(tmp_path)
    parent = store.path.parent
    moved = parent.with_name("relocated")
    parent.rename(moved)
    symlink_directory(parent, moved)
    with pytest.raises(LocalStateUnavailable, match="redirect"):
        with closing(store.connect()):
            pass


def test_existing_store_refuses_junction_parent(tmp_path, monkeypatch):
    store = local_store(tmp_path)
    parent = store.path.parent
    monkeypatch.setattr(Path, "is_junction", lambda path: path == parent)
    with pytest.raises(LocalStateUnavailable, match="redirect"):
        PlatformLocalStore(store.path, roles=MODULE_HOST_ROLES, host_identity="host:venus")


def test_live_store_refuses_junction_parent(tmp_path, monkeypatch):
    store = local_store(tmp_path)
    monkeypatch.setattr(Path, "is_junction", lambda path: path == store.path.parent)
    with pytest.raises(LocalStateUnavailable, match="redirect"):
        store.connect()


@pytest.mark.skipif(os.name != "nt", reason="native NTFS junction coverage requires Windows")
def test_native_windows_junction_cannot_adopt_existing_store(tmp_path):
    store = local_store(tmp_path)
    alias = tmp_path / "junction"
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(alias), str(store.path.parent)],
        capture_output=True, check=False,
    )
    if result.returncode:
        pytest.skip("runner could not create a native NTFS directory junction")
    try:
        assert alias.is_junction()
        with pytest.raises(LocalStateUnavailable, match="redirect"):
            PlatformLocalStore(
                alias / store.path.name, roles=MODULE_HOST_ROLES, host_identity="host:venus",
            )
    finally:
        alias.rmdir()
