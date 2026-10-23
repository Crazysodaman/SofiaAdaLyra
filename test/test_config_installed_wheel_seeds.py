"""Source-to-installed-wheel first-install seed regression contracts.

Release acceptance still requires running these on the actual installed wheel.
"""
from dataclasses import replace
from pathlib import Path
import tomllib

import pytest

from sofia.platform.config.layout import RuntimeStorageLayout
from sofia.identity.model import IdentityBootstrapMode
import sofia.platform.config.layout as layout_module
from sofia.platform.state.canonical_sqlite import CanonicalStateUnavailable, require_existing_sqlite


def test_missing_checkout_layout_uses_imported_wheel_seeds(tmp_path, monkeypatch):
    """No guessed venv/lib/pythonX.Y/src/sofia path in installed releases."""
    monkeypatch.setenv("SOFIA_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.delenv("SOFIA_PROTECTED_ROOT", raising=False)
    monkeypatch.delenv("SOFIA_STATE_HOME_POINTER", raising=False)
    monkeypatch.delenv("SOFIA_STATE_HOME_POINTER_KEY", raising=False)
    monkeypatch.delenv("SOFIA_MIN_WRITER_EPOCH", raising=False)
    layout = RuntimeStorageLayout.from_environment(
        tmp_path / "fake-venv" / "lib" / "python3.13",
        mode_override="development",
    )
    # The imported-package seed root is the sofia package directory
    # (layout.py is nested two packages under sofia/ since the
    # platform restructure).
    expected = Path(layout_module.__file__).resolve().parents[2]
    assert layout.source_root == expected
    layout.provision_from_source()
    require_existing_sqlite(layout.state_path)
    for name, seed in (
        ("constitution.md", expected / "constitution" / "constitution.md"),
        ("constitution.sha256", expected / "constitution" / "constitution.sha256"),
        ("identity.json", expected / "identity" / "identity.json"),
        ("personality.json", expected / "personality" / "personality.json"),
        ("avatar.json", expected / "embodiment" / "avatar.json"),
    ):
        destination = (
            layout.protected_root / name
            if name in {"constitution.md", "constitution.sha256", "identity.json"}
            else layout.state_root / name
        )
        assert destination.read_bytes() == seed.read_bytes()


def test_incomplete_existing_checkout_cannot_fallback_to_installed_seeds(
    tmp_path, monkeypatch,
):
    checkout = tmp_path / "checkout"
    (checkout / "src" / "sofia").mkdir(parents=True)
    monkeypatch.setenv("SOFIA_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.delenv("SOFIA_PROTECTED_ROOT", raising=False)
    layout = RuntimeStorageLayout.from_environment(
        checkout, mode_override="development",
    )
    assert layout.source_root == checkout / "src" / "sofia"
    with pytest.raises(FileNotFoundError, match="runtime seed source does not exist"):
        layout.provision_from_source()
    assert not layout.state_path.exists()


def test_wheel_manifest_includes_every_first_install_seed():
    root = Path(__file__).resolve().parents[1]
    manifest = tomllib.loads(
        (root / "pyproject.toml").read_text(encoding="utf-8")
    )
    included = set(manifest["tool"]["setuptools"]["package-data"]["sofia"])
    assert {
        "constitution/constitution.md",
        "constitution/constitution.sha256",
        "identity/identity.json",
        "personality/personality.json",
        "embodiment/avatar.json",
    }.issubset(included)

def _existing_layout_after_bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv("SOFIA_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.delenv("SOFIA_PROTECTED_ROOT", raising=False)
    new = RuntimeStorageLayout.from_environment(
        Path(__file__).resolve().parents[1], mode_override="development",
    )
    new.provision_from_source()
    return replace(new, identity_bootstrap_mode=IdentityBootstrapMode.REQUIRE_EXISTING)


def test_live_restart_never_reseeds_lost_identity(tmp_path, monkeypatch):
    existing = _existing_layout_after_bootstrap(tmp_path, monkeypatch)
    existing.identity_path.unlink()
    with pytest.raises(CanonicalStateUnavailable, match="supervised restore"):
        existing.provision_from_source()
    assert not existing.identity_path.exists()
    assert existing.state_path.is_file()


def test_live_restart_never_reseeds_lost_personality(tmp_path, monkeypatch):
    existing = _existing_layout_after_bootstrap(tmp_path, monkeypatch)
    existing.personality_path.unlink()
    existing.provision_from_source()
    assert not existing.personality_path.exists()
    assert existing.identity_path.is_file()


def test_live_restart_rejects_redirected_identity(tmp_path, monkeypatch):
    existing = _existing_layout_after_bootstrap(tmp_path, monkeypatch)
    target = tmp_path / "saved-identity"
    existing.identity_path.replace(target)
    try:
        existing.identity_path.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable on this test host")
    with pytest.raises(CanonicalStateUnavailable, match="redirected"):
        existing.provision_from_source()
    assert target.is_file()
    assert existing.identity_path.is_symlink()
