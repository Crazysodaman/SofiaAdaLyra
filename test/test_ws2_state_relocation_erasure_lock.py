"""Deferred regression for signed-erasure append serialization during recovery.

Runs only against synthetic relocated homes; no host cutover, live deletion,
backup rotation, Android dispatch or CI invocation is performed here.
"""
from contextlib import contextmanager

import sofia.ops.state_relocation as relocation
from sofia.memory.deletion_ledger import MemoryDeletionLedger
from test.test_venus_artemis_relocation_evidence import _plan, _stage


def test_final_candidate_publication_is_inside_existing_journal_append_lock(
    tmp_path, monkeypatch,
):
    proof = _plan(tmp_path)
    underlying_lock = MemoryDeletionLedger._exclusive
    original_publish = relocation._publish_new_home_without_replacing
    held = [False]
    observed = []

    @contextmanager
    def tracked_lock(ledger):
        with underlying_lock(ledger):
            assert not held[0]
            held[0] = True
            try:
                yield
            finally:
                held[0] = False

    def observed_publish(staging, destination, **kwargs):
        observed.append(held[0])
        return original_publish(staging, destination, **kwargs)

    monkeypatch.setattr(MemoryDeletionLedger, "_exclusive", tracked_lock)
    monkeypatch.setattr(
        relocation, "_publish_new_home_without_replacing", observed_publish,
    )

    staged, _calls = _stage(proof, tmp_path, monkeypatch)

    assert staged.activated is False
    assert observed == [True]
    assert held == [False]
    assert (proof.destination_root / "sofia.db").is_file()
    assert (tmp_path / "operator-held" / "erasures.jsonl.lock").is_file()
