"""Headless startup selection: reuse owner-installed PUBLIC assets only."""
from pathlib import Path

from sofia.ui.avatar2d_installation import discover_public_avatar2d_root


def _pack(local: Path, name: str, *, character: bool = True) -> Path:
    root = local / "SofiaAdaLyra" / "Avatar2D" / name
    outfit = root / "outfits" / "day.default"
    outfit.mkdir(parents=True)
    (outfit / "manifest.json").write_text("{}", encoding="utf8")
    if character:
        head = root / "character"
        head.mkdir()
        (head / "manifest.json").write_text("{}", encoding="utf8")
    return root


def test_existing_public_v2_pack_is_found_without_environment_setting(tmp_path):
    original = _pack(tmp_path, "Public")
    preferred = _pack(tmp_path, "Public-V2")
    assert discover_public_avatar2d_root(None, local_app_data=str(tmp_path)) == preferred
    assert original.is_dir()


def test_explicit_owner_path_always_wins_even_if_absent(tmp_path):
    _pack(tmp_path, "Public-V2")
    explicit = tmp_path / "reviewed_custom_public_pack"
    assert discover_public_avatar2d_root(
        str(explicit), local_app_data=str(tmp_path)
    ) == explicit


def test_no_pack_does_not_create_any_files_or_guess_private_paths(tmp_path):
    assert discover_public_avatar2d_root(
        None, local_app_data=str(tmp_path)
    ) is None
    assert list(tmp_path.iterdir()) == []
    assert discover_public_avatar2d_root(None, local_app_data=None) is None


def test_incomplete_pack_is_skipped_in_favor_of_complete_public_install(tmp_path):
    _pack(tmp_path, "Public-V2", character=False)
    complete = _pack(tmp_path, "Public-All")
    assert discover_public_avatar2d_root(
        "", local_app_data=str(tmp_path)
    ) == complete


def test_discovery_rejects_linked_public_root(monkeypatch, tmp_path):
    _pack(tmp_path, "Public-V2")
    fallback = _pack(tmp_path, "Public")
    original_is_symlink = Path.is_symlink

    def detect_link(self):
        return self.name == "Public-V2" or original_is_symlink(self)

    monkeypatch.setattr(Path, "is_symlink", detect_link)
    assert discover_public_avatar2d_root(
        None, local_app_data=str(tmp_path)
    ) == fallback
