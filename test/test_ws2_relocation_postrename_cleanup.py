"""Deferred high-risk staging cleanup after post-rename durability uncertainty.

Simulates publication of a complete synthetic stage, then failed parent fsync.
No actual state migration, activation, source restore or tests are run.
"""
import os

import pytest

import sofia.ops.state_relocation as relocation
from sofia.ops.state_relocation import StateHomePublicationUncertain
from test.test_venus_artemis_relocation_evidence import _plan, _stage


def test_postrename_uncertainty_is_not_masked_by_missing_staging_cleanup(
    tmp_path, monkeypatch,
):
    proof = _plan(tmp_path)
    original_publish = relocation._publish_new_home_without_replacing
    observed = []

    def simulate_rename_then_unproven_fsync(staging, destination, **kwargs):
        # Real authorization and final erasure check are still required.
        if kwargs.get("recheck_authorization") is not None:
            assert kwargs["recheck_authorization"]() is True
        os.rename(staging, destination)
        observed.append((staging, destination))
        raise StateHomePublicationUncertain(
            "candidate home was renamed but publication durability is "
            "uncertain; do not activate or silently retry over destination"
        )

    monkeypatch.setattr(
        relocation, "_publish_new_home_without_replacing",
        simulate_rename_then_unproven_fsync,
    )
    with pytest.raises(StateHomePublicationUncertain, match="do not activate"):
        _stage(proof, tmp_path, monkeypatch)

    assert len(observed) == 1
    staging, destination = observed[0]
    assert not staging.exists()
    assert (destination / "sofia.db").read_bytes() == b"isolated-stage-fixture"
    assert (destination / "protected" / "identity.json").is_file()
    assert proof.source_state_path.read_bytes() == b"isolated-original-fixture"
    assert not list(tmp_path.glob(".artemis-staged.restore-*"))
    # The visible candidate is NOT an activation receipt after the error.
    # It must be independently inspected, never overwritten on a retry.


def test_prepublication_error_cleans_only_random_staging(tmp_path, monkeypatch):
    proof = _plan(tmp_path)
    observed = []

    def refuse_before_rename(staging, destination, **kwargs):
        observed.append(staging)
        raise PermissionError("independent writer fence expired before publication")

    monkeypatch.setattr(
        relocation, "_publish_new_home_without_replacing",
        refuse_before_rename,
    )
    with pytest.raises(PermissionError, match="writer fence expired"):
        _stage(proof, tmp_path, monkeypatch)

    assert observed and not observed[0].exists()
    assert not proof.destination_root.exists()
    assert proof.source_state_path.read_bytes() == b"isolated-original-fixture"
