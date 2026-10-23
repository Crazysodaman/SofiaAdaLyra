"""CA-6109: no synthetic measurement becomes an operational accept."""
from __future__ import annotations

import pytest

from sofia.platform.ops.capacity_probe import measure_storage, report_storage
from sofia.platform.ops.capacity import CapacityError
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite

pytestmark = pytest.mark.pkg_ops


def test_real_file_metadata_including_sqlite_wal_and_nested_assets(tmp_path):
    db = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    (tmp_path / "sofia.db-wal").write_bytes(b"x" * 11)
    media = tmp_path / "media"
    (media / "nested").mkdir(parents=True)
    (media / "nested" / "voice.wav").write_bytes(b"abc")
    readings = measure_storage(db, media_dir=media)
    values = {row.resource: row.used for row in readings}
    assert values["canonical_db_bytes"] == db.stat().st_size + 11
    assert values["media_asset_bytes"] == 3
    result = report_storage(readings)
    assert result["acceptance_verified"] is False
    assert result["overall"] == "warn"
    assert result["readings"]["media_asset_bytes"] == 3
    assert "backup_bytes" in result["missing_resources"]
    assert "cpu_sustained_millicores" in result["missing_resources"]


def test_missing_database_or_measurement_dir_refuses_to_invent_readings(tmp_path):
    with pytest.raises(FileNotFoundError):
        measure_storage(tmp_path / "not_a_database.db")
    db = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    with pytest.raises(CapacityError):
        measure_storage(db, archive_dir=tmp_path / "does_not_exist")


def test_symlink_escape_is_denied_without_following_source_data(tmp_path):
    db = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    media = tmp_path / "media"
    media.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "private").write_bytes(b"do not read this")
    link = media / "redirect"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("host policy does not allow symlinks")
    with pytest.raises(CapacityError, match="symlink"):
        measure_storage(db, media_dir=media)


def test_limit_and_overlap_fail_closed(tmp_path):
    db = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    media = tmp_path / "media"
    media.mkdir()
    for index in range(3):
        (media / f"{index}.txt").write_bytes(b"sample")
    with pytest.raises(CapacityError, match="entry limit"):
        measure_storage(db, media_dir=media, max_entries=2)
    with pytest.raises(CapacityError, match="overlapping"):
        measure_storage(db, media_dir=media, archive_dir=media)
    with pytest.raises(CapacityError, match="max_depth"):
        measure_storage(db, max_depth=-1)


def test_nonregular_sidecar_fails_closed(tmp_path):
    db = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    (tmp_path / "sofia.db-wal").mkdir()
    with pytest.raises(CapacityError, match="nonregular"):
        measure_storage(db)
