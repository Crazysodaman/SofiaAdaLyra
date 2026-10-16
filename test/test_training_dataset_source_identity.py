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


def test_real_git_worktree_source_is_denied_but_empty_ancestor_marker_is_not(tmp_path):
    # Some CI/container roots expose an empty .git sentinel. It must not make
    # every independent temp file look like repository content.
    empty_root=tmp_path/"mounted-root"
    (empty_root/".git").mkdir(parents=True)
    independent=empty_root/"datasets"/"public.jsonl"
    independent.parent.mkdir()
    write_rows(independent)
    assert inspect(independent).unique_rows==23

    checkout=tmp_path/"checkout"
    control=checkout/".git"
    (control/"objects").mkdir(parents=True)
    (control/"HEAD").write_text("ref: refs/heads/main\n",encoding="utf-8")
    tracked=checkout/"training.jsonl"
    write_rows(tracked)
    with pytest.raises(PermissionError,match="Git checkout"):
        inspect(tracked)

    linked=tmp_path/"linked-worktree"
    linked.mkdir()
    (linked/".git").write_text("gitdir: ../metadata/worktrees/linked\n",encoding="utf-8")
    linked_data=linked/"training.jsonl"
    write_rows(linked_data)
    with pytest.raises(PermissionError,match="Git checkout"):
        inspect(linked_data)


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


@pytest.mark.parametrize("source_class,license_id,source_ref", [
    ("licensed_public", "OWNER-ORIGINAL", "public-source:claimed-rights"),
    ("owner_original_nonprivate", "CC0-1.0", "owner-source:claimed-rights"),
    ("licensed_public", "CC0-1.0", "owner-source:wrong-origin"),
    ("owner_original_nonprivate", "OWNER-ORIGINAL", "public-source:wrong-origin"),
    ("synthetic_nonsensitive", "OWNER-ORIGINAL", "public-source:mismatch"),
])
def test_training_rights_labels_must_match_provenance_origin(
    tmp_path,source_class,license_id,source_ref,
):
    data=tmp_path/"legit.jsonl"
    write_rows(data)
    with pytest.raises(PermissionError,match="rights class"):
        inspect_public_dataset(
            path=data,source_class=source_class,license_id=license_id,
            source_ref=source_ref,approval_ref="owner-ui:reviewed",
            at=NOW,
        )


def test_valid_explicit_public_rights_class_still_scans(tmp_path):
    data=tmp_path/"public.jsonl"
    write_rows(data)
    reviewed=inspect_public_dataset(
        path=data,source_class="licensed_public",license_id="CC0-1.0",
        source_ref="public-source:checked-by-owner",
        approval_ref="owner-ui:checked-by-owner",
        at=NOW,
    )
    assert reviewed.source_class=="licensed_public"
    assert reviewed.training_authorized is False


def test_blank_instruction_cannot_be_admitted_as_training_example(tmp_path):
    data=tmp_path/"blank.jsonl"
    write_rows(data)
    with data.open("a",encoding="utf-8") as out:
        out.write(json.dumps({"instruction":"   ","response":"Public text"})+"\n")
    with pytest.raises(PermissionError,match="unsafe source"):
        inspect(data)
