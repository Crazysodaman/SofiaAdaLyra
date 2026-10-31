"""Independent host-owned GOALS effect attestation ledger contracts."""

from datetime import datetime, timedelta, timezone
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
    with pytest.raises(RuntimeError):
        ledger.attest_effect(
            dispatch_id="goal-action:13",
            goal_id="goal:13",
            capability="cap.h",
            outcome="performed",
            attested_by="artemis",
            now=OBSERVED_AT,
        )
