"""Authorized Core component installation (G2-B.3).

Core is a separately packaged component (see
:mod:`sofia.platform.verify.component_artifacts`). Installing or replacing it
on a Platform host is a consequential operation that requires explicit
authority at this boundary before any bytes move.

Receipts live in a platform-owned component registry, deliberately separate
from the canonical state database that Core owns: the Platform must never
write Core-owned state in order to record its own installation decisions.
"""

from __future__ import annotations

from hashlib import sha256
import os
import subprocess
import sys
import tempfile
import venv
from importlib.metadata import PathDistribution
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Callable

from sofia.platform.ops.platform_install import InstallAuthority, InstallOperation, InstallOutcome
from sofia.platform.verify.component_artifacts import (
    CORE_ASSET_FILES,
    ComponentArtifactError,
    inspect_wheel,
)

CORE_DISTRIBUTION = "sofia-core"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}")
_VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def _version(value: str) -> tuple[int, int, int]:
    match = _VERSION.fullmatch(value)
    if match is None:
        raise ValueError("component version must be semantic (major.minor.patch)")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


class ComponentSignatureVerifier:
    """Trusted-verifier boundary for component artifact signatures.

    Callers never supply boolean trust. A concrete verifier decides trust
    from an explicit trusted keyring and fails closed: absent keys, wrong
    signers, revoked keys and tampered artifacts are all rejections.
    """

    def verify(self, artifact: CoreComponentArtifact, wheel_path: Path) -> None:
        raise NotImplementedError


class Ed25519ComponentSignatureVerifier(ComponentSignatureVerifier):
    """Verify component artifact digests against a trusted Ed25519 keyring.

    The signed message is the lowercase hex SHA-256 digest of the wheel
    file itself, so the signature binds the exact artifact bytes.
    """

    def __init__(self, trusted_keys: dict[str, Path | bytes]) -> None:
        if not isinstance(trusted_keys, dict) or not trusted_keys:
            raise ValueError("at least one trusted component key is required")
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PublicKey,
        )

        loaded: dict[str, Ed25519PublicKey] = {}
        for key_id, source in trusted_keys.items():
            if not isinstance(key_id, str) or not key_id.strip():
                raise ValueError("component signer key IDs must be nonempty")
            if isinstance(source, Path):
                raw = source.read_bytes()
            elif isinstance(source, bytes):
                raw = source
            else:
                raise TypeError(
                    "trusted component keys must be Path or bytes values"
                )
            key = serialization.load_pem_public_key(raw)
            if not isinstance(key, Ed25519PublicKey):
                raise TypeError(
                    f"trusted component key {key_id!r} is not Ed25519"
                )
            loaded[key_id] = key
        self._keys = loaded

    def verify(self, artifact: CoreComponentArtifact, wheel_path: Path) -> None:
        import base64

        from cryptography.exceptions import InvalidSignature

        key = self._keys.get(artifact.signer_key_id)
        if key is None:
            raise CoreComponentInstallError(
                f"component signer {artifact.signer_key_id!r} is not trusted"
            )
        try:
            signature = base64.b64decode(artifact.signature_b64, validate=True)
        except (ValueError, TypeError) as error:
            raise CoreComponentInstallError(
                "component signature is not valid base64"
            ) from error
        try:
            key.verify(signature, artifact.sha256.encode("ascii"))
        except InvalidSignature:
            raise CoreComponentInstallError(
                "component signature does not verify against the trusted keyring"
            ) from None


class CoreComponentInstallError(RuntimeError):
    """Raised when a Core component artifact or its authority is rejected."""


@dataclass(frozen=True, slots=True)
class CoreComponentArtifact:
    """A reviewed Core component artifact candidate for installation.

    Trust is never expressed here: ``signature_b64`` is opaque evidence that
    the configured trusted verifier must accept before any bytes move.
    """

    artifact_id: str
    version: str
    sha256: str
    signature_b64: str
    signer_key_id: str
    source: str

    def __post_init__(self) -> None:
        for value, label in (
            (self.artifact_id, "artifact_id"), (self.signer_key_id, "signer_key_id"),
            (self.source, "source"),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > 500:
                raise ValueError(f"{label} must be bounded text")
        if _SHA256.fullmatch(self.sha256) is None:
            raise ValueError("component artifact requires lowercase SHA-256")
        if (
            not isinstance(self.signature_b64, str)
            or not self.signature_b64.strip()
            or len(self.signature_b64) > 2000
        ):
            raise ValueError("component artifact requires bounded signature evidence")
        _version(self.version)


@dataclass(frozen=True, slots=True)
class CoreComponentReceipt:
    receipt_id: str
    artifact_id: str
    version: str
    operation: InstallOperation
    outcome: InstallOutcome
    artifact_sha256: str
    authority: InstallAuthority
    approval_id: str | None
    health_verified: bool
    installed_at: datetime
    detail: str = ""

    def __post_init__(self) -> None:
        if _ID.fullmatch(self.receipt_id) is None:
            raise ValueError("receipt_id must be canonical")
        if self.installed_at.tzinfo is None or self.installed_at.utcoffset() is None:
            raise ValueError("installed_at must be timezone-aware")
        if _SHA256.fullmatch(self.artifact_sha256) is None:
            raise ValueError("receipt requires artifact SHA-256")
        if self.outcome is InstallOutcome.SUCCEEDED and not (
            self.signature_authorized()
            and self.health_verified
        ):
            raise ValueError("successful install requires authority and health verification")

    def signature_authorized(self) -> bool:
        return self.authority is not InstallAuthority.NONE and (
            self.authority is not InstallAuthority.OPERATOR_APPROVED
            or bool(self.approval_id)
        )


@dataclass(frozen=True, slots=True)
class CoreComponentInstallAttempt:
    """Durable record of an attempted stage, including interrupted attempts."""

    attempt_id: str
    artifact_id: str
    version: str
    artifact_sha256: str
    operation: InstallOperation
    authority: InstallAuthority
    approval_id: str | None
    started_at: datetime
    outcome: InstallOutcome | None
    completed_at: datetime | None
    detail: str


class CoreComponentRegistry:
    """Platform-local record of installed Core components.

    This registry is a dedicated Platform-owned SQLite file. It is never the
    canonical state database: recording a Platform installation decision must
    not require writing Core-owned state.
    """

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        if self.path.name == "sofia.db":
            raise ValueError("Core component registry must not use the canonical state database")
        with closing(self._connect()) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS core_component_receipt (
                    receipt_id TEXT PRIMARY KEY,
                    artifact_id TEXT NOT NULL UNIQUE,
                    version TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    artifact_sha256 TEXT NOT NULL,
                    authority TEXT NOT NULL,
                    approval_id TEXT,
                    health_verified INTEGER NOT NULL,
                    installed_at TEXT NOT NULL,
                    detail TEXT NOT NULL
                )
            """)
            # Preserve all historical decisions; the single current receipt
            # is a compatibility projection, not an audit log.
            db.execute("""
                CREATE TABLE IF NOT EXISTS core_component_receipt_history (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    receipt_id TEXT NOT NULL UNIQUE,
                    artifact_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    artifact_sha256 TEXT NOT NULL,
                    authority TEXT NOT NULL,
                    approval_id TEXT,
                    health_verified INTEGER NOT NULL,
                    installed_at TEXT NOT NULL,
                    detail TEXT NOT NULL
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS core_component_install_attempt (
                    attempt_id TEXT PRIMARY KEY,
                    artifact_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    artifact_sha256 TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    authority TEXT NOT NULL,
                    approval_id TEXT,
                    started_at TEXT NOT NULL,
                    outcome TEXT,
                    completed_at TEXT,
                    detail TEXT NOT NULL DEFAULT ''
                )
            """)
            # Only one unresolved physical stage per identity is permitted.
            # A crash leaves a pending record that requires review, not an
            # implicit retry which may race an installation in progress.
            db.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS
                    core_component_one_unresolved_stage
                ON core_component_install_attempt(artifact_id)
                WHERE outcome IS NULL
            """)
            # A previous release kept only the current row. Upgrade it once,
            # without rewriting earlier history on subsequent startups.
            db.execute("""
                INSERT OR IGNORE INTO core_component_receipt_history(
                    receipt_id, artifact_id, version, operation, outcome,
                    artifact_sha256, authority, approval_id, health_verified,
                    installed_at, detail
                )
                SELECT receipt_id, artifact_id, version, operation, outcome,
                    artifact_sha256, authority, approval_id, health_verified,
                    installed_at, detail
                FROM core_component_receipt
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _receipt_from_row(row: sqlite3.Row) -> CoreComponentReceipt:
        return CoreComponentReceipt(
            receipt_id=row["receipt_id"], artifact_id=row["artifact_id"],
            version=row["version"], operation=InstallOperation(row["operation"]),
            outcome=InstallOutcome(row["outcome"]),
            artifact_sha256=row["artifact_sha256"],
            authority=InstallAuthority(row["authority"]),
            approval_id=row["approval_id"],
            health_verified=bool(row["health_verified"]),
            installed_at=datetime.fromisoformat(row["installed_at"]),
            detail=row["detail"],
        )

    def begin_attempt(
        self,
        artifact: CoreComponentArtifact,
        operation: InstallOperation,
        authority: InstallAuthority,
        approval_id: str | None,
    ) -> str:
        """Durably reserve a stage before the first installation side effect."""
        attempt_id = f"core-attempt-{uuid4().hex}"
        with closing(self._connect()) as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                db.execute("""
                    INSERT INTO core_component_install_attempt(
                        attempt_id, artifact_id, version, artifact_sha256,
                        operation, authority, approval_id, started_at
                    ) VALUES (?,?,?,?,?,?,?,?)
                """, (
                    attempt_id, artifact.artifact_id, artifact.version,
                    artifact.sha256, operation.value, authority.value,
                    approval_id, datetime.now(timezone.utc).isoformat(),
                ))
                db.commit()
            except sqlite3.IntegrityError as error:
                db.rollback()
                raise CoreComponentInstallError(
                    "unresolved Core installation attempt requires reconciliation"
                ) from error
        return attempt_id

    def pending_attempts(
        self, artifact_id: str = CORE_DISTRIBUTION
    ) -> tuple[CoreComponentInstallAttempt, ...]:
        """Read-only inspection of interrupted or concurrently staged work."""
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM core_component_install_attempt "
                "WHERE artifact_id=? AND outcome IS NULL ORDER BY started_at, attempt_id",
                (artifact_id,),
            ).fetchall()
        return tuple(self._attempt_from_row(row) for row in rows)

    @staticmethod
    def _attempt_from_row(row: sqlite3.Row) -> CoreComponentInstallAttempt:
        return CoreComponentInstallAttempt(
            attempt_id=row["attempt_id"], artifact_id=row["artifact_id"],
            version=row["version"], artifact_sha256=row["artifact_sha256"],
            operation=InstallOperation(row["operation"]),
            authority=InstallAuthority(row["authority"]),
            approval_id=row["approval_id"],
            started_at=datetime.fromisoformat(row["started_at"]),
            outcome=InstallOutcome(row["outcome"]) if row["outcome"] else None,
            completed_at=(
                datetime.fromisoformat(row["completed_at"])
                if row["completed_at"] else None
            ),
            detail=row["detail"],
        )

    def attempts(
        self, artifact_id: str = CORE_DISTRIBUTION
    ) -> tuple[CoreComponentInstallAttempt, ...]:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM core_component_install_attempt "
                "WHERE artifact_id=? ORDER BY started_at, attempt_id",
                (artifact_id,),
            ).fetchall()
        return tuple(self._attempt_from_row(row) for row in rows)

    def finish_failed_attempt(self, attempt_id: str, detail: str) -> None:
        """Record a handled failure; unknown/crashed attempts remain pending."""
        with closing(self._connect()) as db, db:
            changed = db.execute(
                "UPDATE core_component_install_attempt "
                "SET outcome=?, completed_at=?, detail=? "
                "WHERE attempt_id=? AND outcome IS NULL",
                (
                    InstallOutcome.FAILED.value,
                    datetime.now(timezone.utc).isoformat(),
                    str(detail)[:2000], attempt_id,
                ),
            )
            if changed.rowcount != 1:
                raise CoreComponentInstallError(
                    "Core installation attempt is not pending"
                )

    def record(self, receipt: CoreComponentReceipt, *, attempt_id: str | None = None) -> None:
        if not isinstance(receipt, CoreComponentReceipt):
            raise TypeError("CoreComponentReceipt required")
        values = (
            receipt.receipt_id, receipt.artifact_id, receipt.version,
            receipt.operation.value, receipt.outcome.value,
            receipt.artifact_sha256, receipt.authority.value,
            receipt.approval_id, int(receipt.health_verified),
            receipt.installed_at.astimezone(timezone.utc).isoformat(),
            receipt.detail[:2000],
        )
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                if attempt_id is not None:
                    pending = db.execute(
                        "SELECT * FROM core_component_install_attempt "
                        "WHERE attempt_id=? AND outcome IS NULL",
                        (attempt_id,),
                    ).fetchone()
                    if (
                        pending is None
                        or pending["artifact_id"] != receipt.artifact_id
                        or pending["version"] != receipt.version
                        or pending["artifact_sha256"] != receipt.artifact_sha256
                        or pending["operation"] != receipt.operation.value
                        or pending["authority"] != receipt.authority.value
                        or pending["approval_id"] != receipt.approval_id
                        or receipt.outcome is not InstallOutcome.SUCCEEDED
                    ):
                        raise CoreComponentInstallError(
                            "Core install receipt does not match pending stage"
                        )
                db.execute("""
                    INSERT INTO core_component_receipt_history(
                        receipt_id, artifact_id, version, operation, outcome,
                        artifact_sha256, authority, approval_id, health_verified,
                        installed_at, detail
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """, values)
                db.execute("""
                    INSERT INTO core_component_receipt(
                        receipt_id, artifact_id, version, operation, outcome,
                        artifact_sha256, authority, approval_id, health_verified,
                        installed_at, detail
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(artifact_id) DO UPDATE SET
                        receipt_id=excluded.receipt_id,
                        version=excluded.version,
                        operation=excluded.operation,
                        outcome=excluded.outcome,
                        artifact_sha256=excluded.artifact_sha256,
                        authority=excluded.authority,
                        approval_id=excluded.approval_id,
                        health_verified=excluded.health_verified,
                        installed_at=excluded.installed_at,
                        detail=excluded.detail
                """, values)
                if attempt_id is not None:
                    changed = db.execute(
                        "UPDATE core_component_install_attempt "
                        "SET outcome=?, completed_at=?, detail=? "
                        "WHERE attempt_id=? AND outcome IS NULL",
                        (
                            InstallOutcome.SUCCEEDED.value,
                            receipt.installed_at.astimezone(timezone.utc).isoformat(),
                            receipt.detail[:2000], attempt_id,
                        ),
                    )
                    if changed.rowcount != 1:
                        raise CoreComponentInstallError(
                            "Core install stage changed before receipt commit"
                        )
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def installed(self, artifact_id: str = CORE_DISTRIBUTION) -> CoreComponentReceipt | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM core_component_receipt WHERE artifact_id=?",
                (artifact_id,),
            ).fetchone()
        return None if row is None else self._receipt_from_row(row)

    def history(self, artifact_id: str = CORE_DISTRIBUTION) -> tuple[CoreComponentReceipt, ...]:
        """Return immutable, insertion-ordered platform install evidence."""
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM core_component_receipt_history "
                "WHERE artifact_id=? ORDER BY sequence",
                (artifact_id,),
            ).fetchall()
        return tuple(self._receipt_from_row(row) for row in rows)


def verify_core_component_content(wheel_path: Path) -> None:
    """Reject any Core wheel that violates the component content contract."""

    report = inspect_wheel(wheel_path, CORE_DISTRIBUTION)
    if report.contains("sofia/platform") or report.contains("sofia/sdk"):
        raise CoreComponentInstallError(
            "Core component wheel must not contain Platform or SDK files"
        )
    missing = sorted(set(CORE_ASSET_FILES) - set(report.files))
    if missing:
        raise CoreComponentInstallError(f"Core component wheel is missing assets: {missing}")
    required = ("sofia-platform", "sofia-sdk")
    present = {dep.split(";")[0].strip() for dep in report.requires_dist}
    absent = sorted(set(required) - present)
    if absent:
        raise CoreComponentInstallError(
            f"Core component is incompatible with this Platform host; missing dependencies: {absent}"
        )


# This verifier must be backed by the existing independently trusted owner
# approval or signed standing-policy authority. An approval ID alone is never
# permission, and this component is not an authorization database.
CoreInstallAuthorizer = Callable[
    [InstallAuthority, str | None, CoreComponentArtifact, InstallOperation], bool
]


class CoreComponentInstaller:
    """Install or replace the Core component under explicit authority."""

    def __init__(
        self,
        registry: CoreComponentRegistry,
        signature_verifier: ComponentSignatureVerifier,
        *,
        installation_root: Path | None = None,
        authorization_check: CoreInstallAuthorizer | None = None,
    ) -> None:
        if authorization_check is not None and not callable(authorization_check):
            raise TypeError("authorization_check must be a trusted callable")
        if not isinstance(signature_verifier, ComponentSignatureVerifier):
            raise TypeError(
                "Core component installation requires a trusted signature verifier"
            )
        self.registry = registry
        self.signature_verifier = signature_verifier
        self.installation_root = Path(installation_root).resolve() if installation_root else None
        self.authorization_check = authorization_check

    def execute(
        self,
        artifact: CoreComponentArtifact,
        wheel_path: Path,
        *,
        authority: InstallAuthority,
        approval_id: str | None = None,
        operation: InstallOperation = InstallOperation.INSTALL,
    ) -> CoreComponentReceipt:
        if not isinstance(artifact, CoreComponentArtifact):
            raise TypeError("CoreComponentArtifact required")
        if artifact.artifact_id != CORE_DISTRIBUTION:
            raise CoreComponentInstallError(
                "Core component artifact ID must be sofia-core"
            )
        if not isinstance(authority, InstallAuthority):
            raise TypeError("InstallAuthority required")
        if not isinstance(operation, InstallOperation):
            raise TypeError("InstallOperation required")
        if authority is InstallAuthority.NONE:
            raise PermissionError("Core component installation requires explicit authority")
        if authority is InstallAuthority.OPERATOR_APPROVED and not approval_id:
            raise PermissionError("operator-approved Core installation requires approval_id")
        existing = self.registry.installed(artifact.artifact_id)
        if (
            existing is not None
            and existing.outcome is InstallOutcome.SUCCEEDED
            and operation is not InstallOperation.ROLLBACK
            and _version(artifact.version) < _version(existing.version)
        ):
            raise CoreComponentInstallError(
                f"Core downgrade from {existing.version} to {artifact.version} "
                "requires rollback authority"
            )
        wheel_path = Path(wheel_path)
        if not wheel_path.is_file() or wheel_path.is_symlink():
            raise FileNotFoundError(wheel_path)
        observed_digest = sha256(wheel_path.read_bytes()).hexdigest()
        if observed_digest != artifact.sha256:
            raise CoreComponentInstallError(
                "Core component artifact digest does not match the wheel file"
            )
        self.signature_verifier.verify(artifact, wheel_path)
        try:
            verify_core_component_content(wheel_path)
            wheel_metadata = inspect_wheel(wheel_path, CORE_DISTRIBUTION)
        except ComponentArtifactError as error:
            raise CoreComponentInstallError(str(error)) from error
        if wheel_metadata.version != artifact.version:
            raise CoreComponentInstallError(
                "Core artifact declared version does not match signed wheel metadata"
            )
        if operation is InstallOperation.ROLLBACK:
            # Downgrade authority is not permission to install an unrelated
            # older wheel. A rollback target must be exact previously
            # attested bytes from this Platform's own install history.
            history = self.registry.history(artifact.artifact_id)
            if not any(
                entry.outcome is InstallOutcome.SUCCEEDED
                and entry.version == artifact.version
                and entry.artifact_sha256 == artifact.sha256
                and entry.operation in (
                    InstallOperation.INSTALL,
                    InstallOperation.UPDATE,
                    InstallOperation.REPAIR,
                    InstallOperation.ROLLBACK,
                )
                for entry in history
            ):
                raise CoreComponentInstallError(
                    "rollback requires a previously verified Core artifact"
                )
            if existing is None or existing.outcome is not InstallOutcome.SUCCEEDED:
                raise CoreComponentInstallError(
                    "rollback requires a currently recorded Core installation"
                )
        if self.installation_root is None:
            raise CoreComponentInstallError(
                "installation_root is required; a health probe is not a physical install"
            )
        # Caller-supplied enum values and arbitrary approval IDs are not
        # independent proof. Only a trusted approval/policy consumer can
        # authorize this exact artifact and operation.
        if self.authorization_check is None:
            raise PermissionError("trusted Core installation authorizer is required")
        if self.authorization_check(authority, approval_id, artifact, operation) is not True:
            raise PermissionError("Core component installation authority denied")
        health_verified = self._verify_health(wheel_path)
        if not health_verified:
            raise CoreComponentInstallError("Core component failed the health probe")
        attempt_id = self.registry.begin_attempt(
            artifact, operation, authority, approval_id
        )
        try:
            installed_path = self._stage_verified_install(wheel_path, artifact)
        except Exception as error:
            # Python/SystemExit or a process crash leaves a pending row for
            # explicit restart reconciliation instead of a false success.
            self.registry.finish_failed_attempt(attempt_id, str(error))
            raise
        receipt = CoreComponentReceipt(
            receipt_id=f"core-install-{artifact.version}-{uuid4().hex}",
            artifact_id=artifact.artifact_id,
            version=artifact.version,
            operation=operation,
            outcome=InstallOutcome.SUCCEEDED,
            artifact_sha256=artifact.sha256,
            authority=authority,
            approval_id=approval_id,
            health_verified=health_verified,
            installed_at=datetime.now(timezone.utc),
            detail=f"physically installed and independently verified in {installed_path.name}",
        )
        self.registry.record(receipt, attempt_id=attempt_id)
        return receipt

    def verify_installed(
        self,
        artifact: CoreComponentArtifact,
        wheel_path: Path,
    ) -> CoreComponentReceipt:
        """Reconcile a previous success receipt with current signed disk bytes.

        This is read-only and never authorizes activation. Call it after
        restart or before handing a staged Core path to the worker controller.
        An old successful receipt cannot stand in for missing or modified files.
        """
        if not isinstance(artifact, CoreComponentArtifact):
            raise TypeError("CoreComponentArtifact required")
        if artifact.artifact_id != CORE_DISTRIBUTION:
            raise CoreComponentInstallError("Core component artifact ID must be sofia-core")
        receipt = self.registry.installed(artifact.artifact_id)
        if (
            receipt is None
            or receipt.outcome is not InstallOutcome.SUCCEEDED
            or receipt.version != artifact.version
            or receipt.artifact_sha256 != artifact.sha256
        ):
            raise CoreComponentInstallError(
                "current Core receipt does not match the requested installed artifact"
            )
        wheel_path = Path(wheel_path)
        if not wheel_path.is_file() or wheel_path.is_symlink():
            raise FileNotFoundError(wheel_path)
        if sha256(wheel_path.read_bytes()).hexdigest() != artifact.sha256:
            raise CoreComponentInstallError("Core install artifact digest mismatch")
        self.signature_verifier.verify(artifact, wheel_path)
        try:
            wheel_metadata = inspect_wheel(wheel_path, CORE_DISTRIBUTION)
            verify_core_component_content(wheel_path)
        except ComponentArtifactError as error:
            raise CoreComponentInstallError(str(error)) from error
        if wheel_metadata.version != artifact.version:
            raise CoreComponentInstallError("Core install artifact version mismatch")
        if self.installation_root is None:
            raise CoreComponentInstallError("Core installation root is not configured")
        destination = self.installation_root / f"core-{artifact.version}-{artifact.sha256}"
        if destination.is_symlink() or not destination.is_dir():
            raise CoreComponentInstallError(
                "previously recorded Core installation is absent or redirected"
            )
        self._verify_installed_bytes(destination, artifact, wheel_path)
        return receipt

    def _stage_verified_install(
        self, wheel_path: Path, artifact: CoreComponentArtifact
    ) -> Path:
        """Install into a quarantined venv, verify RECORD bytes, then publish.

        This prepares immutable Core bytes only. A worker controller must
        separately authorize activation and canonical-state ownership.
        """
        root = self.installation_root
        assert root is not None
        root.mkdir(parents=True, exist_ok=True)
        destination = root / f"core-{artifact.version}-{artifact.sha256}"
        if destination.is_symlink():
            raise CoreComponentInstallError("Core installation destination is a symlink")
        with tempfile.TemporaryDirectory(prefix=".core-stage-", dir=root) as temporary:
            staging = Path(temporary) / "environment"
            venv.EnvBuilder(with_pip=True).create(staging)
            python = staging / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
            try:
                subprocess.run(
                    [str(python), "-m", "pip", "install", "--no-index", "--no-deps",
                     "--disable-pip-version-check", str(wheel_path.resolve())],
                    check=True, capture_output=True, text=True, timeout=600,
                )
                self._verify_installed_bytes(staging, artifact, wheel_path)
            except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                raise CoreComponentInstallError("physical Core installation failed") from exc
            # Stage publication: old environments remain available for rollback.
            # An already-published candidate is never silently overwritten.
            if destination.exists():
                self._verify_installed_bytes(destination, artifact, wheel_path)
                return destination
            os.replace(staging, destination)
        try:
            self._verify_installed_bytes(destination, artifact, wheel_path)
        except Exception:
            # Do not retain or attest a partially published environment.
            import shutil
            shutil.rmtree(destination, ignore_errors=True)
            raise
        return destination

    @staticmethod
    def _verify_installed_bytes(root: Path, artifact: CoreComponentArtifact, wheel: Path) -> None:
        """Check installed dist metadata and every wheel-owned regular file."""
        import zipfile
        site = root / "Lib/site-packages" if sys.platform == "win32" else next(
            (root / "lib").glob("python*/site-packages"), None
        )
        if site is None:
            raise CoreComponentInstallError("installed Core site-packages is missing")
        with zipfile.ZipFile(wheel) as archive:
            entries = {name: archive.read(name) for name in archive.namelist()
                       if not name.endswith("/") and not name.endswith(".dist-info/RECORD")}
        matching = list(site.glob("sofia_core-*.dist-info"))
        if len(matching) != 1:
            raise CoreComponentInstallError("installed Core distribution metadata missing or ambiguous")
        metadata = PathDistribution(matching[0]).metadata
        if metadata.get("Name", "").lower().replace("_", "-") != CORE_DISTRIBUTION or metadata.get("Version") != artifact.version:
            raise CoreComponentInstallError("installed Core distribution identity/version mismatch")
        for name, expected in entries.items():
            location = site / name
            if location.is_symlink() or not location.is_file() or sha256(location.read_bytes()).digest() != sha256(expected).digest():
                raise CoreComponentInstallError(f"installed Core bytes mismatch: {name}")

    def _verify_health(self, wheel_path: Path) -> bool:
        """Import the candidate Core surface against the live Platform.

        The candidate wheel is overlaid onto a copy of the currently
        installed ``sofia`` package, mirroring pip's in-place install
        semantics: the probe imports the ARTIFACT's Core with the live
        Platform and SDK, never the checkout source tree.
        """

        import os
        import shutil
        import subprocess
        import sys
        import tempfile
        import zipfile

        import sofia

        package_root = Path(sofia.__file__).resolve().parent
        probe = (
            "import sys\n"
            "import sofia.core.constitution\n"
            "import sofia.core.identity.model\n"
            "import sofia.sdk.cognition_model\n"
            "assert sofia.core.identity.model.IdentityBootstrapMode is not None\n"
            "core_modules = [name for name in sys.modules if name.startswith('sofia.core')]\n"
            "assert core_modules, core_modules\n"
        )
        env = {key: value for key, value in os.environ.items() if not key.startswith("SOFIA_")}
        with tempfile.TemporaryDirectory(prefix="sofia-core-health-") as tmp:
            site_dir = Path(tmp) / "site"
            shutil.copytree(package_root, site_dir / "sofia")
            with zipfile.ZipFile(wheel_path) as archive:
                archive.extractall(site_dir)
            env["PYTHONPATH"] = str(site_dir)
            completed = subprocess.run(
                [sys.executable, "-c", probe],
                capture_output=True, text=True, env=env, timeout=120,
            )
        return completed.returncode == 0
