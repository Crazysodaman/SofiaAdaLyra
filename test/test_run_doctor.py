from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import shutil
import sqlite3

import pytest

from sofia.constitution.store import canonical_constitution_text
from sofia.platform.run import doctor
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SEED_CONSTITUTION = (
    REPOSITORY_ROOT
    / "src"
    / "sofia"
    / "constitution"
    / "constitution.md"
)
SEED_PERSONALITY = (
    REPOSITORY_ROOT
    / "src"
    / "sofia"
    / "personality"
    / "personality.json"
)
SEED_AVATAR = REPOSITORY_ROOT / "src" / "sofia" / "embodiment" / "avatar.json"
FIXTURE_INSTANCE_ID = "00000000-0000-4000-8000-000000000001"
EXPECTED_CHECK_IDS = (
    "storage_layout",
    "canonical_state",
    "sqlite_integrity",
    "schema_registry",
    "constitution_integrity",
    "identity_authenticity",
    "personality_loadability",
    "embodiment_loadability",
    "startup_heartbeat",
    "writer_lock_files",
)


def provisioned_state_root(tmp_path: Path) -> Path:
    state_root = tmp_path / "state"
    protected = state_root / "protected"
    protected.mkdir(parents=True)

    shutil.copyfile(SEED_CONSTITUTION, protected / "constitution.md")
    trusted_hash = sha256(
        canonical_constitution_text(
            SEED_CONSTITUTION.read_text(encoding="utf-8")
        ).encode("utf-8")
    ).hexdigest()
    (protected / "constitution.sha256").write_text(
        trusted_hash + "\n",
        encoding="utf-8",
    )
    (protected / "identity.json").write_text(
        json.dumps(
            {
                "name": "Sofía Ada Lyra",
                "instance_id": FIXTURE_INSTANCE_ID,
            }
        ),
        encoding="utf-8",
    )
    shutil.copyfile(SEED_PERSONALITY, state_root / "personality.json")
    shutil.copyfile(SEED_AVATAR, state_root / "avatar.json")
    bootstrap_canonical_sqlite(state_root / "sofia.db")
    return state_root


def test_doctor_reports_healthy_provisioned_install(tmp_path: Path) -> None:
    state_root = provisioned_state_root(tmp_path)
    before = sorted(str(path) for path in state_root.rglob("*"))

    report = doctor.run_doctor(state_path=state_root / "sofia.db")

    assert report.outcome == "healthy"
    assert report.failed_count == 0
    assert report.degraded_count == 0
    assert tuple(
        check.id for check in report.checks
    ) == EXPECTED_CHECK_IDS
    identity = report.check("identity_authenticity")
    assert identity is not None
    assert identity.status == doctor.STATUS_OK
    assert FIXTURE_INSTANCE_ID in identity.detail
    after = sorted(str(path) for path in state_root.rglob("*"))
    assert before == after


def test_doctor_is_explicit_about_unknown_facts(tmp_path: Path) -> None:
    state_root = provisioned_state_root(tmp_path)
    report = doctor.run_doctor(state_path=state_root / "sofia.db")

    schema_check = report.check("schema_registry")
    heartbeat_check = report.check("startup_heartbeat")
    assert schema_check is not None
    assert heartbeat_check is not None
    assert schema_check.status == doctor.STATUS_UNKNOWN
    assert "not registered yet" in schema_check.detail
    assert heartbeat_check.status == doctor.STATUS_UNKNOWN
    assert report.unknown_count == 2


def test_doctor_fails_when_canonical_database_missing(
    tmp_path: Path,
) -> None:
    state_root = provisioned_state_root(tmp_path)
    (state_root / "sofia.db").unlink()

    report = doctor.run_doctor(state_path=state_root / "sofia.db")

    canonical = report.check("canonical_state")
    integrity = report.check("sqlite_integrity")
    assert canonical is not None
    assert integrity is not None
    assert canonical.status == doctor.STATUS_FAILED
    assert integrity.status == doctor.STATUS_FAILED
    assert report.outcome == "failed"


def test_doctor_fails_on_corrupted_constitution_hash(
    tmp_path: Path,
) -> None:
    state_root = provisioned_state_root(tmp_path)
    hash_path = state_root / "protected" / "constitution.sha256"
    hash_path.write_text("0" * 64 + "\n", encoding="utf-8")

    report = doctor.run_doctor(state_path=state_root / "sofia.db")

    constitution = report.check("constitution_integrity")
    assert constitution is not None
    assert constitution.status == doctor.STATUS_FAILED
    assert report.outcome == "failed"


def test_doctor_flags_schema_registry_mismatch(tmp_path: Path) -> None:
    state_root = provisioned_state_root(tmp_path)
    database = state_root / "sofia.db"
    with sqlite3.connect(database) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS state_schema_component (
                component TEXT PRIMARY KEY,
                current_revision INTEGER NOT NULL CHECK(current_revision > 0),
                readable_min INTEGER NOT NULL CHECK(readable_min > 0),
                readable_max INTEGER NOT NULL CHECK(readable_max > 0),
                writable_min INTEGER NOT NULL CHECK(writable_min > 0),
                writable_max INTEGER NOT NULL CHECK(writable_max > 0),
                registered_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            INSERT INTO state_schema_component VALUES
            ('state-plane', 9, 1, 9, 9, 9, '2030-01-01T00:00:00+00:00')
            """
        )
        db.commit()

    report = doctor.run_doctor(state_path=database)

    schema_check = report.check("schema_registry")
    assert schema_check is not None
    assert schema_check.status == doctor.STATUS_FAILED
    assert "state-plane" in schema_check.detail


def test_doctor_flags_degraded_startup_heartbeat(tmp_path: Path) -> None:
    state_root = provisioned_state_root(tmp_path)
    database = state_root / "sofia.db"
    with sqlite3.connect(database) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS run_application_heartbeat (
                instance_id TEXT PRIMARY KEY,
                recorded_at TEXT NOT NULL,
                ready INTEGER NOT NULL CHECK(ready IN (0,1)),
                runtime_state TEXT NOT NULL,
                database_writable INTEGER NOT NULL
                    CHECK(database_writable IN (0,1)),
                background_running INTEGER NOT NULL
                    CHECK(background_running IN (0,1)),
                detail TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            INSERT INTO run_application_heartbeat VALUES
            ('i', '2030-01-01T00:00:00+00:00', 0, 'STARTING', 1, 0,
             'startup pending')
            """
        )
        db.commit()

    report = doctor.run_doctor(state_path=database)

    heartbeat = report.check("startup_heartbeat")
    assert heartbeat is not None
    assert heartbeat.status == doctor.STATUS_DEGRADED
    assert report.outcome == "degraded"


def test_doctor_missing_instance_reports_only_observed_absence(
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "empty"
    state_root.mkdir()

    report = doctor.run_doctor(state_path=state_root / "sofia.db")

    assert report.outcome == "failed"
    canonical = report.check("canonical_state")
    identity = report.check("identity_authenticity")
    assert canonical is not None
    assert identity is not None
    assert canonical.status == doctor.STATUS_FAILED
    assert identity.status == doctor.STATUS_FAILED
    assert _state_files_are_untouched(state_root)


def _state_files_are_untouched(state_root: Path) -> bool:
    return sorted(str(path) for path in state_root.rglob("*")) == []


def test_doctor_cli_exit_codes_and_json(tmp_path: Path, capsys) -> None:
    state_root = provisioned_state_root(tmp_path)

    exit_code = doctor.main(
        ["--state-path", str(state_root), "--json"]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["outcome"] == "healthy"
    assert tuple(
        check["id"] for check in payload["checks"]
    ) == EXPECTED_CHECK_IDS

    empty = tmp_path / "missing"
    empty.mkdir()
    failed_code = doctor.main(["--state-path", str(empty)])
    assert failed_code == 3


def test_doctor_check_validation() -> None:
    with pytest.raises(ValueError):
        doctor.DoctorCheck(
            id="x",
            title="t",
            status="MAYBE",
            detail="d",
        )
    with pytest.raises(TypeError):
        doctor.DoctorReport(
            generated_at="not-a-datetime",
            state_path=Path("s"),
            checks=(),
        )
    with pytest.raises(ValueError):
        doctor.DoctorReport(
            generated_at=doctor.datetime.now(),
            state_path=Path("s"),
            checks=(),
        )
