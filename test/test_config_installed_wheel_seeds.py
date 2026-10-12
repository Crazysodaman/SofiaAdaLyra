"""Source-to-installed-wheel first-install seed regression contracts.

Release acceptance still requires running these on the actual installed wheel.
"""
from pathlib import Path
import tomllib

import pytest

from sofia.config.layout import RuntimeStorageLayout
import sofia.config.layout as layout_module
from sofia.state.canonical_sqlite import require_existing_sqlite


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
    expected = Path(layout_module.__file__).resolve().parents[1]
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
