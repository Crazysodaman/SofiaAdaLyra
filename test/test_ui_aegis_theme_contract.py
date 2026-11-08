"""Cross-surface Aegis theme contract tests; never import the personal Core UI."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / "contracts" / "ui" / "aegis-theme-v1.json"
DESIGN = ROOT / "docs" / "roadmaps" / "AEGIS_SHARED_GUI_TUI_THEME.md"
RUST = ROOT / "rust" / "crates" / "sofia-contracts" / "src" / "ui_theme.rs"


def _tokens_from_canonical_design() -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in DESIGN.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [part.strip().strip("`") for part in line.strip("|").split("|")]
        if len(cells) >= 4 and re.fullmatch(r"#[0-9A-F]{6}", cells[2]):
            rows[cells[1]] = cells[2]
    return rows


def test_shared_palette_matches_owner_approved_design_exactly() -> None:
    data = json.loads(THEME.read_text(encoding="utf-8"))
    assert set(data) == {"schema", "name", "tokens"}
    assert data["schema"] == "aegis.ui.theme.v1"
    assert data["name"] == "aegis-dark"
    assert data["tokens"] == _tokens_from_canonical_design()
    assert data["tokens"]["primary"] == "#9400D3"
    assert data["tokens"]["accent"] == "#00C2FF"
    assert data["tokens"]["tertiary"] == "#39FF14"
    assert data["tokens"]["surface_card"] == "#0B1020"


def test_rust_uses_one_bundled_palette_not_forked_colors() -> None:
    source = RUST.read_text(encoding="utf-8")
    assert 'include_str!("../../../../contracts/ui/aegis-theme-v1.json")' in source
    assert "pub fn bundled_theme()" in source
    assert "parse_strict(raw)" in source
