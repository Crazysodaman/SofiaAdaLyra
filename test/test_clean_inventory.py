from pathlib import Path
import pytest
from sofia.clean import Disposition, inspect_candidates


def test_normal_regular_file_requires_review(tmp_path):
    (tmp_path / "module.py").write_text("x = 1")
    record, = inspect_candidates(tmp_path, ("module.py",))
    assert record.disposition is Disposition.REVIEW
    assert record.size_bytes == 5
    assert "deletion not established" in record.reason
    assert (tmp_path / "module.py").read_text() == "x = 1"


def test_nested_regular_file(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("ok")
    assert inspect_candidates(tmp_path, ("src/a.py",))[0].size_bytes == 2


@pytest.mark.parametrize("path", ["state/sofia.db", "state/notes.txt", "backups/a", ".git/config", ".env", ".env.local", "secrets/token", "credentials/txt", "src/sofia/constitution/current.py", "src/sofia/identity/name.py", "src/sofia/data/avatar.json", "src/sofia/data/anything", "SRC/SOFIA/IDENTITY/x", "foo/private.key", "foo/a.sqlite3", "foo/a.sqlite"])
def test_protected_candidates_never_inspected(tmp_path, path):
    record, = inspect_candidates(tmp_path, (path,))
    assert record.disposition is Disposition.PROTECTED
    assert record.size_bytes is None


@pytest.mark.parametrize("path", ["", "../outside", "src/../state/x", "/etc/passwd", "a//b", "a/./b", "a/", "C:/Windows/x", "a\\b", "a\x00b", "."])
def test_invalid_paths_fail_closed(tmp_path, path):
    assert inspect_candidates(tmp_path, (path,))[0].disposition is Disposition.UNKNOWN


def test_missing_is_not_dead_code(tmp_path):
    assert inspect_candidates(tmp_path, ("missing.py",))[0].disposition is Disposition.UNKNOWN


def test_directory_not_treated_as_candidate_file(tmp_path):
    (tmp_path / "dir").mkdir()
    assert inspect_candidates(tmp_path, ("dir",))[0].disposition is Disposition.UNKNOWN


def test_parent_file_not_traversed(tmp_path):
    (tmp_path / "file").write_text("x")
    assert inspect_candidates(tmp_path, ("file/nested",))[0].disposition is Disposition.UNKNOWN


def test_symlink_file_not_followed(tmp_path):
    target = tmp_path / "target.py"
    target.write_text("secret")
    (tmp_path / "link.py").symlink_to(target)
    assert inspect_candidates(tmp_path, ("link.py",))[0].disposition is Disposition.UNKNOWN


def test_symlink_parent_not_followed(tmp_path):
    actual = tmp_path / "real"
    actual.mkdir()
    (actual / "file.py").write_text("secret")
    (tmp_path / "shortcut").symlink_to(actual, target_is_directory=True)
    assert inspect_candidates(tmp_path, ("shortcut/file.py",))[0].disposition is Disposition.UNKNOWN


def test_root_symlink_rejected(tmp_path):
    actual = tmp_path / "real"
    actual.mkdir()
    (tmp_path / "alias").symlink_to(actual, target_is_directory=True)
    with pytest.raises(ValueError):
        inspect_candidates(tmp_path / "alias", ())


def test_missing_root_rejected(tmp_path):
    with pytest.raises(ValueError):
        inspect_candidates(tmp_path / "absent", ())


def test_requires_tuple_and_path_root(tmp_path):
    with pytest.raises(TypeError):
        inspect_candidates(str(tmp_path), ())
    with pytest.raises(TypeError):
        inspect_candidates(tmp_path, ["file"])


def test_multiple_candidates_preserve_order(tmp_path):
    (tmp_path / "ok.py").write_text("ok")
    records = inspect_candidates(tmp_path, ("missing", "ok.py", "state/secret"))
    assert tuple(record.disposition for record in records) == (Disposition.UNKNOWN, Disposition.REVIEW, Disposition.PROTECTED)


def test_no_write_or_delete_capability_exposed():
    from sofia import clean
    assert set(clean.__all__) == {"Disposition", "InventoryRecord", "inspect_candidates"}
