from datetime import datetime, timezone
import json

from sofia.ops.history import SQLiteTelemetryHistory
from sofia.ops.model import HostTelemetry


NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def telemetry(cpu: float = 12.5) -> HostTelemetry:
    return HostTelemetry(
        observed_at=NOW,
        cpu_percent=cpu,
        ram_used_bytes=4,
        ram_total_bytes=16,
        storage_free_bytes=100,
    )


def test_sqlite_telemetry_round_trip_uses_canonical_database(tmp_path):
    state = tmp_path / "sofia.db"
    history = SQLiteTelemetryHistory(state)
    history.append("venus", telemetry())

    restored = SQLiteTelemetryHistory(state)

    assert restored.latest("venus") == telemetry()


def test_legacy_jsonl_telemetry_migrates_and_retires(tmp_path):
    legacy = tmp_path / "ops-telemetry.jsonl"
    from dataclasses import asdict
    rows = []
    for cpu in (11.0, 12.5):
        row = asdict(telemetry(cpu))
        row["observed_at"] = NOW.isoformat()
        row["host_id"] = "venus"
        rows.append(json.dumps(row))
    legacy.write_text("\n".join(rows) + "\n", encoding="utf-8")

    state = tmp_path / "sofia.db"
    history = SQLiteTelemetryHistory(
        state,
        legacy_path=legacy,
    )

    assert history.latest("venus") == telemetry(12.5)
    assert not legacy.exists()
    assert (tmp_path / "ops-telemetry.jsonl.migrated").is_file()
