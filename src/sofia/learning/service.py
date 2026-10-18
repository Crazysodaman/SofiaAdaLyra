"""Canonical lineage, point-in-time datasets and independent evaluation.

This service deliberately has no background thread and no capability gateway.
ApplicationBackgroundCoordinator remains the only scheduler; SAFE/capabilities
remain the only action authority.  All rows live in the configured canonical
``sofia.db`` through :class:`CanonicalSQLiteGuard`.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import platform
import re
import sqlite3
from typing import Callable, Mapping
from types import MappingProxyType

from sofia.goals.evidence import GoalEvidence, GoalEvidenceIndex
from sofia.state.canonical_sqlite import CanonicalSQLiteGuard

from .contracts import (
    DataUse, DataUseGrant, OutcomeClass, PROHIBITED_TRAINING_SOURCES,
    Prediction, PredictionMode, SourceClass,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SCHEMA_VERSION = "ml-feature-v1"
_MAX_FEATURES = 128
_MAX_SAMPLES = 100_000


def _utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class GroundedSample:
    sample_id: str
    source_class: SourceClass
    source_ref: str
    outcome_ref: str
    principal_id: str
    audience_id: str
    subject_id: str
    group_id: str
    prediction_at: datetime
    outcome: OutcomeClass
    features: Mapping[str, float | int | bool | None]
    retention_until: datetime
    purpose: str
    max_source_age_seconds: int = 3600

    def __post_init__(self) -> None:
        for field in (
            "sample_id", "source_ref", "outcome_ref", "principal_id",
            "audience_id", "subject_id", "group_id", "purpose",
        ):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip() or len(value) > 400:
                raise ValueError(f"{field} must be a bounded nonempty string")
        if not isinstance(self.source_class, SourceClass):
            raise TypeError("source_class must be SourceClass")
        if self.source_class in PROHIBITED_TRAINING_SOURCES:
            raise PermissionError("ambient chat/private media/journal training is denied")
        if not isinstance(self.outcome, OutcomeClass):
            raise TypeError("outcome must be OutcomeClass")
        observed = _utc(self.prediction_at, "prediction_at")
        retained = _utc(self.retention_until, "retention_until")
        if retained <= observed:
            raise ValueError("sample retention must extend past prediction time")
        if (
            type(self.max_source_age_seconds) is not int
            or not 1 <= self.max_source_age_seconds <= 30 * 86400
        ):
            raise ValueError("source freshness bound must be in [1 second, 30 days]")
        if not isinstance(self.features, Mapping) or not 1 <= len(self.features) <= _MAX_FEATURES:
            raise ValueError("one to 128 scalar features required")
        if any(
            not isinstance(key, str) or not key.strip() or len(key) > 100
            or type(value) not in (int, float, bool, type(None))
            or (type(value) is float and not isfinite(value))
            for key, value in self.features.items()
        ):
            raise TypeError("features must contain named JSON scalars only")
        # Freeze a plain copy so a caller cannot mutate a reviewed sample.
        object.__setattr__(self, "features", MappingProxyType(dict(self.features)))


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    manifest_id: str
    schema_version: str
    seed: int
    created_at: datetime
    sample_ids: tuple[str, ...]
    train_ids: tuple[str, ...]
    validation_ids: tuple[str, ...]
    holdout_ids: tuple[str, ...]
    feature_names: tuple[str, ...]
    source_digest: str
    library_digest: str


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    evaluation_id: str
    manifest_id: str
    baseline_digest: str
    candidate_digest: str
    evaluated_at: datetime
    baseline_accuracy: float | None
    candidate_accuracy: float | None
    paired_delta: float | None
    scored: int
    unknown: int
    holdout_digest: str


class LearningService:
    """One canonical, authority-free ML foundation owner."""

    def __init__(self, state_path: str | Path, *, approval_verifier=None) -> None:
        self._guard = CanonicalSQLiteGuard(Path(state_path))
        self._evidence = GoalEvidenceIndex(state_path)
        self._approval = approval_verifier
        with closing(self._connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS ml_data_use_grant(
                    grant_id TEXT PRIMARY KEY, principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL, purpose TEXT NOT NULL,
                    uses_json TEXT NOT NULL, issued_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL, approval_ref TEXT NOT NULL UNIQUE,
                    record_digest TEXT NOT NULL UNIQUE
                );
                CREATE TABLE IF NOT EXISTS ml_data_use_revocation(
                    grant_id TEXT PRIMARY KEY REFERENCES ml_data_use_grant(grant_id),
                    revoked_at TEXT NOT NULL, approval_ref TEXT NOT NULL UNIQUE
                );
                CREATE TABLE IF NOT EXISTS ml_grounded_sample(
                    sample_id TEXT PRIMARY KEY, principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL, subject_id TEXT NOT NULL,
                    group_id TEXT NOT NULL, source_class TEXT NOT NULL,
                    source_ref TEXT NOT NULL, source_at TEXT NOT NULL,
                    outcome_ref TEXT NOT NULL, prediction_at TEXT NOT NULL,
                    max_source_age_seconds INTEGER NOT NULL,
                    outcome_at TEXT NOT NULL,
                    outcome TEXT NOT NULL, features_json TEXT NOT NULL,
                    retention_until TEXT NOT NULL, purpose TEXT NOT NULL,
                    grant_id TEXT NOT NULL, record_digest TEXT NOT NULL UNIQUE
                );
                CREATE TABLE IF NOT EXISTS ml_source_revocation(
                    source_ref TEXT PRIMARY KEY, revoked_at TEXT NOT NULL,
                    approval_ref TEXT NOT NULL UNIQUE
                );
                CREATE TABLE IF NOT EXISTS ml_dataset_manifest(
                    manifest_id TEXT PRIMARY KEY, body_json TEXT NOT NULL,
                    created_at TEXT NOT NULL, record_digest TEXT NOT NULL UNIQUE
                );
                CREATE TABLE IF NOT EXISTS ml_evaluation(
                    evaluation_id TEXT PRIMARY KEY, manifest_id TEXT NOT NULL,
                    body_json TEXT NOT NULL, evaluated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ml_operating_state(
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    mode TEXT NOT NULL, revision INTEGER NOT NULL,
                    changed_at TEXT NOT NULL, approval_ref TEXT,
                    revoked INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ml_prediction_trace(
                    prediction_id TEXT PRIMARY KEY, principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL, mode TEXT NOT NULL,
                    body_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    action_executed INTEGER NOT NULL CHECK(action_executed=0)
                );
            """)
            db.execute(
                "INSERT OR IGNORE INTO ml_operating_state VALUES(1,?,0,?,NULL,0)",
                (PredictionMode.SHADOW.value, datetime.now(timezone.utc).isoformat()),
            )

    def _connect(self) -> sqlite3.Connection:
        return self._guard.connect(timeout=10)

    @staticmethod
    def _grant_body(grant: DataUseGrant) -> dict:
        return {
            "grant_id": grant.grant_id,
            "principal_id": grant.principal_id,
            "audience_id": grant.audience_id,
            "purpose": grant.purpose,
            "uses": sorted(value.value for value in grant.uses),
            "issued_at": grant.issued_at.astimezone(timezone.utc).isoformat(),
            "expires_at": grant.expires_at.astimezone(timezone.utc).isoformat(),
            "approval_ref": grant.approval_ref,
        }

    def record_grant(self, grant: DataUseGrant) -> None:
        if not isinstance(grant, DataUseGrant):
            raise TypeError("typed DataUseGrant required")
        body = self._grant_body(grant)
        values = (
            grant.grant_id, grant.principal_id, grant.audience_id, grant.purpose,
            _canonical(body["uses"]), body["issued_at"], body["expires_at"],
            grant.approval_ref, _digest(body),
        )
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                "SELECT principal_id,audience_id,purpose,uses_json,issued_at,expires_at,approval_ref,record_digest "
                "FROM ml_data_use_grant WHERE grant_id=?", (grant.grant_id,),
            ).fetchone()
            if prior is not None:
                if prior != values[1:]:
                    raise PermissionError("immutable data-use grant ID was replayed differently")
                return
            if self._approval is None:
                raise PermissionError("SAFE data-use approval verifier is unavailable")
            self._approval.consume(
                approval_id=grant.approval_ref,
                capability="learning.data_use.grant",
                parameters={key: value for key, value in body.items() if key != "approval_ref"},
                now=grant.issued_at,
                _transaction_db=db,
            )
            db.execute("INSERT INTO ml_data_use_grant VALUES(?,?,?,?,?,?,?,?,?)", values)

    def revoke_grant(self, grant_id: str, *, at: datetime, approval_ref: str) -> None:
        moment = _utc(at, "at").isoformat()
        if not approval_ref.startswith(("owner-ui:", "safe:")):
            raise PermissionError("authenticated revocation evidence required")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM ml_data_use_grant WHERE grant_id=?", (grant_id,)).fetchone() is None:
                raise LookupError("unknown data-use grant")
            if self._approval is None:
                raise PermissionError("SAFE data-use revocation verifier is unavailable")
            self._approval.consume(
                approval_id=approval_ref,
                capability="learning.data_use.revoke",
                parameters={"grant_id": grant_id}, now=datetime.fromisoformat(moment),
                _transaction_db=db,
            )
            try:
                db.execute("INSERT INTO ml_data_use_revocation VALUES(?,?,?)", (grant_id, moment, approval_ref))
            except sqlite3.IntegrityError as exc:
                raise PermissionError("grant already revoked or revocation receipt replayed") from exc

    def _require_grant(
        self, db: sqlite3.Connection, grant: DataUseGrant, *, at: datetime,
        required: tuple[DataUse, ...], principal_id: str, audience_id: str,
        purpose: str,
    ) -> None:
        row = db.execute(
            "SELECT record_digest FROM ml_data_use_grant g "
            "LEFT JOIN ml_data_use_revocation r ON r.grant_id=g.grant_id "
            "WHERE g.grant_id=? AND r.grant_id IS NULL", (grant.grant_id,),
        ).fetchone()
        if row is None or row[0] != _digest(self._grant_body(grant)):
            raise PermissionError("data-use grant is missing, changed, or revoked")
        if (
            principal_id != grant.principal_id or audience_id != grant.audience_id
            or purpose != grant.purpose or not grant.permits(*required, at=at)
        ):
            raise PermissionError("data use exceeds exact principal/audience/purpose/operation grant")

    def active_grant(
        self, *, principal_id: str, audience_id: str, purpose: str,
        required: tuple[DataUse, ...], at: datetime,
    ) -> DataUseGrant | None:
        """Return one exact durable grant, or ``None`` when use is not authorized.

        This is an eligibility lookup for existing application-owned workers. It
        cannot create or widen a grant, and deliberately requires the caller to
        name every operation it intends to perform.
        """
        moment = _utc(at, "at")
        if not required or any(not isinstance(item, DataUse) for item in required):
            raise TypeError("required must contain typed DataUse operations")
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT g.grant_id,g.uses_json,g.issued_at,g.expires_at,g.approval_ref "
                "FROM ml_data_use_grant g "
                "LEFT JOIN ml_data_use_revocation r ON r.grant_id=g.grant_id "
                "WHERE g.principal_id=? AND g.audience_id=? AND g.purpose=? "
                "AND g.issued_at<=? AND g.expires_at>? AND r.grant_id IS NULL "
                "ORDER BY g.issued_at DESC,g.grant_id",
                (principal_id, audience_id, purpose, moment.isoformat(), moment.isoformat()),
            ).fetchall()
        for row in rows:
            grant = DataUseGrant(
                grant_id=row[0], principal_id=principal_id, audience_id=audience_id,
                purpose=purpose,
                uses=frozenset(DataUse(item) for item in json.loads(row[1])),
                issued_at=datetime.fromisoformat(row[2]),
                expires_at=datetime.fromisoformat(row[3]), approval_ref=row[4],
            )
            if grant.permits(*required, at=moment):
                return grant
        return None

    @staticmethod
    def _require_scoped_evidence(
        evidence: GoalEvidence | None, *, principal_id: str, audience_id: str,
        name: str,
    ) -> GoalEvidence:
        if evidence is None:
            raise PermissionError(f"{name} evidence does not exist")
        if evidence.kind == "conversation_message" or evidence.source == "conversation":
            raise PermissionError("raw conversation cannot become statistical training evidence")
        if evidence.principal_id != principal_id or evidence.audience != audience_id:
            raise PermissionError(f"{name} evidence principal/audience scope mismatch")
        return evidence

    @staticmethod
    def _source_matches_class(source_class: SourceClass, evidence: GoalEvidence) -> bool:
        if source_class is SourceClass.FLEET_TELEMETRY:
            return evidence.kind == "external_observation" and bool(
                evidence.source and evidence.source.startswith(("fleet:", "ops:"))
            )
        if source_class is SourceClass.OPS_OBSERVATION:
            return evidence.kind in {"external_observation", "reviewed_evidence"} and bool(
                evidence.source and evidence.source.startswith(("ops:", "ops-"))
            )
        if source_class is SourceClass.OPERATION_RECEIPT:
            return evidence.kind == "operation_receipt"
        if source_class is SourceClass.GOAL_EVIDENCE:
            return evidence.kind in {"reviewed_evidence", "external_observation"}
        if source_class is SourceClass.ARTIFACT_EVALUATION:
            return evidence.kind == "reviewed_evidence" and bool(
                evidence.source and evidence.source.startswith(("life:", "creative:"))
            )
        # Public JSONL intake remains EVOLVE's existing owner and does not
        # pass through GoalEvidenceIndex.
        return False

    def admit_sample(self, sample: GroundedSample, grant: DataUseGrant) -> None:
        if not isinstance(sample, GroundedSample) or not isinstance(grant, DataUseGrant):
            raise TypeError("typed sample and grant required")
        source = self._require_scoped_evidence(
            self._evidence.lookup(sample.source_ref), principal_id=sample.principal_id,
            audience_id=sample.audience_id, name="source",
        )
        outcome = self._require_scoped_evidence(
            self._evidence.lookup(sample.outcome_ref), principal_id=sample.principal_id,
            audience_id=sample.audience_id, name="outcome",
        )
        if not self._source_matches_class(sample.source_class, source):
            raise PermissionError("declared source class conflicts with canonical evidence")
        prediction_at = _utc(sample.prediction_at, "prediction_at")
        source_at = source.observed_at.astimezone(timezone.utc)
        if source_at > prediction_at:
            raise PermissionError("future source observation cannot enter point-in-time features")
        if (prediction_at - source_at).total_seconds() > sample.max_source_age_seconds:
            raise PermissionError("stale source observation cannot enter point-in-time features")
        if outcome.observed_at.astimezone(timezone.utc) <= prediction_at:
            raise PermissionError("outcome must be independently observed after prediction cutoff")
        if sample.outcome is not OutcomeClass.UNKNOWN:
            expected = sample.outcome is OutcomeClass.POSITIVE
            if outcome.successful is None or outcome.successful is not expected:
                raise PermissionError("sample label conflicts with independently observed outcome")
        elif outcome.successful is not None:
            raise PermissionError("verified positive/negative outcome cannot be relabeled unknown")
        body = {
            "sample_id": sample.sample_id, "principal_id": sample.principal_id,
            "audience_id": sample.audience_id, "subject_id": sample.subject_id,
            "group_id": sample.group_id, "source_class": sample.source_class.value,
            "source_ref": sample.source_ref, "outcome_ref": sample.outcome_ref,
            "source_at": source_at.isoformat(),
            "prediction_at": prediction_at.isoformat(),
            "max_source_age_seconds": sample.max_source_age_seconds,
            "outcome_at": outcome.observed_at.astimezone(timezone.utc).isoformat(),
            "outcome": sample.outcome.value,
            "features": dict(sorted(sample.features.items())),
            "retention_until": _utc(sample.retention_until, "retention_until").isoformat(),
            "purpose": sample.purpose, "grant_id": grant.grant_id,
        }
        digest = _digest(body)
        values = (
            sample.sample_id, sample.principal_id, sample.audience_id,
            sample.subject_id, sample.group_id, sample.source_class.value,
            sample.source_ref, body["source_at"], sample.outcome_ref,
            body["prediction_at"], sample.max_source_age_seconds,
            body["outcome_at"], sample.outcome.value, _canonical(body["features"]),
            body["retention_until"], sample.purpose, grant.grant_id, digest,
        )
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            self._require_grant(
                db, grant, at=prediction_at,
                required=(DataUse.OBSERVATION, DataUse.STORAGE,
                          DataUse.FEATURE_EXTRACTION, DataUse.STATISTICAL_TRAINING),
                principal_id=sample.principal_id, audience_id=sample.audience_id,
                purpose=sample.purpose,
            )
            if db.execute(
                "SELECT 1 FROM ml_source_revocation WHERE source_ref IN (?,?)",
                (sample.source_ref, sample.outcome_ref),
            ).fetchone():
                raise PermissionError("revoked evidence cannot enter training lineage")
            prior = db.execute(
                "SELECT record_digest FROM ml_grounded_sample WHERE sample_id=?",
                (sample.sample_id,),
            ).fetchone()
            if prior is not None:
                if prior[0] != digest:
                    raise PermissionError("sample ID replay changed immutable lineage")
                return
            count = db.execute("SELECT COUNT(*) FROM ml_grounded_sample").fetchone()[0]
            if count >= _MAX_SAMPLES:
                raise RuntimeError("bounded canonical learning sample limit reached")
            db.execute("INSERT INTO ml_grounded_sample VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", values)

    def revoke_source(self, source_ref: str, *, at: datetime, approval_ref: str) -> None:
        if not approval_ref.startswith(("owner-ui:", "safe:", "retention:")):
            raise PermissionError("authenticated source revocation/retention receipt required")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute(
                "SELECT 1 FROM ml_grounded_sample WHERE source_ref=? OR outcome_ref=?",
                (source_ref, source_ref),
            ).fetchone() is None:
                raise LookupError("unknown lineage source")
            if self._approval is None:
                raise PermissionError("SAFE source revocation verifier is unavailable")
            self._approval.consume(
                approval_id=approval_ref,
                capability="learning.source.revoke",
                parameters={"source_ref": source_ref}, now=_utc(at, "at"),
                _transaction_db=db,
            )
            try:
                db.execute(
                    "INSERT INTO ml_source_revocation VALUES(?,?,?)",
                    (source_ref, _utc(at, "at").isoformat(), approval_ref),
                )
            except sqlite3.IntegrityError as exc:
                raise PermissionError("source already revoked or receipt replayed") from exc

    def create_manifest(
        self, *, principal_id: str, audience_id: str, purpose: str,
        at: datetime, seed: int = 0,
    ) -> DatasetManifest:
        moment = _utc(at, "at")
        if type(seed) is not int or not 0 <= seed < 2**32:
            raise ValueError("seed must be a pinned uint32")
        with closing(self._connect()) as db, db:
            rows = db.execute("""
                SELECT s.sample_id,s.group_id,s.prediction_at,s.outcome_at,
                       s.features_json,s.record_digest
                FROM ml_grounded_sample s
                JOIN ml_data_use_grant g ON g.grant_id=s.grant_id
                LEFT JOIN ml_data_use_revocation gr ON gr.grant_id=g.grant_id
                LEFT JOIN ml_source_revocation sr ON sr.source_ref=s.source_ref
                LEFT JOIN ml_source_revocation orv ON orv.source_ref=s.outcome_ref
                WHERE s.principal_id=? AND s.audience_id=? AND s.purpose=?
                  AND s.retention_until>? AND g.expires_at>?
                  AND gr.grant_id IS NULL AND sr.source_ref IS NULL
                  AND orv.source_ref IS NULL
                ORDER BY s.outcome_at,s.sample_id
            """, (principal_id, audience_id, purpose, moment.isoformat(), moment.isoformat())).fetchall()
            if len(rows) < 3:
                raise ValueError("at least three currently eligible grounded samples required")
            groups: dict[str, list[tuple]] = {}
            for row in rows:
                groups.setdefault(row[1], []).append(row)
            if len(groups) < 3:
                raise ValueError("at least three independent groups required")
            ordered_groups = sorted(
                groups,
                key=lambda key: (
                    min(row[3] for row in groups[key]),
                    sha256(f"{seed}:{key}".encode("utf-8")).hexdigest(),
                ),
            )
            train_end = max(1, len(ordered_groups) * 60 // 100)
            validation_end = max(train_end + 1, len(ordered_groups) * 80 // 100)
            validation_end = min(validation_end, len(ordered_groups) - 1)
            partitions = (
                ordered_groups[:train_end],
                ordered_groups[train_end:validation_end],
                ordered_groups[validation_end:],
            )
            if any(not part for part in partitions):
                raise ValueError("chronological group-separated split could not be formed")
            ids = tuple(row[0] for row in rows)
            ids_by_group = {key: tuple(row[0] for row in groups[key]) for key in groups}
            split_ids = tuple(
                tuple(sample for group in part for sample in ids_by_group[group])
                for part in partitions
            )
            feature_names = tuple(sorted({
                name for row in rows for name in json.loads(row[4])
            }))
            source_digest = _digest(tuple(row[5] for row in rows))
            library_digest = _digest({
                "python": platform.python_version(), "implementation": platform.python_implementation(),
                "algorithm": "chronological-group-split-v1",
            })
            body = {
                "schema_version": _SCHEMA_VERSION, "seed": seed,
                "created_at": moment.isoformat(), "sample_ids": ids,
                "train_ids": split_ids[0], "validation_ids": split_ids[1],
                "holdout_ids": split_ids[2], "feature_names": feature_names,
                "source_digest": source_digest, "library_digest": library_digest,
                "principal_id": principal_id, "audience_id": audience_id,
                "purpose": purpose,
            }
            manifest_id = "ml-dataset:" + _digest(body)
            body["manifest_id"] = manifest_id
            raw = _canonical(body)
            try:
                db.execute(
                    "INSERT INTO ml_dataset_manifest VALUES(?,?,?,?)",
                    (manifest_id, raw, moment.isoformat(), _digest(body)),
                )
            except sqlite3.IntegrityError:
                existing = db.execute(
                    "SELECT body_json FROM ml_dataset_manifest WHERE manifest_id=?",
                    (manifest_id,),
                ).fetchone()
                if existing is None or existing[0] != raw:
                    raise PermissionError("immutable dataset manifest collision")
        return self.get_manifest(manifest_id, at=moment)

    def get_manifest(self, manifest_id: str, *, at: datetime) -> DatasetManifest:
        moment = _utc(at, "at")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT body_json,record_digest FROM ml_dataset_manifest WHERE manifest_id=?",
                (manifest_id,),
            ).fetchone()
            if row is None:
                raise LookupError("unknown dataset manifest")
            body = json.loads(row[0])
            if _digest(body) != row[1] or "ml-dataset:" + _digest({k: v for k, v in body.items() if k != "manifest_id"}) != manifest_id:
                raise PermissionError("dataset manifest integrity failure")
            placeholders = ",".join("?" for _ in body["sample_ids"])
            invalid = db.execute(f"""
                SELECT 1 FROM ml_grounded_sample s
                JOIN ml_data_use_grant g ON g.grant_id=s.grant_id
                LEFT JOIN ml_data_use_revocation gr ON gr.grant_id=g.grant_id
                LEFT JOIN ml_source_revocation sr ON sr.source_ref=s.source_ref
                LEFT JOIN ml_source_revocation orv ON orv.source_ref=s.outcome_ref
                WHERE s.sample_id IN ({placeholders}) AND (
                    s.retention_until<=? OR g.expires_at<=? OR gr.grant_id IS NOT NULL
                    OR sr.source_ref IS NOT NULL OR orv.source_ref IS NOT NULL)
                LIMIT 1
            """, (*body["sample_ids"], moment.isoformat(), moment.isoformat())).fetchone()
            count = db.execute(
                f"SELECT COUNT(*) FROM ml_grounded_sample WHERE sample_id IN ({placeholders})",
                tuple(body["sample_ids"]),
            ).fetchone()[0]
            if invalid is not None or count != len(body["sample_ids"]):
                raise PermissionError("manifest source was revoked, expired, or removed")
            lineage = db.execute(
                f"SELECT source_ref,source_at,outcome_ref,outcome_at,principal_id,audience_id "
                f"FROM ml_grounded_sample WHERE sample_id IN ({placeholders})",
                tuple(body["sample_ids"]),
            ).fetchall()
            for source_ref, source_at, outcome_ref, outcome_at, principal_id, audience_id in lineage:
                source = self._evidence.lookup(source_ref)
                outcome = self._evidence.lookup(outcome_ref)
                if (
                    source is None or outcome is None
                    or source.principal_id != principal_id or source.audience != audience_id
                    or outcome.principal_id != principal_id or outcome.audience != audience_id
                    or source.observed_at.astimezone(timezone.utc).isoformat() != source_at
                    or outcome.observed_at.astimezone(timezone.utc).isoformat() != outcome_at
                ):
                    raise PermissionError("manifest original evidence is unavailable or changed")
        return DatasetManifest(
            manifest_id=body["manifest_id"], schema_version=body["schema_version"],
            seed=body["seed"], created_at=datetime.fromisoformat(body["created_at"]),
            sample_ids=tuple(body["sample_ids"]), train_ids=tuple(body["train_ids"]),
            validation_ids=tuple(body["validation_ids"]), holdout_ids=tuple(body["holdout_ids"]),
            feature_names=tuple(body["feature_names"]), source_digest=body["source_digest"],
            library_digest=body["library_digest"],
        )

    def evaluate(
        self, manifest_id: str, *, baseline_digest: str, candidate_digest: str,
        baseline: Callable[[Mapping[str, object]], OutcomeClass],
        candidate: Callable[[Mapping[str, object]], OutcomeClass], at: datetime,
    ) -> EvaluationResult:
        moment = _utc(at, "at")
        manifest = self.get_manifest(manifest_id, at=moment)
        for name, value in (("baseline_digest", baseline_digest), ("candidate_digest", candidate_digest)):
            if not _SHA256.fullmatch(value):
                raise ValueError(f"{name} must be SHA-256")
        with closing(self._connect()) as db, db:
            placeholders = ",".join("?" for _ in manifest.holdout_ids)
            rows = db.execute(
                f"SELECT sample_id,features_json,outcome FROM ml_grounded_sample "
                f"WHERE sample_id IN ({placeholders}) ORDER BY outcome_at,sample_id",
                manifest.holdout_ids,
            ).fetchall()
            correct_baseline = correct_candidate = scored = unknown = 0
            for sample_id, raw_features, raw_outcome in rows:
                expected = OutcomeClass(raw_outcome)
                if expected is OutcomeClass.UNKNOWN:
                    unknown += 1
                    continue
                features = json.loads(raw_features)
                first = baseline(features)
                second = candidate(features)
                if not isinstance(first, OutcomeClass) or not isinstance(second, OutcomeClass):
                    raise TypeError("evaluators must return typed OutcomeClass")
                scored += 1
                correct_baseline += int(first is expected)
                correct_candidate += int(second is expected)
            baseline_accuracy = None if not scored else correct_baseline / scored
            candidate_accuracy = None if not scored else correct_candidate / scored
            delta = None if not scored else candidate_accuracy - baseline_accuracy
            body = {
                "manifest_id": manifest_id, "baseline_digest": baseline_digest,
                "candidate_digest": candidate_digest, "evaluated_at": moment.isoformat(),
                "baseline_accuracy": baseline_accuracy, "candidate_accuracy": candidate_accuracy,
                "paired_delta": delta, "scored": scored, "unknown": unknown,
                "holdout_digest": _digest(manifest.holdout_ids),
            }
            evaluation_id = "ml-evaluation:" + _digest(body)
            db.execute(
                "INSERT OR IGNORE INTO ml_evaluation VALUES(?,?,?,?)",
                (evaluation_id, manifest_id, _canonical(body), moment.isoformat()),
            )
        return EvaluationResult(
            evaluation_id=evaluation_id, manifest_id=manifest_id,
            baseline_digest=baseline_digest,
            candidate_digest=candidate_digest, evaluated_at=moment,
            baseline_accuracy=baseline_accuracy,
            candidate_accuracy=candidate_accuracy, paired_delta=delta,
            scored=scored, unknown=unknown,
            holdout_digest=body["holdout_digest"],
        )

    def mode(self) -> PredictionMode:
        with closing(self._connect()) as db:
            row = db.execute("SELECT mode FROM ml_operating_state WHERE singleton=1").fetchone()
        return PredictionMode(row[0])

    def set_mode(self, mode: PredictionMode, *, at: datetime, approval_ref: str | None = None) -> None:
        if not isinstance(mode, PredictionMode):
            raise TypeError("mode must be PredictionMode")
        if mode in (PredictionMode.ADVISORY, PredictionMode.LIMITED) and (
            not isinstance(approval_ref, str)
            or not approval_ref.startswith(("owner-ui:", "safe:"))
        ):
            raise PermissionError("advisory/limited mode needs independent owner/SAFE approval")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if mode in (PredictionMode.ADVISORY, PredictionMode.LIMITED):
                if self._approval is None:
                    raise PermissionError("SAFE prediction-mode approval verifier is unavailable")
                self._approval.consume(
                    approval_id=approval_ref,
                    capability="learning.mode.set",
                    parameters={"mode": mode.value}, now=_utc(at, "at"),
                    _transaction_db=db,
                )
            db.execute(
                "UPDATE ml_operating_state SET mode=?,revision=revision+1,changed_at=?,approval_ref=?,revoked=0 WHERE singleton=1",
                (mode.value, _utc(at, "at").isoformat(), approval_ref),
            )

    def revoke_mode(self, *, at: datetime, approval_ref: str) -> None:
        if not approval_ref.startswith(("owner-ui:", "safe:", "operator-stop:")):
            raise PermissionError("authenticated mode revocation required")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if not approval_ref.startswith("operator-stop:"):
                if self._approval is None:
                    raise PermissionError("SAFE prediction-mode revocation verifier is unavailable")
                self._approval.consume(
                    approval_id=approval_ref,
                    capability="learning.mode.revoke",
                    parameters={"mode": PredictionMode.SHADOW.value},
                    now=_utc(at, "at"), _transaction_db=db,
                )
            db.execute(
                "UPDATE ml_operating_state SET mode=?,revision=revision+1,changed_at=?,approval_ref=?,revoked=1 WHERE singleton=1",
                (PredictionMode.SHADOW.value, _utc(at, "at").isoformat(), approval_ref),
            )

    def record_prediction(self, prediction: Prediction) -> None:
        if not isinstance(prediction, Prediction):
            raise TypeError("typed Prediction required")
        current = self.mode()
        if prediction.mode is not current:
            raise PermissionError("prediction mode differs from current canonical mode")
        body = {
            "prediction_id": prediction.prediction_id,
            "candidate_digest": prediction.candidate_digest,
            "subject_id": prediction.subject_id,
            "principal_id": prediction.principal_id,
            "audience_id": prediction.audience_id,
            "generated_at": prediction.generated_at.astimezone(timezone.utc).isoformat(),
            "expires_at": prediction.expires_at.astimezone(timezone.utc).isoformat(),
            "mode": prediction.mode.value, "value": dict(prediction.value),
            "uncertainty": prediction.uncertainty,
            "reason_refs": prediction.reason_refs,
            "grants_authority": False, "is_factual_evidence": False,
            "grants_consent": False,
        }
        with closing(self._connect()) as db, db:
            try:
                db.execute(
                    "INSERT INTO ml_prediction_trace VALUES(?,?,?,?,?,?,0)",
                    (prediction.prediction_id, prediction.principal_id,
                     prediction.audience_id, prediction.mode.value,
                     _canonical(body), body["generated_at"]),
                )
            except sqlite3.IntegrityError as exc:
                prior = db.execute(
                    "SELECT body_json FROM ml_prediction_trace WHERE prediction_id=?",
                    (prediction.prediction_id,),
                ).fetchone()
                if prior is None or prior[0] != _canonical(body):
                    raise PermissionError("prediction replay changed immutable trace") from exc

    def diagnostics(self, *, principal_id: str, audience_id: str, limit: int = 20) -> dict:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("diagnostic limit must be in [1, 100]")
        with closing(self._connect()) as db:
            state = db.execute(
                "SELECT mode,revision,changed_at,revoked FROM ml_operating_state WHERE singleton=1"
            ).fetchone()
            traces = db.execute(
                "SELECT body_json FROM ml_prediction_trace WHERE principal_id=? AND audience_id=? "
                "ORDER BY created_at DESC LIMIT ?",
                (principal_id, audience_id, limit),
            ).fetchall()
        return {
            "mode": state[0], "revision": state[1], "changed_at": state[2],
            "revoked": bool(state[3]), "recommendations_execute_actions": False,
            "predictions_are_evidence": False, "traces": tuple(json.loads(row[0]) for row in traces),
        }

    def enforce_retention(self, *, at: datetime, limit: int = 500) -> dict[str, int]:
        """Delete expired/revoked samples and every derived manifest/evaluation.

        This bounded callback is registered with the existing application
        background coordinator; it is not an ML scheduler.
        """
        moment = _utc(at, "at")
        if type(limit) is not int or not 1 <= limit <= 5000:
            raise ValueError("retention batch limit must be in [1, 5000]")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("""
                SELECT s.sample_id FROM ml_grounded_sample s
                JOIN ml_data_use_grant g ON g.grant_id=s.grant_id
                LEFT JOIN ml_data_use_revocation gr ON gr.grant_id=g.grant_id
                LEFT JOIN ml_source_revocation sr ON sr.source_ref=s.source_ref
                LEFT JOIN ml_source_revocation orv ON orv.source_ref=s.outcome_ref
                WHERE s.retention_until<=? OR g.expires_at<=?
                   OR gr.grant_id IS NOT NULL OR sr.source_ref IS NOT NULL
                   OR orv.source_ref IS NOT NULL
                ORDER BY s.retention_until,s.sample_id LIMIT ?
            """, (moment.isoformat(), moment.isoformat(), limit)).fetchall()
            expired = {row[0] for row in rows}
            manifests = []
            if expired:
                for manifest_id, raw in db.execute(
                    "SELECT manifest_id,body_json FROM ml_dataset_manifest"
                ).fetchall():
                    if expired.intersection(json.loads(raw)["sample_ids"]):
                        manifests.append(manifest_id)
                if manifests:
                    marks = ",".join("?" for _ in manifests)
                    db.execute(f"DELETE FROM ml_evaluation WHERE manifest_id IN ({marks})", manifests)
                    db.execute(f"DELETE FROM ml_dataset_manifest WHERE manifest_id IN ({marks})", manifests)
                marks = ",".join("?" for _ in expired)
                db.execute(f"DELETE FROM ml_grounded_sample WHERE sample_id IN ({marks})", tuple(expired))
        return {"samples_deleted": len(expired), "manifests_deleted": len(manifests)}
