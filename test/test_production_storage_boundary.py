from pathlib import Path

from sofia.config import create_production_configuration
from sofia.config.layout import RuntimeStorageLayout
from sofia.identity.model import IdentityBootstrapMode
import sofia.config.layout as layout_module


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "src" / "sofia"


def _source_files():
    return tuple(sorted(SOURCE_ROOT.rglob("*.py")))


def test_source_does_not_use_development_configuration_outside_config():
    allowed = {
        SOURCE_ROOT / "config" / "__init__.py",
        SOURCE_ROOT / "config" / "defaults.py",
    }
    offenders = []
    for path in _source_files():
        if path in allowed:
            continue
        text = path.read_text(encoding="utf-8-sig")
        if "create_default_configuration" in text:
            offenders.append(path.relative_to(ROOT).as_posix())

    assert offenders == [], (
        "Live/source modules must use create_production_configuration "
        f"instead of development defaults: {offenders}"
    )


def test_source_does_not_hardcode_repository_state_directory():
    allowed = {
        SOURCE_ROOT / "config" / "layout.py",
    }
    patterns = (
        'parents[3] / "state"',
        "parents[3] / 'state'",
        'repository_root / "state"',
        "repository_root / 'state'",
    )
    offenders = []
    for path in _source_files():
        if path in allowed:
            continue
        text = path.read_text(encoding="utf-8-sig")
        if any(pattern in text for pattern in patterns):
            offenders.append(path.relative_to(ROOT).as_posix())

    assert offenders == [], (
        "Canonical runtime state must come from RuntimeStorageLayout: "
        f"{offenders}"
    )


def test_production_configuration_ignores_development_mode_flag(
    tmp_path,
    monkeypatch,
):
    state_root = tmp_path / "production-state"
    protected_root = tmp_path / "production-protected"
    monkeypatch.setenv("SOFIA_RUNTIME_MODE", "development")
    monkeypatch.setenv("SOFIA_STATE_ROOT", str(state_root))
    monkeypatch.setenv("SOFIA_PROTECTED_ROOT", str(protected_root))

    configuration = create_production_configuration()

    assert configuration.state_path == state_root / "sofia.db"
    assert (
        configuration.identity_bootstrap_mode
        is IdentityBootstrapMode.REQUIRE_EXISTING
    )


def test_windows_production_layout_defaults_to_programdata(
    tmp_path,
    monkeypatch,
):
    repository_root = tmp_path / "repo"
    program_data = tmp_path / "ProgramData"
    monkeypatch.delenv("SOFIA_STATE_ROOT", raising=False)
    monkeypatch.delenv("SOFIA_PROTECTED_ROOT", raising=False)
    monkeypatch.setenv("PROGRAMDATA", str(program_data))
    monkeypatch.setattr(layout_module.os, "name", "nt")

    layout = RuntimeStorageLayout.from_environment(
        repository_root,
        mode_override="production",
    )

    assert layout.mode == "production"
    assert layout.state_root == program_data / "SofiaAdaLyra"
    assert layout.state_path == program_data / "SofiaAdaLyra" / "sofia.db"
    assert layout.protected_root == (
        program_data / "SofiaAdaLyra" / "protected"
    )
    assert (
        layout.identity_bootstrap_mode
        is IdentityBootstrapMode.REQUIRE_EXISTING
    )
