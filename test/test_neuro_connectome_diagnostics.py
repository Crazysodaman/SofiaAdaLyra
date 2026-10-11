"""Read-only NEURO Settings diagnostics regression source (not executed)."""
from __future__ import annotations

import sqlite3

from sofia.neuro.store import neuro_connectome_diagnostics, neuro_observability_text
from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite


def test_connectome_settings_are_visible_without_live_neuro_snapshot(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    result = neuro_observability_text(state)
    assert "not recorded a production snapshot" in result
    assert "Connectome competition configured: enabled" in result
    assert "Reviewed association learning configured: disabled" in result
    assert "Observed fallback: UNKNOWN" in result
    assert "Association confidence: UNKNOWN" in result
    with sqlite3.connect(state) as db:
        names = {row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
    assert "neuro_association_weight" not in names


def test_connectome_aggregation_never_discloses_principal_or_candidate(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    with sqlite3.connect(state) as db:
        db.execute(
            "CREATE TABLE neuro_association_weight ("
            "principal_id TEXT,audience_id TEXT,candidate_id TEXT,"
            "feature_unit INTEGER,weight REAL,changed_at TEXT)"
        )
        db.execute("CREATE TABLE neuro_association_event (occurred_at TEXT)")
        db.executemany(
            "INSERT INTO neuro_association_weight VALUES(?,?,?,?,?,?)",
            [
                ("private-principal","private-audience","private-id",1,0.6,"2026-10-11"),
                ("private-principal","private-audience","private-id",2,-0.2,"2026-10-11"),
            ],
        )
        db.execute("INSERT INTO neuro_association_event VALUES(?)",("2026-10-11",))
    text = "\n".join(neuro_connectome_diagnostics(state))
    assert "2 feature weights for 1 distinct candidates" in text
    assert "Mean absolute association weight: 0.400" in text
    assert "Reviewed teaching/reversion receipts: 1" in text
    assert "confidence score" in text
    assert "private-principal" not in text
    assert "private-audience" not in text
    assert "private-id" not in text


def test_selection_fallback_does_not_invent_a_circuit_failure(tmp_path, monkeypatch):
    from sofia.neuro import store as module

    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    observed = {
        "updated_at":"2026-10-11T12:00:00+00:00", "routing":None,
        "snapshot":{
            "selection_method":"salience-v1",
            "winner_reason":"deterministic salience","focus":None,"secondary":(),
            "active_signal_count":0,"homeostasis":{
                "cognitive_load":0.1,"novelty_load":0.1,"competition_pressure":0.1,
            },
        },
    }
    monkeypatch.setattr(module.NeuroObservabilityStore,"current",lambda self:observed)
    rendered = module.neuro_observability_text(state)
    assert "Latest recorded selection algorithm: salience-v1" in rendered
    assert "deterministic selection observed while circuit enabled" in rendered
    assert "reason NOT independently established" in rendered
    assert "circuit failed" not in rendered
