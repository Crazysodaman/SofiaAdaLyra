from pathlib import Path

import pytest

import sofia.state.atomic_file as atomic_file
from sofia.state.atomic_file import atomic_write_text


def test_atomic_write_creates_and_replaces_text(tmp_path: Path) -> None:
    target = tmp_path / "state.json"

    atomic_write_text(target, "first\n")
    assert target.read_text(encoding="utf-8") == "first\n"

    atomic_write_text(target, "second\n")
    assert target.read_text(encoding="utf-8") == "second\n"
    assert tuple(tmp_path.glob(".state.json.*.tmp")) == ()


def test_failed_replace_preserves_existing_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "state.json"
    target.write_text("known-good\n", encoding="utf-8")

    def fail_replace(source, destination):
        raise PermissionError("simulated sharing violation")

    monkeypatch.setattr(atomic_file.os, "replace", fail_replace)

    with pytest.raises(PermissionError):
        atomic_write_text(
            target,
            "new-value\n",
            attempts=1,
        )

    assert target.read_text(encoding="utf-8") == "known-good\n"
    assert tuple(tmp_path.glob(".state.json.*.tmp")) == ()


def test_transient_replace_failure_is_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "state.json"
    real_replace = atomic_file.os.replace
    attempts = []

    def flaky_replace(source, destination):
        attempts.append((source, destination))
        if len(attempts) == 1:
            raise PermissionError("transient")
        return real_replace(source, destination)

    monkeypatch.setattr(atomic_file.os, "replace", flaky_replace)
    monkeypatch.setattr(atomic_file.time, "sleep", lambda seconds: None)

    atomic_write_text(
        target,
        "durable\n",
        attempts=2,
        initial_delay_seconds=0,
    )

    assert len(attempts) == 2
    assert target.read_text(encoding="utf-8") == "durable\n"
