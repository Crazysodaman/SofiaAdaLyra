"""Deferred production startup canonical-state identity contracts."""
from dataclasses import replace
import pytest

from sofia.composition.root import compose
from sofia.identity.model import IdentityBootstrapMode
from sofia.state.canonical_sqlite import CanonicalStateUnavailable
from test.test_memory_runtime_wiring import _configuration


def test_require_existing_refuses_missing_state_without_creating_it(tmp_path):
    cfg = replace(
        _configuration(tmp_path),
        identity_bootstrap_mode=IdentityBootstrapMode.REQUIRE_EXISTING,
    )
    assert not cfg.state_path.exists()
    with pytest.raises(CanonicalStateUnavailable, match="unavailable"):
        compose(cfg)
    assert not cfg.state_path.exists()
    assert not list(tmp_path.glob("sofia.db*"))


def test_require_existing_refuses_redirected_state_file(tmp_path):
    other = tmp_path / "other.db"
    other.touch()
    state = tmp_path / "sofia.db"
    try:
        state.symlink_to(other)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable on this host")
    cfg = replace(
        _configuration(tmp_path),
        identity_bootstrap_mode=IdentityBootstrapMode.REQUIRE_EXISTING,
    )
    with pytest.raises(CanonicalStateUnavailable, match="symbolic link"):
        compose(cfg)
    assert other.is_file()
    assert state.is_symlink()
