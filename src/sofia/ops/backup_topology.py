"""Multi-host/failure-domain backup topology for canonical Sofía state."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
from uuid import uuid4

from sofia.ops.backup import (
    BackupCipher,
    BackupEngine,
    load_backup_key,
    rotate_backups,
)
from sofia.state.model import StateClass, StateKey, StateRecord
from sofia.state.plane import StatePlane


@dataclass(frozen=True, slots=True)
class BackupTarget:
    target_id: str
    host_id: str
    failure_domain: str
    root: Path

    def __post_init__(self) -> None:
        for name, value in (
            ("target_id", self.target_id),
            ("host_id", self.host_id),
            ("failure_domain", self.failure_domain),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonempty")
        if not isinstance(self.root, Path):
            raise TypeError("root must be Path")


@dataclass(frozen=True, slots=True)
class BackupTopologyPolicy:
    minimum_copies: int = 2
    minimum_failure_domains: int = 2
    minimum_hosts: int = 2
    keep_per_target: int = 7

    def __post_init__(self) -> None:
        for name in (
            "minimum_copies",
            "minimum_failure_domains",
            "minimum_hosts",
            "keep_per_target",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True, slots=True)
class BackupCopyResult:
    target_id: str
    host_id: str
    failure_domain: str
    backup_id: str | None
    backup_path: str | None
    manifest_sha256: str | None
    verified: bool
    error_type: str | None = None


@dataclass(frozen=True, slots=True)
class BackupSetResult:
    set_id: str
    created_at: datetime
    source_host_id: str
    source_failure_domain: str
    copies: tuple[BackupCopyResult, ...]
    accepted: bool

    @property
    def verified_copies(self) -> tuple[BackupCopyResult, ...]:
        return tuple(item for item in self.copies if item.verified)


class BackupTopologyError(RuntimeError):
    pass


class BackupTopologyJournal:
    NAMESPACE = "ops-backup-topology"

    def __init__(self, state_plane: StatePlane) -> None:
        if not isinstance(state_plane, StatePlane):
            raise TypeError("state_plane must be StatePlane")
        self.state_plane = state_plane

    @staticmethod
    def _payload(result: BackupSetResult) -> bytes:
        return json.dumps(
            {
                "set_id": result.set_id,
                "created_at": result.created_at.isoformat(),
                "source_host_id": result.source_host_id,
                "source_failure_domain": result.source_failure_domain,
                "accepted": result.accepted,
                "copies": [
                    {
                        "target_id": item.target_id,
                        "host_id": item.host_id,
                        "failure_domain": item.failure_domain,
                        "backup_id": item.backup_id,
                        "backup_path": item.backup_path,
                        "manifest_sha256": item.manifest_sha256,
                        "verified": item.verified,
                        "error_type": item.error_type,
                    }
                    for item in result.copies
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    def append(self, result: BackupSetResult) -> None:
        key = StateKey(self.NAMESPACE, result.set_id)
        if self.state_plane.read(key) is not None:
            raise BackupTopologyError("backup set journal entry already exists")
        self.state_plane.write(
            StateRecord(
                key=key,
                state_class=StateClass.IMMUTABLE_ARTIFACT,
                revision=1,
                value=self._payload(result),
                updated_at=result.created_at,
                source="ops:backup-topology",
            ),
            expected_revision=None,
        )

    def latest(self) -> dict | None:
        rows = self.state_plane.list_namespace(self.NAMESPACE)
        if not rows:
            return None
        latest = max(rows, key=lambda item: (item.updated_at, item.key.key))
        return json.loads(latest.value.decode("utf-8"))


class MultiHostBackupCoordinator:
    """Create and verify independent encrypted copies across declared domains."""

    def __init__(
        self,
        *,
        state_path: Path,
        engine: BackupEngine,
        state_plane: StatePlane,
        targets: tuple[BackupTarget, ...],
        source_host_id: str,
        source_failure_domain: str,
        policy: BackupTopologyPolicy | None = None,
    ) -> None:
        if not isinstance(state_path, Path) or not state_path.is_file():
            raise FileNotFoundError("canonical state database required")
        if not isinstance(engine, BackupEngine):
            raise TypeError("engine must be BackupEngine")
        if not isinstance(state_plane, StatePlane):
            raise TypeError("state_plane must be StatePlane")
        if not targets:
            raise ValueError("at least one backup target is required")
        if len({item.target_id for item in targets}) != len(targets):
            raise ValueError("backup target IDs must be unique")
        if not source_host_id.strip() or not source_failure_domain.strip():
            raise ValueError("source host/failure domain required")
        self.state_path = state_path
        self.engine = engine
        self.state_plane = state_plane
        self.targets = targets
        self.source_host_id = source_host_id
        self.source_failure_domain = source_failure_domain
        self.policy = policy or BackupTopologyPolicy()
        self.journal = BackupTopologyJournal(state_plane)

    def _preflight(self) -> None:
        independent = tuple(
            target
            for target in self.targets
            if target.failure_domain != self.source_failure_domain
        )
        if len(independent) < self.policy.minimum_copies:
            raise BackupTopologyError(
                "insufficient backup targets outside source failure domain"
            )
        if len({item.failure_domain for item in independent}) < (
            self.policy.minimum_failure_domains
        ):
            raise BackupTopologyError(
                "insufficient independent backup failure domains"
            )
        if len({item.host_id for item in independent}) < self.policy.minimum_hosts:
            raise BackupTopologyError(
                "insufficient independent backup hosts"
            )

    def run(self, *, now: datetime | None = None) -> BackupSetResult:
        self._preflight()
        moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        set_id = f"{moment.strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:10]}"
        copies: list[BackupCopyResult] = []

        for target in self.targets:
            if target.failure_domain == self.source_failure_domain:
                copies.append(
                    BackupCopyResult(
                        target.target_id,
                        target.host_id,
                        target.failure_domain,
                        None,
                        None,
                        None,
                        False,
                        "SameFailureDomain",
                    )
                )
                continue
            try:
                backup_dir, evidence = self.engine.create(
                    state_path=self.state_path,
                    destination_root=target.root,
                    source_host_id=self.source_host_id,
                    failure_domain=target.failure_domain,
                    now=moment,
                )
                manifest = self.engine.verify(backup_dir)
                rotate_backups(
                    target.root,
                    keep=self.policy.keep_per_target,
                )
                copies.append(
                    BackupCopyResult(
                        target.target_id,
                        target.host_id,
                        target.failure_domain,
                        evidence.backup_id,
                        str(backup_dir),
                        manifest.digest,
                        True,
                        None,
                    )
                )
            except Exception as exc:
                copies.append(
                    BackupCopyResult(
                        target.target_id,
                        target.host_id,
                        target.failure_domain,
                        None,
                        None,
                        None,
                        False,
                        type(exc).__name__,
                    )
                )

        verified = tuple(item for item in copies if item.verified)
        accepted = (
            len(verified) >= self.policy.minimum_copies
            and len({item.failure_domain for item in verified})
                >= self.policy.minimum_failure_domains
            and len({item.host_id for item in verified})
                >= self.policy.minimum_hosts
        )
        result = BackupSetResult(
            set_id=set_id,
            created_at=moment,
            source_host_id=self.source_host_id,
            source_failure_domain=self.source_failure_domain,
            copies=tuple(copies),
            accepted=accepted,
        )
        self.journal.append(result)
        if not accepted:
            raise BackupTopologyError(
                f"backup topology set {set_id} did not meet policy"
            )
        return result


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = raw.strip().casefold()
    if value in {"1", "true", "on", "yes"}:
        return True
    if value in {"0", "false", "off", "no", ""}:
        return False
    raise ValueError(f"{name} must be boolean")


def backup_topology_enabled() -> bool:
    return _env_bool("SOFIA_BACKUP_TOPOLOGY_ENABLED", False)


def _targets_from_environment(raw: str) -> tuple[BackupTarget, ...]:
    """Parse target_id|host_id|failure_domain|path entries separated by ';'."""
    result: list[BackupTarget] = []
    for item in raw.split(";"):
        item = item.strip()
        if not item:
            continue
        parts = item.split("|", 3)
        if len(parts) != 4:
            raise ValueError(
                "SOFIA_BACKUP_TARGETS entries must be "
                "target_id|host_id|failure_domain|path"
            )
        target_id, host_id, failure_domain, path = (part.strip() for part in parts)
        result.append(
            BackupTarget(
                target_id=target_id,
                host_id=host_id,
                failure_domain=failure_domain,
                root=Path(path),
            )
        )
    return tuple(result)


def create_backup_topology_from_environment(
    *,
    state_path: Path,
    state_plane: StatePlane,
) -> MultiHostBackupCoordinator | None:
    if not backup_topology_enabled():
        return None
    key_path = os.environ.get("SOFIA_BACKUP_KEY_FILE", "").strip()
    source_domain = os.environ.get(
        "SOFIA_BACKUP_SOURCE_FAILURE_DOMAIN",
        "",
    ).strip()
    targets = _targets_from_environment(
        os.environ.get("SOFIA_BACKUP_TARGETS", "")
    )
    if not key_path or not source_domain or not targets:
        raise RuntimeError(
            "backup topology requires key file, source failure domain and targets"
        )
    policy = BackupTopologyPolicy(
        minimum_copies=int(os.environ.get("SOFIA_BACKUP_MIN_COPIES", "2")),
        minimum_failure_domains=int(
            os.environ.get("SOFIA_BACKUP_MIN_FAILURE_DOMAINS", "2")
        ),
        minimum_hosts=int(os.environ.get("SOFIA_BACKUP_MIN_HOSTS", "2")),
        keep_per_target=int(os.environ.get("SOFIA_BACKUP_KEEP_PER_TARGET", "7")),
    )
    return MultiHostBackupCoordinator(
        state_path=state_path,
        engine=BackupEngine(BackupCipher(load_backup_key(Path(key_path)))),
        state_plane=state_plane,
        targets=targets,
        source_host_id=os.environ.get(
            "SOFIA_BACKUP_SOURCE_HOST_ID",
            socket.gethostname(),
        ).strip(),
        source_failure_domain=source_domain,
        policy=policy,
    )


def backup_topology_interval_seconds() -> float:
    value = float(os.environ.get("SOFIA_BACKUP_INTERVAL_SECONDS", "3600"))
    if value < 300:
        raise ValueError("backup topology interval must be at least 300 seconds")
    return value
