"""Read-only operator status backed by actual canonical LIFE/ACT/SAFE rows."""
from pathlib import Path
from types import SimpleNamespace
import sqlite3

from sofia.state.canonical_sqlite import CanonicalSQLiteGuard
from sofia.ui.settings_sections import SettingsSections


def _read_snapshot(path: Path) -> str:
    panel = object.__new__(SettingsSections)
    panel.config = SimpleNamespace(state_path=path)
    panel._canonical_state = CanonicalSQLiteGuard(path)
    return panel.autonomy_snapshot()


def test_operator_snapshot_never_invents_work_without_source_rows(tmp_path):
    path = tmp_path / "sofia.db"
    path.touch()
    shown = _read_snapshot(path)
    assert "no actions performed" in shown
    assert "UNKNOWN (no recorded selection)" in shown
    assert "Resource pressure: UNKNOWN" in shown
    assert "ACT pending system notices: UNKNOWN" in shown


def test_operator_snapshot_scopes_projects_and_labels_historical_pressure(tmp_path):
    path = tmp_path / "sofia.db"
    with sqlite3.connect(path) as db:
        db.execute("""
            CREATE TABLE life_selection(
                selection_id TEXT PRIMARY KEY, kind TEXT, project_id TEXT,
                reason TEXT, resource_pressure REAL, busy INTEGER, selected_at TEXT
            )
        """)
        db.execute(
            "INSERT INTO life_selection VALUES (?,?,?,?,?,?,?)",
            ("selected:1", "project", "project:mine", "verified interest", 0.42, 0,
             "2026-10-11T08:00:00+00:00"),
        )
        db.execute("""
            CREATE TABLE life_project(
                project_id TEXT PRIMARY KEY, name TEXT, status TEXT, updated_at TEXT,
                owner_principal_id TEXT, audience_id TEXT
            )
        """)
        db.executemany(
            "INSERT INTO life_project VALUES (?,?,?,?,?,?)",
            [
                ("project:mine", "My art", "active", "2026-10-11T08:00:00+00:00",
                 "sofia:self", "local:text"),
                ("project:other", "Other private project", "active",
                 "2026-10-11T09:00:00+00:00", "person:other", "private:other"),
            ],
        )
        db.execute("""
            CREATE TABLE act_system_notice(notice_id TEXT, status TEXT)
        """)
        db.execute(
            "INSERT INTO act_system_notice VALUES (?,?)",
            ("notice:1", "queued"),
        )
        db.execute("""
            CREATE TABLE act_outreach_trace(
                trace_id INTEGER PRIMARY KEY, stage TEXT, reason TEXT,
                recorded_at TEXT, receipt_id TEXT, recipient_confirmed INTEGER
            )
        """)
        db.execute(
            "INSERT INTO act_outreach_trace VALUES (?,?,?,?,?,?)",
            (1, "suppressed", "quiet_hours", "2026-10-11T08:00:00+00:00", None, 0),
        )
    shown = _read_snapshot(path)
    assert "My art [active]" in shown
    assert "Other private project" not in shown
    assert "Resource pressure at selection: 0.42" in shown
    assert "historical, not a live measurement" in shown
    assert "ACT pending system notices: 1" in shown
    assert "stage=suppressed, reason=quiet_hours" in shown
    assert "recipient_confirmed=False" in shown
