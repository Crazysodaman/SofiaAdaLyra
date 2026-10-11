"""SAFE permission state cannot independently resurrect canonical state.

Source regressions only. Execute in the final user-approved test campaign.
"""
import pytest

from sofia.safe.permissions import PermissionStore
from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite


def test_permission_store_requires_a_real_canonical_database(tmp_path):
    path = tmp_path / "unmounted" / "sofia.db"
    with pytest.raises(FileNotFoundError):
        PermissionStore(path)
    assert not path.exists()
    assert not path.parent.exists()


def test_grant_reads_cannot_recreate_a_deleted_state_file(tmp_path):
    path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = PermissionStore(path)
    assert store.grants() == ()
    path.unlink()
    with pytest.raises(FileNotFoundError):
        store.grants()
    with pytest.raises(FileNotFoundError):
        store.private_adult_authority()
    assert not path.exists()


def test_explicit_canonical_bootstrap_preserves_normal_permission_contract(tmp_path):
    path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = PermissionStore(path)
    assert store.private_adult_authority().adult_avatar is False
