from pathlib import Path

from sofia.filesystem.inspector import FilesystemInspector
from sofia.filesystem.model import (
    FilesystemOperation,
    FilesystemResultKind,
)


def test_unauthorized_inspector_rejects_directory_listing(
    tmp_path: Path,
):
    inspector = FilesystemInspector(
        root=tmp_path,
        authorized=False,
    )

    result = inspector.list_directory()

    assert result.operation is FilesystemOperation.LIST_DIRECTORY
    assert result.kind is FilesystemResultKind.UNAUTHORIZED


def test_authorized_inspector_lists_directory(
    tmp_path: Path,
):
    (tmp_path / "alpha.txt").write_text(
        "alpha",
        encoding="utf-8",
    )

    (tmp_path / "beta.txt").write_text(
        "beta",
        encoding="utf-8",
    )

    inspector = FilesystemInspector(
        root=tmp_path,
        authorized=True,
    )

    result = inspector.list_directory()

    assert result.kind is FilesystemResultKind.SUCCESS
    assert tmp_path / "alpha.txt" in result.entries
    assert tmp_path / "beta.txt" in result.entries


def test_directory_listing_is_bounded(
    tmp_path: Path,
):
    for index in range(
        FilesystemInspector.MAX_DIRECTORY_ENTRIES + 25
    ):
        (tmp_path / f"entry-{index}.txt").write_text(
            "content",
            encoding="utf-8",
        )

    inspector = FilesystemInspector(
        root=tmp_path,
        authorized=True,
    )

    result = inspector.list_directory()

    assert result.kind is FilesystemResultKind.LIMIT_REACHED
    assert len(result.entries) == (
        FilesystemInspector.MAX_DIRECTORY_ENTRIES
    )


def test_inspect_path_reports_existing_file(
    tmp_path: Path,
):
    target = tmp_path / "example.txt"

    target.write_text(
        "hello",
        encoding="utf-8",
    )

    inspector = FilesystemInspector(
        root=tmp_path,
        authorized=True,
    )

    result = inspector.inspect_path(target)

    assert result.kind is FilesystemResultKind.SUCCESS


def test_inspect_path_reports_missing_path(
    tmp_path: Path,
):
    inspector = FilesystemInspector(
        root=tmp_path,
        authorized=True,
    )

    result = inspector.inspect_path(
        tmp_path / "missing.txt"
    )

    assert result.kind is FilesystemResultKind.NOT_FOUND


def test_read_file_returns_actual_content(
    tmp_path: Path,
):
    target = tmp_path / "example.txt"

    target.write_text(
        "Sofía filesystem test.",
        encoding="utf-8",
    )

    inspector = FilesystemInspector(
        root=tmp_path,
        authorized=True,
    )

    result = inspector.read_file(target)

    assert result.kind is FilesystemResultKind.SUCCESS
    assert result.content == "Sofía filesystem test."


def test_read_file_does_not_modify_file(
    tmp_path: Path,
):
    target = tmp_path / "example.txt"

    original = "original content"

    target.write_text(
        original,
        encoding="utf-8",
    )

    inspector = FilesystemInspector(
        root=tmp_path,
        authorized=True,
    )

    inspector.read_file(target)

    assert target.read_text(
        encoding="utf-8"
    ) == original


def test_large_file_is_rejected_before_read(
    tmp_path: Path,
):
    target = tmp_path / "large.txt"

    with target.open("wb") as file_handle:
        file_handle.truncate(
            FilesystemInspector.MAX_FILE_BYTES + 1
        )

    inspector = FilesystemInspector(
        root=tmp_path,
        authorized=True,
    )

    result = inspector.read_file(target)

    assert result.kind is FilesystemResultKind.LIMIT_REACHED
    assert result.content is None
    assert "was not read" in result.message


def test_path_outside_authorized_root_is_rejected(
    tmp_path: Path,
):
    root = tmp_path / "root"
    outside = tmp_path / "outside"

    root.mkdir()
    outside.mkdir()

    target = outside / "secret.txt"

    target.write_text(
        "outside scope",
        encoding="utf-8",
    )

    inspector = FilesystemInspector(
        root=root,
        authorized=True,
    )

    result = inspector.read_file(target)

    assert result.kind is FilesystemResultKind.UNAUTHORIZED


def test_parent_traversal_is_rejected(
    tmp_path: Path,
):
    root = tmp_path / "root"
    outside = tmp_path / "outside"

    root.mkdir()
    outside.mkdir()

    target = outside / "secret.txt"

    target.write_text(
        "outside scope",
        encoding="utf-8",
    )

    inspector = FilesystemInspector(
        root=root,
        authorized=True,
    )

    result = inspector.read_file(
        Path("..") / "outside" / "secret.txt"
    )

    assert result.kind is FilesystemResultKind.UNAUTHORIZED


def test_search_files_returns_matching_files(
    tmp_path: Path,
):
    source = tmp_path / "src"
    source.mkdir()

    first = source / "first.py"
    second = source / "second.py"
    text = source / "notes.txt"

    first.write_text(
        "first",
        encoding="utf-8",
    )

    second.write_text(
        "second",
        encoding="utf-8",
    )

    text.write_text(
        "notes",
        encoding="utf-8",
    )

    inspector = FilesystemInspector(
        root=tmp_path,
        authorized=True,
    )

    result = inspector.search_files("*.py")

    assert result.kind is FilesystemResultKind.SUCCESS
    assert first in result.entries
    assert second in result.entries
    assert text not in result.entries


def test_search_files_is_bounded_by_result_limit(
    tmp_path: Path,
):
    for index in range(
        FilesystemInspector.MAX_SEARCH_RESULTS + 25
    ):
        (tmp_path / f"file-{index}.py").write_text(
            "content",
            encoding="utf-8",
        )

    inspector = FilesystemInspector(
        root=tmp_path,
        authorized=True,
    )

    result = inspector.search_files("*.py")

    assert result.kind is FilesystemResultKind.LIMIT_REACHED
    assert len(result.entries) == (
        FilesystemInspector.MAX_SEARCH_RESULTS
    )


def test_search_files_rejects_long_pattern(
    tmp_path: Path,
):
    inspector = FilesystemInspector(
        root=tmp_path,
        authorized=True,
    )

    pattern = "a" * (
        FilesystemInspector.MAX_SEARCH_PATTERN_LENGTH + 1
    )

    try:
        inspector.search_files(pattern)
    except ValueError:
        return

    raise AssertionError(
        "Search pattern exceeding the configured limit "
        "should raise ValueError."
    )


def test_search_files_rejects_empty_pattern(
    tmp_path: Path,
):
    inspector = FilesystemInspector(
        root=tmp_path,
        authorized=True,
    )

    try:
        inspector.search_files("")
    except ValueError:
        return

    raise AssertionError(
        "Empty search pattern should raise ValueError."
    )


def test_filesystem_root_is_exposed(
    tmp_path: Path,
):
    inspector = FilesystemInspector(
        root=tmp_path,
        authorized=False,
    )

    assert inspector.root == tmp_path.resolve()


def test_filesystem_authorization_can_be_observed(
    tmp_path: Path,
):
    inspector = FilesystemInspector(
        root=tmp_path,
        authorized=True,
    )

    assert inspector.authorized is True