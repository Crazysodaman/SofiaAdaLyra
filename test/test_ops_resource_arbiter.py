from datetime import datetime, timedelta, timezone

import pytest

from sofia.platform.ops import ResourceArbiter, ResourceObservation


NOW = datetime(2026, 10, 22, 23, tzinfo=timezone.utc)


def observation(*, exclusive=False, observed_at=NOW):
    return ResourceObservation(
        "gpu:venus:0" if not exclusive else "device:camera:0",
        "venus", "gpu" if not exclusive else "camera",
        (("units", 1), ("vram_bytes", 16 << 30)), observed_at, exclusive,
    )


def arbiter(path, *, allowed=True):
    return ResourceArbiter(
        path,
        authorizer=lambda principal, audience, resource, authority, now: allowed,
    )


def test_capacity_reservation_is_durable_idempotent_and_bounded(canonical_state_path):
    service = arbiter(canonical_state_path)
    kwargs = dict(
        reservation_id="reservation:one", workload_id="workload:model",
        principal_id="principal:sofia", audience="private:sparks",
        amounts=(("vram_bytes", 8 << 30),), authority_ref="grant:one",
        now=NOW, expires_at=NOW + timedelta(minutes=10),
    )
    first = service.reserve(observation(), **kwargs)
    again = arbiter(canonical_state_path).reserve(observation(), **kwargs)
    assert again == first
    with pytest.raises(RuntimeError, match="already reserved"):
        service.reserve(
            observation(), reservation_id="reservation:two",
            workload_id="workload:other", principal_id="principal:sofia",
            audience="private:sparks", amounts=(("vram_bytes", 9 << 30),),
            authority_ref="grant:two", now=NOW,
            expires_at=NOW + timedelta(minutes=10),
        )


def test_unauthorized_or_stale_resource_reservation_fails_closed(canonical_state_path):
    kwargs = dict(
        reservation_id="reservation:one", workload_id="workload:model",
        principal_id="principal:sofia", audience="private:sparks",
        amounts=(("vram_bytes", 1),), authority_ref="grant:one",
        now=NOW, expires_at=NOW + timedelta(minutes=1),
    )
    with pytest.raises(PermissionError):
        arbiter(canonical_state_path, allowed=False).reserve(observation(), **kwargs)
    with pytest.raises(RuntimeError, match="stale"):
        arbiter(canonical_state_path).reserve(
            observation(observed_at=NOW - timedelta(minutes=3)), **kwargs,
        )


def test_background_work_yields_to_interactive_pressure(canonical_state_path):
    with pytest.raises(RuntimeError, match="foreground"):
        arbiter(canonical_state_path).reserve(
            observation(), reservation_id="reservation:one",
            workload_id="workload:background", principal_id="principal:sofia",
            audience="private:sparks", amounts=(("vram_bytes", 1),),
            authority_ref="grant:one", now=NOW,
            expires_at=NOW + timedelta(minutes=1), background=True,
            interactive_pressure=1,
        )


def test_exclusive_device_lease_survives_restart_and_requires_exact_release_owner(
    canonical_state_path,
):
    service = arbiter(canonical_state_path)
    lease = service.acquire_device_lease(
        observation(exclusive=True), reservation_id="lease:camera",
        workload_id="workload:vision", principal_id="principal:sofia",
        audience="private:sparks", authority_ref="grant:camera", now=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    restarted = arbiter(canonical_state_path)
    assert restarted.inspect(lease.reservation_id).status == "active"
    with pytest.raises(PermissionError):
        restarted.release_device_lease(
            lease.reservation_id, principal_id="principal:other",
            authority_ref="grant:camera", now=NOW,
        )
    released = restarted.release_device_lease(
        lease.reservation_id, principal_id="principal:sofia",
        authority_ref="grant:camera", now=NOW,
    )
    assert released.status == "released"


def test_revoked_grant_cannot_strand_exactly_owned_resource_cleanup(
    canonical_state_path,
):
    allowed = True

    def authorize(principal, audience, resource, authority, now):
        return allowed

    service = ResourceArbiter(canonical_state_path, authorizer=authorize)
    lease = service.acquire_device_lease(
        observation(exclusive=True), reservation_id="lease:cleanup",
        workload_id="workload:vision", principal_id="principal:sofia",
        audience="private:sparks", authority_ref="grant:cleanup", now=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    allowed = False

    released = service.release_device_lease(
        lease.reservation_id, principal_id="principal:sofia",
        authority_ref="grant:cleanup", now=NOW + timedelta(seconds=1),
    )

    assert released.status == "released"
