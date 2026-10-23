"""Deferred production startup canonical-state identity contracts."""
from dataclasses import replace
import pytest

from sofia.platform.composition.root import compose
from sofia.identity.model import IdentityBootstrapMode
from sofia.platform.state.canonical_sqlite import CanonicalStateUnavailable
from test.test_memory_runtime_wiring import _configuration


def test_require_existing_refuses_missing_state_without_creating_it(tmp_path):
    cfg = replace(
        _configuration(tmp_path),
        identity_bootstrap_mode=IdentityBootstrapMode.REQUIRE_EXISTING,
    )
    # The shared configuration helper explicitly first-installs the fixture;
    # simulate actual state loss before testing REQUIRE_EXISTING preflight.
    cfg.state_path.unlink()
    assert not cfg.state_path.exists()
    with pytest.raises(CanonicalStateUnavailable, match="unavailable"):
        compose(cfg)
    assert not cfg.state_path.exists()
    assert not list(tmp_path.glob("sofia.db*"))


def test_require_existing_refuses_redirected_state_file(tmp_path):
    # Build the disposable real fixture first; then replace the state path
    # with the malicious redirected symlink. Canonical startup must refuse.
    cfg = replace(
        _configuration(tmp_path),
        identity_bootstrap_mode=IdentityBootstrapMode.REQUIRE_EXISTING,
    )
    cfg.state_path.unlink()
    other = tmp_path / "other.db"
    other.touch()
    state = cfg.state_path
    try:
        state.symlink_to(other)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable on this host")
    with pytest.raises(CanonicalStateUnavailable, match="symbolic link"):
        compose(cfg)
    assert other.is_file()
    assert state.is_symlink()
