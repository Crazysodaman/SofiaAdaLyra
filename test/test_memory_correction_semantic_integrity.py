"""Deferred canonical correction verification and state-loss regressions."""
import os
import sqlite3

import pytest

from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.state.canonical_sqlite import CanonicalStateUnavailable
from sofia.state.sqlite_plane import SQLiteStatePlane
from sofia.verify.semantic_integrity import SemanticIntegrityVerifier
from test.test_memory_reviewed_corrections import _candidate


def _state(tmp_path):
    path = tmp_path / "sofia.db"
    plane = SQLiteStatePlane(path)
    store = DurableMemoryCandidateStore(path)
    original = _candidate("Old favorite railroad", 1)
    correction = _candidate("Correct favorite railroad", 2)
    store.propose(original)
    store.promote(original.candidate_id)
    store.propose(correction)
    store.link_correction(correction.candidate_id, original.candidate_id)
    store.promote(correction.candidate_id)
    store.close()
    return path, plane, original, correction


def _codes(report):
    return {finding.code for finding in report.findings}


def test_valid_atomic_correction_has_no_correction_integrity_findings(tmp_path):
    path, plane, original, correction = _state(tmp_path)
    report = SemanticIntegrityVerifier(path, state_plane=plane).verify()
    assert not {x for x in _codes(report) if x.startswith("memory.correction.")}


def test_correction_verifier_detects_independent_status_and_scope_tampering(tmp_path):
    path, plane, original, correction = _state(tmp_path)
    verifier = SemanticIntegrityVerifier(path, state_plane=plane)
    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE memory_candidate SET status='promoted' WHERE candidate_id=?",
            (str(original.candidate_id),),
        )
        db.commit()
    assert "memory.correction.not_settled" in _codes(verifier.verify())

    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE memory_candidate SET audience_id='mobile:private:foreign' "
            "WHERE candidate_id=?", (str(correction.candidate_id),),
        )
        db.commit()
    assert "memory.correction.cross_scope" in _codes(verifier.verify())


def test_integrity_verifier_cannot_follow_replaced_state(tmp_path):
    path, plane, original, correction = _state(tmp_path)
    verifier = SemanticIntegrityVerifier(path, state_plane=plane)
    alternate = tmp_path / "different.db"
    with sqlite3.connect(alternate) as db:
        db.execute("CREATE TABLE decoy (id INTEGER)")
    os.replace(alternate, path)
    with pytest.raises(CanonicalStateUnavailable, match="replaced"):
        verifier.verify()
