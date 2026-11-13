"""Exact-SHA CI must compile both native Rust desktops on Windows and Linux."""
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/aegis-rust-desktop.yml"


def test_desktop_workflow_builds_real_feature_gated_binaries_on_both_hosts():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "os: [ubuntu-24.04, windows-latest]" in source
    assert "EXPECTED_SOURCE_SHA" in source
    assert "--features desktop" in source
    for binary in ("aegis-control-center", "sofia-desktop"):
        assert f"--bin {binary}" in source
    assert "cargo clippy --locked" in source
    assert "cargo test --locked" in source
    assert "cargo build --locked" in source


def test_desktop_workflow_runs_without_core_or_display_claims():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "Test both desktop applications without a display server" in source
    assert "SOFIA_STATE_ROOT" not in source
    assert "ollama" not in source.lower()
    assert "xvfb" not in source.lower()


def test_full_release_gates_build_the_native_tui_before_binary_smoke_tests():
    root = WORKFLOW.parents[2]
    for relative in (
        ".github/actions/platform-only-checks/action.yml",
        ".github/workflows/manual-verify.yml",
        ".github/workflows/release-candidate.yml",
        ".github/workflows/debian-release-candidate.yml",
        ".github/workflows/package-tests.yml",
    ):
        source = (root / relative).read_text(encoding="utf-8")
        assert "cargo build --locked -p sofia-ui-broker --bin aegis_tui" in source
