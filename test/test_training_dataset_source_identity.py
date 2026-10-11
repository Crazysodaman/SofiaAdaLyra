"""Deferred real intake source-identity regression, no model training."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sofia.evolve.training_sources import inspect_public_dataset

pytestmark = pytest.mark.pkg_core
NOW = datetime(2026, 10, 11, 18, tzinfo=timezone.utc)


def write_rows(path):
    path.write_text(
        "".join(
            json.dumps({
                "instruction": f"Public circuit tutorial {i}",
                "response": f"Neutral public example {i}",
            }) + "\n" for i in range(23)
        ),
        encoding="utf-8",
    )


def inspect(path):
    return inspect_public_dataset(
        path=path,
        source_class="owner_original_nonprivate",
        license_id="OWNER-ORIGINAL",
        source_ref="owner-source:reviewed-circuit-examples",
        approval_ref="owner-ui:reviewed-circuit-examples",
        at=NOW,
    )


def test_stable_local_file_is_read_in_full(tmp_path):
    data = tmp_path / "circuits.jsonl"
    write_rows(data)
    reviewed = inspect(data)
    assert reviewed.unique_rows == 23
    assert reviewed.bytes_observed == data.stat().st_size
    assert reviewed.training_authorized is False


def test_symlinked_parent_is_not_allowed_as_dataset_source(tmp_path):
    original = tmp_path / "canonical"
    original.mkdir()
    data = original / "circuits.jsonl"
    write_rows(data)
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(original, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable on host")
    with pytest.raises(PermissionError, match="symbolic links or junctions"):
        inspect(alias / "circuits.jsonl")


def test_file_mutated_between_stat_and_open_is_denied(tmp_path, monkeypatch):
    data = tmp_path / "circuits.jsonl"
    write_rows(data)
    actual_open = Path.open
    raced = {"done": False}

    def open_with_race(path, *args, **kwargs):
        if (
            not raced["done"]
            and path == data
            and args and args[0] == "rb"
        ):
            raced["done"] = True
            with actual_open(path, "ab") as out:
                out.write(b"\n")
        return actual_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_with_race)
    with pytest.raises(PermissionError, match="changed before inspection"):
        inspect(data)
    assert raced["done"] is True
