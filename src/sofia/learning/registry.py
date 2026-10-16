"""Content-addressed external candidate registry with fail-closed loading."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from math import isfinite
import os
from pathlib import Path
import re
import sqlite3
from typing import Callable

from sofia.state.canonical_sqlite import CanonicalSQLiteGuard

from .contracts import DataUse, DataUseGrant

_SHA = re.compile(r"^[0-9a-f]{64}$")
SUPPORTED_FORMATS = frozenset({"json-linear-v1"})


@dataclass(frozen=True, slots=True)
class CandidateArtifact:
    candidate_id: str
    artifact_path: Path
    artifact_sha256: str
    signature: bytes
    signer_key_id: str
    format: str
    runtime: str
    created_at: datetime
    expires_at: datetime
    max_bytes: int
    max_ram_mb: int
    max_cpu_seconds: int
    fallback_candidate_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_id, str) or not self.candidate_id.startswith("ml-candidate:"):
            raise ValueError("candidate ID must use ml-candidate namespace")
        if not isinstance(self.artifact_path, Path) or not self.artifact_path.is_absolute():
            raise ValueError("candidate artifact path must be absolute")
        if not _SHA.fullmatch(self.artifact_sha256):
            raise ValueError("candidate artifact requires SHA-256")
        if not isinstance(self.signature, bytes) or not self.signature:
            raise ValueError("candidate artifact requires detached signature")
        if not isinstance(self.signer_key_id, str) or not self.signer_key_id.strip():
            raise ValueError("candidate signer key ID required")
        if self.format not in SUPPORTED_FORMATS:
            raise ValueError("candidate export format is not supported")
        if self.runtime != "python-cpu":
            raise ValueError("candidate runtime is incompatible")
        for value, low, high, name in (
            (self.max_bytes, 1, 512 * 1024 * 1024, "bytes"),
            (self.max_ram_mb, 1, 4096, "RAM"),
            (self.max_cpu_seconds, 1, 300, "CPU time"),
        ):
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"candidate {name} ceiling is outside policy")
        if self.created_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("candidate times must be timezone-aware")
        if not self.created_at < self.expires_at <= self.created_at + timedelta(days=90):
            raise ValueError("candidate must expire within 90 days")

    def signed_bytes(self) -> bytes:
        body = {
            "candidate_id": self.candidate_id,
            "artifact_sha256": self.artifact_sha256,
            "format": self.format, "runtime": self.runtime,
            "created_at": self.created_at.astimezone(timezone.utc).isoformat(),
            "expires_at": self.expires_at.astimezone(timezone.utc).isoformat(),
            "max_bytes": self.max_bytes, "max_ram_mb": self.max_ram_mb,
            "max_cpu_seconds": self.max_cpu_seconds,
            "fallback_candidate_id": self.fallback_candidate_id,
        }
        return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


class CandidateRegistry:
    """Metadata in canonical state; immutable model bytes stay externally managed."""

    def __init__(
        self, state_path: str | Path, *, artifact_root: Path,
        verify_signature: Callable[[str, bytes, bytes], bool],
        approval_verifier=None,
    ) -> None:
        if not isinstance(artifact_root, Path) or not artifact_root.is_absolute():
            raise ValueError("managed candidate artifact root must be absolute")
        if not callable(verify_signature):
            raise TypeError("signature verifier required")
        self._guard = CanonicalSQLiteGuard(Path(state_path))
        self._root = artifact_root.resolve()
        self._verify = verify_signature
        self._approval = approval_verifier
        with closing(self._guard.connect(timeout=10)) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS ml_model_candidate(
                    candidate_id TEXT PRIMARY KEY, artifact_path TEXT NOT NULL,
                    artifact_sha256 TEXT NOT NULL UNIQUE, signature BLOB NOT NULL,
                    signer_key_id TEXT NOT NULL, format TEXT NOT NULL,
                    runtime TEXT NOT NULL, created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL, max_bytes INTEGER NOT NULL,
                    max_ram_mb INTEGER NOT NULL, max_cpu_seconds INTEGER NOT NULL,
                    fallback_candidate_id TEXT, revoked_at TEXT,
                    registration_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ml_model_activation(
                    revision INTEGER PRIMARY KEY AUTOINCREMENT,
                    candidate_id TEXT NOT NULL, previous_candidate_id TEXT,
                    principal_id TEXT NOT NULL, audience_id TEXT NOT NULL,
                    purpose TEXT NOT NULL, activated_at TEXT NOT NULL,
                    grant_id TEXT NOT NULL,
                    rollback INTEGER NOT NULL
                );
            """)

    def _safe_path(self, path: Path) -> Path:
        if any(
            component.is_symlink() or getattr(component, "is_junction", lambda: False)()
            for component in (path, *path.parents)
        ):
            raise PermissionError("candidate path cannot use symlinks or junctions")
        resolved = path.resolve(strict=True)
        try:
            resolved.relative_to(self._root)
        except ValueError as exc:
            raise PermissionError("candidate artifact escaped managed root") from exc
        if not resolved.is_file():
            raise ValueError("candidate artifact must be a regular file")
        return resolved

    @staticmethod
    def _hash(path: Path, maximum: int) -> tuple[str, int]:
        digest = sha256()
        total = 0
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                total += len(block)
                if total > maximum:
                    raise ValueError("candidate artifact exceeds declared resource ceiling")
                digest.update(block)
        return digest.hexdigest(), total

    @staticmethod
    def _read_stable(path: Path, maximum: int) -> bytes:
        before = path.stat(follow_symlinks=False)
        with path.open("rb") as stream:
            opened = stream.read(maximum + 1)
            details = os.fstat(stream.fileno())
        after = path.stat(follow_symlinks=False)
        identities = (
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns),
            (details.st_dev, details.st_ino, details.st_size, details.st_mtime_ns),
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
        )
        if len(set(identities)) != 1:
            raise PermissionError("candidate artifact changed while being read")
        if len(opened) > maximum:
            raise ValueError("candidate artifact exceeds declared resource ceiling")
        return opened

    @staticmethod
    def _validate_format(data: bytes, export_format: str) -> None:
        if export_format != "json-linear-v1":
            raise PermissionError("candidate format/runtime is incompatible")
        try:
            model = json.loads(data.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise PermissionError("candidate export is not valid JSON") from exc
        if (
            not isinstance(model, dict)
            or set(model) != {"version", "model_type", "features", "weights", "bias"}
            or model["version"] != 1 or model["model_type"] != "linear"
            or not isinstance(model["features"], list)
            or not 1 <= len(model["features"]) <= 128
            or any(not isinstance(item, str) or not item for item in model["features"])
            or not isinstance(model["weights"], list)
            or len(model["weights"]) != len(model["features"])
            or any(type(item) not in (int, float) for item in model["weights"])
            or any(type(item) is float and not isfinite(item) for item in model["weights"])
            or type(model["bias"]) not in (int, float)
            or (type(model["bias"]) is float and not isfinite(model["bias"]))
        ):
            raise PermissionError("candidate export violates json-linear-v1 schema")

    def register(self, artifact: CandidateArtifact) -> None:
        if not isinstance(artifact, CandidateArtifact):
            raise TypeError("typed CandidateArtifact required")
        path = self._safe_path(artifact.artifact_path)
        observed, size = self._hash(path, artifact.max_bytes)
        if observed != artifact.artifact_sha256:
            raise PermissionError("candidate artifact hash mismatch")
        data = self._read_stable(path, min(artifact.max_bytes, artifact.max_ram_mb * 1024 * 1024))
        self._validate_format(data, artifact.format)
        if not self._verify(artifact.signer_key_id, artifact.signed_bytes(), artifact.signature):
            raise PermissionError("candidate signature is not trusted")
        if artifact.candidate_id != "ml-candidate:" + artifact.artifact_sha256:
            raise PermissionError("candidate ID is not content addressed")
        body = {
            "signed_manifest": artifact.signed_bytes().decode("utf-8"),
            "observed_bytes": size, "registered_path": str(path),
            "signature_sha256": sha256(artifact.signature).hexdigest(),
            "signer_key_id": artifact.signer_key_id,
        }
        values = (
            artifact.candidate_id, str(path), artifact.artifact_sha256,
            artifact.signature, artifact.signer_key_id, artifact.format,
            artifact.runtime, artifact.created_at.astimezone(timezone.utc).isoformat(),
            artifact.expires_at.astimezone(timezone.utc).isoformat(),
            artifact.max_bytes, artifact.max_ram_mb, artifact.max_cpu_seconds,
            artifact.fallback_candidate_id, None,
            json.dumps(body, sort_keys=True, separators=(",", ":")),
        )
        with closing(self._guard.connect(timeout=10)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if artifact.fallback_candidate_id is not None and db.execute(
                "SELECT 1 FROM ml_model_candidate WHERE candidate_id=? AND revoked_at IS NULL",
                (artifact.fallback_candidate_id,),
            ).fetchone() is None:
                raise PermissionError("fallback candidate is unavailable")
            prior = db.execute(
                "SELECT artifact_sha256,registration_json FROM ml_model_candidate WHERE candidate_id=?",
                (artifact.candidate_id,),
            ).fetchone()
            if prior is not None:
                if prior != (artifact.artifact_sha256, values[-1]):
                    raise PermissionError("candidate registration replay changed immutable metadata")
                return
            db.execute("INSERT INTO ml_model_candidate VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", values)

    def revoke(self, candidate_id: str, *, at: datetime, approval_ref: str) -> None:
        if not approval_ref.startswith(("owner-ui:", "safe:")):
            raise PermissionError("authenticated candidate revocation required")
        with closing(self._guard.connect(timeout=10)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if self._approval is None:
                raise PermissionError("SAFE candidate revocation verifier is unavailable")
            self._approval.consume(
                approval_id=approval_ref,
                capability="learning.candidate.revoke",
                parameters={"candidate_id": candidate_id}, now=at,
                _transaction_db=db,
            )
            cursor = db.execute(
                "UPDATE ml_model_candidate SET revoked_at=? WHERE candidate_id=? AND revoked_at IS NULL",
                (at.astimezone(timezone.utc).isoformat(), candidate_id),
            )
            if cursor.rowcount != 1:
                raise LookupError("candidate is unknown or already revoked")

    def load(self, candidate_id: str, *, at: datetime) -> bytes:
        moment = at.astimezone(timezone.utc)
        with closing(self._guard.connect(timeout=10)) as db:
            row = db.execute(
                "SELECT artifact_path,artifact_sha256,signature,signer_key_id,format,runtime,"
                "expires_at,max_bytes,max_ram_mb,registration_json,revoked_at "
                "FROM ml_model_candidate WHERE candidate_id=?",
                (candidate_id,),
            ).fetchone()
        if row is None or row[10] is not None or moment >= datetime.fromisoformat(row[6]):
            raise PermissionError("candidate is missing, revoked, or stale")
        if row[4] not in SUPPORTED_FORMATS or row[5] != "python-cpu":
            raise PermissionError("candidate format/runtime is incompatible")
        path = self._safe_path(Path(row[0]))
        observed, _ = self._hash(path, row[7])
        if observed != row[1]:
            raise PermissionError("candidate bytes are corrupt")
        data = self._read_stable(path, min(row[7], row[8] * 1024 * 1024))
        self._validate_format(data, row[4])
        signed = json.loads(row[9])["signed_manifest"].encode("utf-8")
        if not self._verify(row[3], signed, row[2]):
            raise PermissionError("candidate signature no longer verifies")
        return data

    def activate(
        self, candidate_id: str, *, grant: DataUseGrant,
        evaluation_id: str, at: datetime,
    ) -> None:
        if not grant.permits(DataUse.DEPLOYMENT, at=at):
            raise PermissionError("candidate activation needs an unexpired deployment grant")
        self._require_canonical_deployment_grant(grant, at=at)
        self.load(candidate_id, at=at)
        with closing(self._guard.connect(timeout=10)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            candidate_digest = db.execute(
                "SELECT artifact_sha256 FROM ml_model_candidate WHERE candidate_id=?",
                (candidate_id,),
            ).fetchone()[0]
            evaluation = db.execute(
                "SELECT body_json FROM ml_evaluation WHERE evaluation_id=?",
                (evaluation_id,),
            ).fetchone()
            if evaluation is None:
                raise PermissionError("candidate activation lacks independent evaluation")
            evaluation_body = json.loads(evaluation[0])
            if (
                evaluation_body.get("candidate_digest") != candidate_digest
                or not isinstance(evaluation_body.get("scored"), int)
                or evaluation_body["scored"] <= 0
                or evaluation_body.get("paired_delta") is None
            ):
                raise PermissionError("evaluation is unknown or belongs to another candidate")
            dataset = db.execute(
                "SELECT body_json FROM ml_dataset_manifest WHERE manifest_id=?",
                (evaluation_body.get("manifest_id"),),
            ).fetchone()
            if dataset is None:
                raise PermissionError("candidate evaluation dataset is unavailable")
            dataset_body = json.loads(dataset[0])
            if (
                dataset_body.get("principal_id") != grant.principal_id
                or dataset_body.get("audience_id") != grant.audience_id
                or dataset_body.get("purpose") != grant.purpose
            ):
                raise PermissionError("deployment grant scope differs from evaluated dataset")
            prior = db.execute(
                "SELECT candidate_id FROM ml_model_activation "
                "WHERE principal_id=? AND audience_id=? AND purpose=? "
                "ORDER BY revision DESC LIMIT 1",
                (grant.principal_id, grant.audience_id, grant.purpose),
            ).fetchone()
            db.execute(
                "INSERT INTO ml_model_activation(candidate_id,previous_candidate_id,principal_id,audience_id,purpose,activated_at,grant_id,rollback) "
                "VALUES(?,?,?,?,?,?,?,0)",
                (candidate_id, None if prior is None else prior[0],
                 grant.principal_id, grant.audience_id, grant.purpose,
                 at.astimezone(timezone.utc).isoformat(), grant.grant_id),
            )

    def active(
        self, *, principal_id: str, audience_id: str, purpose: str,
        at: datetime,
    ) -> str | None:
        with closing(self._guard.connect(timeout=10)) as db:
            row = db.execute(
                "SELECT candidate_id FROM ml_model_activation "
                "WHERE principal_id=? AND audience_id=? AND purpose=? "
                "ORDER BY revision DESC LIMIT 1",
                (principal_id, audience_id, purpose),
            ).fetchone()
        if row is None:
            return None
        self.load(row[0], at=at)
        return row[0]

    def rollback(self, *, grant: DataUseGrant, at: datetime) -> str:
        if not grant.permits(DataUse.DEPLOYMENT, at=at):
            raise PermissionError("candidate rollback needs deployment authority")
        self._require_canonical_deployment_grant(grant, at=at)
        with closing(self._guard.connect(timeout=10)) as db:
            current = db.execute(
                "SELECT candidate_id,previous_candidate_id FROM ml_model_activation "
                "WHERE principal_id=? AND audience_id=? AND purpose=? "
                "ORDER BY revision DESC LIMIT 1",
                (grant.principal_id, grant.audience_id, grant.purpose),
            ).fetchone()
        if current is None or current[1] is None:
            raise LookupError("no previous candidate available")
        self.load(current[1], at=at)
        with closing(self._guard.connect(timeout=10)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            # Recheck the pointer under the writer lock so concurrent activation cannot be overwritten.
            latest = db.execute(
                "SELECT candidate_id,previous_candidate_id FROM ml_model_activation "
                "WHERE principal_id=? AND audience_id=? AND purpose=? "
                "ORDER BY revision DESC LIMIT 1",
                (grant.principal_id, grant.audience_id, grant.purpose),
            ).fetchone()
            if latest != current:
                raise RuntimeError("active candidate changed during rollback")
            db.execute(
                "INSERT INTO ml_model_activation(candidate_id,previous_candidate_id,principal_id,audience_id,purpose,activated_at,grant_id,rollback) "
                "VALUES(?,?,?,?,?,?,?,1)",
                (current[1], current[0], grant.principal_id,
                 grant.audience_id, grant.purpose,
                 at.astimezone(timezone.utc).isoformat(), grant.grant_id),
            )
        return current[1]

    def _require_canonical_deployment_grant(
        self, grant: DataUseGrant, *, at: datetime,
    ) -> None:
        body = {
            "grant_id": grant.grant_id, "principal_id": grant.principal_id,
            "audience_id": grant.audience_id, "purpose": grant.purpose,
            "uses": sorted(value.value for value in grant.uses),
            "issued_at": grant.issued_at.astimezone(timezone.utc).isoformat(),
            "expires_at": grant.expires_at.astimezone(timezone.utc).isoformat(),
            "approval_ref": grant.approval_ref,
        }
        digest = sha256(json.dumps(
            body, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")).hexdigest()
        with closing(self._guard.connect(timeout=10)) as db:
            row = db.execute(
                "SELECT g.record_digest FROM ml_data_use_grant g "
                "LEFT JOIN ml_data_use_revocation r ON r.grant_id=g.grant_id "
                "WHERE g.grant_id=? AND r.grant_id IS NULL",
                (grant.grant_id,),
            ).fetchone()
        if row is None or row[0] != digest:
            raise PermissionError("deployment grant is absent, changed, or revoked")


def create_candidate_registry_from_environment(
    state_path: str | Path, *, artifact_root: Path,
) -> CandidateRegistry | None:
    """Build the production registry only with an explicit trusted Ed25519 key.

    Absence means candidate loading is unavailable, not implicitly trusted.
    The key file is read once; candidate signatures are rechecked on each load.
    """
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from sofia.safe.execution_approval import ExecutionApprovalVerifier

    key_path = os.environ.get("SOFIA_ML_TRUSTED_PUBLIC_KEY", "").strip()
    key_id = os.environ.get("SOFIA_ML_TRUSTED_KEY_ID", "").strip()
    if not key_path and not key_id:
        return None
    if not key_path or not key_id:
        raise ValueError("ML trusted key path and key ID must be configured together")
    path = Path(key_path).expanduser().resolve(strict=True)
    if not path.is_file() or path.is_symlink():
        raise PermissionError("ML trusted public key must be a regular non-symlink file")
    loaded = serialization.load_pem_public_key(path.read_bytes())
    if not isinstance(loaded, Ed25519PublicKey):
        raise TypeError("ML trusted candidate key must be Ed25519")

    def verify(signer: str, message: bytes, signature: bytes) -> bool:
        if signer != key_id:
            return False
        try:
            loaded.verify(signature, message)
        except InvalidSignature:
            return False
        return True

    return CandidateRegistry(
        state_path, artifact_root=artifact_root, verify_signature=verify,
        approval_verifier=ExecutionApprovalVerifier(state_path),
    )
