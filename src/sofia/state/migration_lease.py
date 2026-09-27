from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sofia.state.json_repository import JsonStateRepository
from sofia.state.namespaces import STATE_MIGRATION_LEASE
from sofia.state.plane import StatePlane, StatePlaneConflictError


class MigrationLeaseBusy(RuntimeError):
    """Another migration owner holds the current lease."""


class MigrationLeaseLost(RuntimeError):
    """The caller no longer owns the migration lease/fencing token."""


def _utc(value: datetime) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("migration lease time must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class MigrationLease:
    owner_id: str
    fencing_token: int
    acquired_at: datetime
    expires_at: datetime
    revision: int

    def __post_init__(self) -> None:
        if not isinstance(self.owner_id, str) or not self.owner_id.strip():
            raise ValueError("owner_id must be nonempty")
        if type(self.fencing_token) is not int or self.fencing_token < 1:
            raise ValueError("fencing_token must be positive")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be positive")
        _utc(self.acquired_at)
        _utc(self.expires_at)
        if self.expires_at <= self.acquired_at:
            raise ValueError("migration lease must expire after acquisition")


class MigrationLeaseStore:
    """Backend-neutral single-writer lease for reviewed schema migrations."""

    KEY = "global"

    def __init__(self, state_plane: StatePlane) -> None:
        if not isinstance(state_plane, StatePlane):
            raise TypeError("state_plane must be a StatePlane")
        self._repo = JsonStateRepository(
            state_plane,
            STATE_MIGRATION_LEASE,
        )
        self._state_plane = state_plane

    @staticmethod
    def _owner(value: str) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > 160:
            raise ValueError("migration owner_id must be 1-160 characters")
        return value.strip()

    @staticmethod
    def _ttl(value: timedelta) -> timedelta:
        if (
            not isinstance(value, timedelta)
            or value <= timedelta(0)
            or value > timedelta(hours=1)
        ):
            raise ValueError("migration lease TTL must be in (0, 1 hour]")
        return value

    @staticmethod
    def _decode(value: dict, revision: int) -> MigrationLease:
        return MigrationLease(
            owner_id=value["owner_id"],
            fencing_token=int(value["fencing_token"]),
            acquired_at=datetime.fromisoformat(value["acquired_at"]),
            expires_at=datetime.fromisoformat(value["expires_at"]),
            revision=revision,
        )

    @staticmethod
    def _value(
        *,
        owner_id: str,
        fencing_token: int,
        acquired_at: datetime,
        expires_at: datetime,
    ) -> dict:
        return {
            "owner_id": owner_id,
            "fencing_token": fencing_token,
            "acquired_at": acquired_at.isoformat(),
            "expires_at": expires_at.isoformat(),
        }

    def current(self) -> MigrationLease | None:
        item = self._repo.get(self.KEY)
        if item is None:
            return None
        value, record = item
        return self._decode(value, record.revision)

    def acquire(
        self,
        *,
        owner_id: str,
        now: datetime,
        ttl: timedelta = timedelta(minutes=5),
    ) -> MigrationLease:
        owner = self._owner(owner_id)
        current_time = _utc(now)
        lease_ttl = self._ttl(ttl)
        existing = self._repo.get(self.KEY)

        if existing is None:
            value = self._value(
                owner_id=owner,
                fencing_token=1,
                acquired_at=current_time,
                expires_at=current_time + lease_ttl,
            )
            try:
                record = self._repo.create(
                    self.KEY,
                    value,
                    updated_at=current_time,
                    source=f"migration-lease:{owner}",
                )
            except StatePlaneConflictError as exc:
                raise MigrationLeaseBusy(
                    "migration lease was acquired concurrently"
                ) from exc
            return self._decode(value, record.revision)

        value, record = existing
        lease = self._decode(value, record.revision)
        if lease.expires_at > current_time and lease.owner_id != owner:
            raise MigrationLeaseBusy(
                f"migration lease is held by {lease.owner_id}"
            )

        same_live_owner = (
            lease.owner_id == owner and lease.expires_at > current_time
        )
        fencing_token = (
            lease.fencing_token
            if same_live_owner
            else lease.fencing_token + 1
        )
        acquired_at = (
            lease.acquired_at if same_live_owner else current_time
        )
        replacement = self._value(
            owner_id=owner,
            fencing_token=fencing_token,
            acquired_at=acquired_at,
            expires_at=current_time + lease_ttl,
        )
        try:
            updated = self._repo.compare_and_put(
                self.KEY,
                replacement,
                expected_revision=record.revision,
                updated_at=current_time,
                source=f"migration-lease:{owner}",
            )
        except StatePlaneConflictError as exc:
            raise MigrationLeaseBusy(
                "migration lease changed during acquisition"
            ) from exc
        return self._decode(replacement, updated.revision)

    def release(
        self,
        lease: MigrationLease,
        *,
        now: datetime,
    ) -> None:
        if not isinstance(lease, MigrationLease):
            raise TypeError("lease must be a MigrationLease")
        current_time = _utc(now)
        existing = self._repo.get(self.KEY)
        if existing is None:
            raise MigrationLeaseLost("migration lease no longer exists")
        value, record = existing
        current = self._decode(value, record.revision)
        if (
            current.owner_id != lease.owner_id
            or current.fencing_token != lease.fencing_token
        ):
            raise MigrationLeaseLost(
                "migration lease ownership/fencing token changed"
            )
        # Expiration does not make a stale owner authoritative again.
        if current.expires_at < current_time:
            raise MigrationLeaseLost("migration lease expired")
        self._state_plane.delete(
            record.key,
            expected_revision=record.revision,
        )
