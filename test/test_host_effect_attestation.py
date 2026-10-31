"""Independent host-owned GOALS effect attestation ledger contracts."""

from datetime import datetime, timedelta, timezone
import os
from types import SimpleNamespace

import pytest

from sofia.platform.run.host_effect_attestation import (
    HostEffectAttestationError,
    HostEffectAttestationLedger,
)

OBSERVED_AT = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


def _after(base: datetime, seconds: float) -> datetime:
    return base + timedelta(seconds=seconds)


@pytest.fixture()
def ledger(tmp_path):
    return HostEffectAttestationLedger(tmp_path / "host-ops")


def test_attestation_seals_and_revalidates_exact_dispatch(tmp_path, ledger):  # noqa: ARG001
    digest = ledger.attest_effect(
        dispatch_id="goal-action:42",
        goal_id="goal:42",
        capability="portainer.summary",
        outcome="performed",
        attested_by="artemis",
        now=OBSERVED_AT,
    )
    assert len(digest) == 64
    assert ledger.store_path.exists() and ledger.store_path.is_file()
    verified = ledger.verify_dispatch_outcome(
        "goal-action:42",
        SimpleNamespace(
            goal_id="goal:42",
            assertion="portainer.summary",
            successful=True,
            observed_at=_after(OBSERVED_AT, 1),
        ),
    )
    assert verified is True


@pytest.mark.parametrize(
    ("goal_id", "assertion", "successful"),
    (
        ("goal:other", "portainer.summary", True),
        ("goal:42", "wrong.capability", True),
        ("goal:42", "portainer.summary", False),
        ("goal:42", "portainer.summary", None),
    ),
)
def test_attestation_never_authorizes_mismatched_receipt(
    ledger, goal_id, assertion, successful,
):
    ledger.attest_effect(
        dispatch_id="goal-action:42",
        goal_id="goal:42",
        capability="portainer.summary",
        outcome="performed",
        attested_by="artemis",
        now=OBSERVED_AT,
    )
    assert (
        ledger.verify_dispatch_outcome(
            "goal-action:42",
            SimpleNamespace(
                goal_id=goal_id,
                assertion=assertion,
                successful=successful,
                observed_at=_after(OBSERVED_AT, 1),
            ),
        )
        is False
    )


def test_absent_outcome_attests_independently_verified_no_effect(ledger):
    ledger.attest_effect(
        dispatch_id="goal-action:8",
        goal_id="goal:8",
        capability="cap.absent",
        outcome="absent",
        attested_by="artemis",
        now=OBSERVED_AT,
    )
    assert (
        ledger.verify_dispatch_outcome(
            "goal-action:8",
            SimpleNamespace(
                goal_id="goal:8",
                assertion="cap.absent",
                successful=False,
                observed_at=_after(OBSERVED_AT, 1),
            ),
        )
        is True
    )
    assert (
        ledger.verify_dispatch_outcome(
            "goal-action:8",
            SimpleNamespace(
                goal_id="goal:8",
                assertion="cap.absent",
                successful=True,
                observed_at=_after(OBSERVED_AT, 1),
            ),
        )
        is False
    )


def test_unknown_dispatch_is_not_verified_even_without_rows(ledger):
    assert (
        ledger.verify_dispatch_outcome(
            "goal-action:none",
            SimpleNamespace(
                goal_id="goal:0",
                assertion="x.y",
                successful=True,
                observed_at=_after(OBSERVED_AT, 5),
            ),
        )
        is False
    )


def test_one_seal_per_dispatch_is_enforced(ledger):
    ledger.attest_effect(
        dispatch_id="goal-action:1",
        goal_id="goal:1",
        capability="cap.x",
        outcome="performed",
        attested_by="artemis",
        now=OBSERVED_AT,
    )
    with pytest.raises(ValueError, match="already independently attested"):
        ledger.attest_effect(
            dispatch_id="goal-action:1",
            goal_id="goal:1",
            capability="cap.x",
            outcome="absent",
            attested_by="artemis",
            now=OBSERVED_AT,
        )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    (
        ({"dispatch_id": "  "}, "exact dispatch id"),
        ({"goal_id": ""}, "exact goal id"),
        ({"capability": ""}, "exact capability"),
        ({"attested_by": ""}, "attesting host identity"),
    ),
)
def test_attestation_requires_exact_identifiers(ledger, kwargs, message):
    seed = {
        "dispatch_id": "goal-action:9",
        "goal_id": "goal:9",
        "capability": "cap.q",
        "outcome": "performed",
        "attested_by": "artemis",
        "now": OBSERVED_AT,
    }
    seed.update(kwargs)
    with pytest.raises(ValueError, match=message):
        ledger.attest_effect(**seed)


@pytest.mark.parametrize("outcome", ("succeeded", "", "PERFORMED"))
def test_only_performed_or_absent_outcomes_are_sealable(ledger, outcome):
    with pytest.raises(ValueError, match="performed or absent"):
        ledger.attest_effect(
            dispatch_id="goal-action:10",
            goal_id="goal:10",
            capability="cap.p",
            outcome=outcome,
            attested_by="artemis",
            now=OBSERVED_AT,
        )


def test_naive_observation_time_is_refused(ledger):
    with pytest.raises(ValueError, match="timezone-aware"):
        ledger.attest_effect(
            dispatch_id="goal-action:2",
            goal_id="goal:2",
            capability="cap.y",
            outcome="performed",
            attested_by="artemis",
            now=OBSERVED_AT.replace(tzinfo=None),
        )


def test_host_observation_must_precede_claimed_core_receipt(ledger):
    ledger.attest_effect(
        dispatch_id="goal-action:3",
        goal_id="goal:3",
        capability="cap.z",
        outcome="performed",
        attested_by="artemis",
        now=OBSERVED_AT,
    )
    assert (
        ledger.verify_dispatch_outcome(
            "goal-action:3",
            SimpleNamespace(
                goal_id="goal:3",
                assertion="cap.z",
                successful=True,
                observed_at=_after(OBSERVED_AT, -1),
            ),
        )
        is False
    )
    assert (
        ledger.verify_dispatch_outcome(
            "goal-action:3",
            SimpleNamespace(
                goal_id="goal:3",
                assertion="cap.z",
                successful=True,
                observed_at=OBSERVED_AT,
            ),
        )
        is True
    )


def test_tampered_journal_cannot_authorize(ledger):
    ledger.attest_effect(
        dispatch_id="goal-action:4",
        goal_id="goal:4",
        capability="cap.w",
        outcome="performed",
        attested_by="artemis",
        now=OBSERVED_AT,
    )
    raw = ledger.store_path.read_text(encoding="utf-8-sig")
    raw = raw.replace('"capability":"cap.w"', '"capability":"forged"')
    ledger.store_path.write_text(raw, encoding="utf-8-sig")
    with pytest.raises(HostEffectAttestationError, match="tampered"):
        ledger.verify_dispatch_outcome(
            "goal-action:4",
            SimpleNamespace(
                goal_id="goal:4",
                assertion="cap.w",
                successful=True,
                observed_at=_after(OBSERVED_AT, 1),
            ),
        )


def test_removed_middle_row_breaks_chain(ledger):
    ledger.attest_effect(
        dispatch_id="goal-action:5",
        goal_id="goal:5",
        capability="cap.v",
        outcome="performed",
        attested_by="artemis",
        now=OBSERVED_AT,
    )
    ledger.attest_effect(
        dispatch_id="goal-action:6",
        goal_id="goal:6",
        capability="cap.u",
        outcome="absent",
        attested_by="artemis",
        now=OBSERVED_AT,
    )
    rows = [
        line for line in
        ledger.store_path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    ledger.store_path.write_text(rows[0] + "\n", encoding="utf-8-sig")
    with pytest.raises(HostEffectAttestationError, match="sealed tip"):
        ledger.verify_dispatch_outcome(
            "goal-action:6",
            SimpleNamespace(
                goal_id="goal:6",
                assertion="cap.u",
                successful=False,
                observed_at=_after(OBSERVED_AT, 2),
            ),
        )


def test_mismatched_host_key_cannot_unseal(ledger):
    ledger.attest_effect(
        dispatch_id="goal-action:7",
        goal_id="goal:7",
        capability="cap.k",
        outcome="performed",
        attested_by="artemis",
        now=OBSERVED_AT,
    )
    ledger._key_path.write_text("ff" * 32, encoding="utf-8-sig")
    with pytest.raises(HostEffectAttestationError, match="tampered"):
        ledger.verify_dispatch_outcome(
            "goal-action:7",
            SimpleNamespace(
                goal_id="goal:7",
                assertion="cap.k",
                successful=True,
                observed_at=_after(OBSERVED_AT, 1),
            ),
        )


def test_invalid_or_short_host_key_is_refused(ledger):
    ledger.attest_effect(
        dispatch_id="goal-action:11",
        goal_id="goal:11",
        capability="cap.j",
        outcome="performed",
        attested_by="artemis",
        now=OBSERVED_AT,
    )
    ledger._key_path.write_text("aa", encoding="utf-8-sig")
    with pytest.raises(HostEffectAttestationError, match="key is invalid"):
        ledger._journal(ledger.store_path)


def test_corrupt_row_is_reported_not_silent(ledger):
    ledger.attest_effect(
        dispatch_id="goal-action:12",
        goal_id="goal:12",
        capability="cap.i",
        outcome="performed",
        attested_by="artemis",
        now=OBSERVED_AT,
    )
    raw = ledger.store_path.read_text(encoding="utf-8-sig")
    ledger.store_path.write_text("{not-json}\n", encoding="utf-8-sig")
    with pytest.raises(HostEffectAttestationError, match="corrupt"):
        ledger._journal(ledger.store_path)


def test_store_root_is_created_owner_private(ledger, tmp_path):
    assert ledger._root.exists()
    assert ledger._root == tmp_path / "host-ops" / "platform-host-effects"
    assert ledger.store_path.parent == ledger._root


def test_ledger_rejects_redirected_store(tmp_path):
    """A journal that is a redirect symlink must never accept writes."""
    across = tmp_path / "elsewhere-journal.jsonl"
    across.write_text("{}", encoding="utf-8")
    try:
        link = tmp_path / "redirected-store.jsonl"
        link.symlink_to(across)
    except (OSError, NotImplementedError):
        pytest.skip("host denies unprivileged symlinks")

    ledger = HostEffectAttestationLedger(tmp_path / "host-ops")
    ledger._store_file = link
    with pytest.raises(PermissionError, match="redirection"):
        ledger.attest_effect(
            dispatch_id="goal-action:13",
            goal_id="goal:13",
            capability="cap.h",
            outcome="performed",
            attested_by="artemis",
            now=OBSERVED_AT,
        )


def _seal_sample(ledger):
    return ledger.attest_effect(
        dispatch_id="goal-action:private", goal_id="goal:private",
        capability="cap.private", outcome="performed",
        attested_by="isolated-host", now=OBSERVED_AT,
    )


@pytest.mark.parametrize("artifact", ("key", "journal", "tip"))
def test_redirected_host_evidence_is_rejected_before_read(ledger, tmp_path, artifact):
    _seal_sample(ledger)
    path = {
        "key": ledger._key_path, "journal": ledger.store_path,
        "tip": ledger.tip_path,
    }[artifact]
    outside = tmp_path / f"outside-{artifact}"
    outside.write_bytes(path.read_bytes())
    path.unlink()
    try:
        path.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("host denies unprivileged symlinks")
    with pytest.raises(PermissionError, match="redirection"):
        ledger._journal(ledger.store_path)


def test_deleted_journal_cannot_reset_anchored_history(ledger):
    _seal_sample(ledger)
    ledger.store_path.unlink()
    with pytest.raises(HostEffectAttestationError, match="journal.*missing"):
        ledger._journal(ledger.store_path)
    with pytest.raises(HostEffectAttestationError, match="journal.*missing"):
        _seal_sample(ledger)


@pytest.mark.skipif(os.name == "nt", reason="POSIX mode contract")
def test_host_artifacts_are_private_even_with_permissive_umask(ledger):
    previous = os.umask(0)
    try:
        _seal_sample(ledger)
    finally:
        os.umask(previous)
    for path in (ledger._key_path, ledger.store_path, ledger.tip_path):
        assert path.stat().st_mode & 0o077 == 0


@pytest.mark.skipif(os.name == "nt", reason="POSIX mode contract")
@pytest.mark.parametrize("artifact", ("key", "journal", "tip"))
def test_broadened_host_artifact_is_denied_without_repair(ledger, artifact):
    _seal_sample(ledger)
    path = {
        "key": ledger._key_path, "journal": ledger.store_path,
        "tip": ledger.tip_path,
    }[artifact]
    path.chmod(0o644)
    with pytest.raises(PermissionError, match="too broad"):
        ledger._journal(ledger.store_path)
    assert path.stat().st_mode & 0o777 == 0o644


def test_host_attestation_survives_restart_and_accepts_next_dispatch(ledger):
    _seal_sample(ledger)
    reopened = HostEffectAttestationLedger(ledger._root.parent)
    reopened.attest_effect(
        dispatch_id="goal-action:next", goal_id="goal:next",
        capability="cap.next", outcome="absent",
        attested_by="isolated-host", now=_after(OBSERVED_AT, 2),
    )
    rows, _ = reopened._journal(reopened.store_path)
    assert [row["dispatch_id"] for row in rows] == [
        "goal-action:private", "goal-action:next",
    ]


def test_contending_ledger_cannot_overwrite_or_read_partial_transaction(ledger):
    _seal_sample(ledger)
    reopened = HostEffectAttestationLedger(ledger._root.parent)
    before = ledger.store_path.read_bytes()
    with ledger._transaction_lock():
        with pytest.raises(HostEffectAttestationError, match="another live"):
            _seal_sample(reopened)
        with pytest.raises(HostEffectAttestationError, match="another live"):
            reopened.verify_dispatch_outcome("goal-action:private", object())
    assert ledger.store_path.read_bytes() == before
    with pytest.raises(ValueError, match="already independently attested"):
        _seal_sample(reopened)


def test_interrupted_tip_publication_stays_denied_after_restart(ledger, monkeypatch):
    _seal_sample(ledger)

    def crash_before_tip(*args):
        raise OSError("injected host crash before tip publication")

    monkeypatch.setattr(ledger, "_seal_tip", crash_before_tip)
    with pytest.raises(OSError, match="injected host crash"):
        ledger.attest_effect(
            dispatch_id="goal-action:interrupted", goal_id="goal:interrupted",
            capability="cap.interrupted", outcome="performed",
            attested_by="isolated-host", now=_after(OBSERVED_AT, 1),
        )
    reopened = HostEffectAttestationLedger(ledger._root.parent)
    with pytest.raises(HostEffectAttestationError, match="sealed tip"):
        reopened.verify_dispatch_outcome("goal-action:interrupted", object())
    with pytest.raises(HostEffectAttestationError, match="sealed tip"):
        _seal_sample(reopened)


def test_missing_key_is_not_replaced_for_existing_evidence(ledger):
    _seal_sample(ledger)
    ledger._key_path.unlink()
    before = ledger.store_path.read_bytes()
    with pytest.raises(HostEffectAttestationError, match="key is missing"):
        ledger.verify_dispatch_outcome("goal-action:private", object())
    assert not ledger._key_path.exists()
    assert ledger.store_path.read_bytes() == before


def test_full_journal_rejects_append_without_poisoning_history(ledger, monkeypatch):
    from sofia.platform.run import host_effect_attestation

    monkeypatch.setattr(host_effect_attestation, "_MAX_ROWS", 1)
    _seal_sample(ledger)
    before = ledger.store_path.read_bytes(), ledger.tip_path.read_bytes()
    with pytest.raises(HostEffectAttestationError, match="integrity bound"):
        ledger.attest_effect(
            dispatch_id="goal-action:overflow", goal_id="goal:overflow",
            capability="cap.overflow", outcome="performed",
            attested_by="isolated-host", now=_after(OBSERVED_AT, 1),
        )
    assert (ledger.store_path.read_bytes(), ledger.tip_path.read_bytes()) == before
    assert len(ledger._journal(ledger.store_path)[0]) == 1
