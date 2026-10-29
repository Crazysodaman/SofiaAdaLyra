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

import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

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


class CoreComponentInstallError(RuntimeError):
    """Raised when a Core component artifact or its authority is rejected."""


@dataclass(frozen=True, slots=True)
class CoreComponentArtifact:
    """A reviewed Core component artifact candidate for installation."""

    artifact_id: str
    version: str
    sha256: str
    signature_verified: bool
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
        if self.signature_verified is not True:
            raise CoreComponentInstallError(
                "Core component requires verified signature evidence before installation"
            )
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

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def record(self, receipt: CoreComponentReceipt) -> None:
        if not isinstance(receipt, CoreComponentReceipt):
            raise TypeError("CoreComponentReceipt required")
        with closing(self._connect()) as db, db:
            db.execute("""
                INSERT OR REPLACE INTO core_component_receipt(
                    receipt_id, artifact_id, version, operation, outcome,
                    artifact_sha256, authority, approval_id, health_verified,
                    installed_at, detail
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """, (
                receipt.receipt_id, receipt.artifact_id, receipt.version,
                receipt.operation.value, receipt.outcome.value,
                receipt.artifact_sha256, receipt.authority.value,
                receipt.approval_id, int(receipt.health_verified),
                receipt.installed_at.astimezone(timezone.utc).isoformat(),
                receipt.detail[:2000],
            ))

    def installed(self, artifact_id: str = CORE_DISTRIBUTION) -> CoreComponentReceipt | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM core_component_receipt WHERE artifact_id=?",
                (artifact_id,),
            ).fetchone()
        if row is None:
            return None
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


class CoreComponentInstaller:
    """Install or replace the Core component under explicit authority."""

    def __init__(self, registry: CoreComponentRegistry) -> None:
        self.registry = registry

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
        try:
            verify_core_component_content(wheel_path)
        except ComponentArtifactError as error:
            raise CoreComponentInstallError(str(error)) from error
        health_verified = self._verify_health(wheel_path)
        if not health_verified:
            raise CoreComponentInstallError("Core component failed the health probe")
        receipt = CoreComponentReceipt(
            receipt_id=f"core-component-install-{artifact.artifact_id}-{artifact.version}",
            artifact_id=artifact.artifact_id,
            version=artifact.version,
            operation=operation,
            outcome=InstallOutcome.SUCCEEDED,
            artifact_sha256=artifact.sha256,
            authority=authority,
            approval_id=approval_id,
            health_verified=health_verified,
            installed_at=datetime.now(timezone.utc),
            detail="verified content, compatibility and health",
        )
        self.registry.record(receipt)
        return receipt

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
