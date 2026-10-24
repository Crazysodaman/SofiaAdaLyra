"""Core B07 bridge for evidence-backed maintenance proposals and learning.

Core may notice, explain and request work. Platform/SAFE/RUN remain the only
owners of authorization and effects.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

from sofia.core.modreg.manifest import ModuleManifest
from sofia.core.modreg.platform import OutcomeObservation, OutcomeStatus, PlatformModuleObserver
from sofia.core.modreg.proposals import ModuleProposalRecord, ProposalAction
from sofia.core.modreg.self_model import CapabilitySelfModel, Grounding
from sofia.core.modreg.workshop import WorkshopDevelopmentRequest, WorkshopRequestService
from sofia.core.social.model import PrincipalContext
from sofia.core.social.principals import SOFIA_PRINCIPAL_ID, SPARKS_PRINCIPAL_ID
from sofia.platform.application.autonomous_work import AutonomousWorkCoordinator, ImprovementDiagnostic
from sofia.platform.run.github_update_watch import UpdateObservation
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("maintenance timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class MaintenanceAssessment:
    assessment_id: str
    module_id: str
    condition: str
    explanation: str
    evidence_refs: tuple[str, ...]
    recovery_options: tuple[str, ...]
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class MaintenanceRequest:
    request_id: str
    kind: str
    subject: str
    status: str
    reason: str
    evidence_refs: tuple[str, ...]
    requested_by: str
    requested_at: datetime
    outcome_ref: str | None


class CoreMaintenanceService:
    """Application-owned Core/Platform seam; no method performs an effect."""

    def __init__(
        self, *, state_path: Path | str, awareness: CapabilitySelfModel,
        observer: PlatformModuleObserver, workshop: WorkshopRequestService,
        autonomous_work: AutonomousWorkCoordinator,
    ) -> None:
        if not isinstance(awareness, CapabilitySelfModel):
            raise TypeError("awareness must be CapabilitySelfModel")
        if not isinstance(observer, PlatformModuleObserver):
            raise TypeError("observer must be PlatformModuleObserver")
        if not isinstance(workshop, WorkshopRequestService):
            raise TypeError("workshop must be WorkshopRequestService")
        if not isinstance(autonomous_work, AutonomousWorkCoordinator):
            raise TypeError("autonomous_work must be AutonomousWorkCoordinator")
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        self.awareness = awareness
        self.observer = observer
        self.workshop = workshop
        self.autonomous_work = autonomous_work
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS core_maintenance_assessment(
                    assessment_id TEXT PRIMARY KEY,module_id TEXT NOT NULL,
                    condition TEXT NOT NULL,explanation TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL,recovery_options_json TEXT NOT NULL,
                    observed_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS core_maintenance_assessment_recent
                    ON core_maintenance_assessment(observed_at DESC,assessment_id DESC);
                CREATE TABLE IF NOT EXISTS core_maintenance_request(
                    request_id TEXT PRIMARY KEY,kind TEXT NOT NULL,subject TEXT NOT NULL,
                    status TEXT NOT NULL,reason TEXT NOT NULL,evidence_refs_json TEXT NOT NULL,
                    requested_by TEXT NOT NULL,requested_at TEXT NOT NULL,outcome_ref TEXT);
                CREATE TABLE IF NOT EXISTS core_maintenance_lesson(
                    outcome_request_id TEXT PRIMARY KEY,module_id TEXT NOT NULL,
                    capability TEXT NOT NULL,status TEXT NOT NULL,
                    verification_method TEXT,settled_at TEXT NOT NULL,
                    lesson TEXT NOT NULL);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _requester(principal: PrincipalContext) -> str:
        if not isinstance(principal, PrincipalContext):
            raise TypeError("principal must be PrincipalContext")
        if principal.principal_id == SOFIA_PRINCIPAL_ID:
            if principal.audience_id != "system:core" or principal.audience_kind.value != "system":
                raise PermissionError("invalid Sofía Core maintenance scope")
        elif principal.principal_id != SPARKS_PRINCIPAL_ID:
            raise PermissionError("maintenance requests require owner or host-bound Core")
        return principal.principal_id

    def troubleshoot(self, module_id: str, *, now: datetime) -> MaintenanceAssessment:
        if not isinstance(module_id, str) or _ID.fullmatch(module_id) is None:
            raise ValueError("module_id must be a bounded identifier")
        moment = _utc(now)
        row = next((item for item in self.awareness.project(now=moment) if item.module_id == module_id), None)
        if row is None:
            condition = "unknown"
            explanation = "No current registry or Platform observation identifies this module."
            options = ("inspect signed module registry", "request fresh Platform observation")
            evidence = ()
        else:
            evidence = tuple(row.notes)
            if row.healthy is Grounding.NO:
                condition = "fault_observed"
                explanation = "Platform observations report an unhealthy or blocked required component."
                options = ("inspect component health evidence", "prepare authorized recovery request")
            elif row.healthy is Grounding.YES:
                condition = "healthy_observed"
                explanation = "Fresh Platform component observations currently report healthy state."
                options = ("no recovery proposed",)
            else:
                condition = "health_unknown"
                explanation = "No fresh component observation proves current health."
                options = ("request a non-effectful health probe", "keep activation/restart blocked")
        assessment = MaintenanceAssessment(
            f"assessment:{uuid4()}", module_id, condition, explanation,
            evidence, options, moment,
        )
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO core_maintenance_assessment VALUES(?,?,?,?,?,?,?)",
                (assessment.assessment_id, module_id, condition, explanation,
                 json.dumps(evidence), json.dumps(options), moment.isoformat()),
            )
        return assessment

    def request_restart(
        self, principal: PrincipalContext, *, subject: str, reason: str,
        evidence_refs: tuple[str, ...], now: datetime,
    ) -> MaintenanceRequest:
        requester = self._requester(principal)
        if not isinstance(subject, str) or _ID.fullmatch(subject) is None:
            raise ValueError("restart subject must be a bounded identifier")
        return self._create_request(
            kind="supervised_restart", subject=subject, reason=reason,
            evidence_refs=evidence_refs, requester=requester, now=now,
        )

    def propose_verified_update(
        self, principal: PrincipalContext, observation: UpdateObservation,
    ) -> MaintenanceRequest:
        requester = self._requester(principal)
        if not isinstance(observation, UpdateObservation):
            raise TypeError("observation must be UpdateObservation")
        if observation.status != "signed_release_available" or observation.verified_release is None:
            raise ValueError("only an independently verified signed release may be proposed")
        release = observation.verified_release
        return self._create_request(
            kind="verified_update", subject=release.release_id,
            reason="A signed exact-revision release is available for guarded activation.",
            evidence_refs=(f"release:{release.manifest_sha256}",),
            requester=requester, now=observation.observed_at,
        )

    def _create_request(
        self, *, kind: str, subject: str, reason: str,
        evidence_refs: tuple[str, ...], requester: str, now: datetime,
    ) -> MaintenanceRequest:
        moment = _utc(now)
        if not reason.strip() or len(reason) > 800:
            raise ValueError("maintenance reason must be bounded")
        if not evidence_refs or len(evidence_refs) > 16 or any(
            not isinstance(item, str) or _ID.fullmatch(item) is None
            for item in evidence_refs
        ):
            raise ValueError("maintenance request requires bounded evidence refs")
        fingerprint = sha256(json.dumps(
            [kind, subject, list(evidence_refs), requester], separators=(",", ":")
        ).encode()).hexdigest()
        request_id = f"corereq:{fingerprint[:40]}"
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT OR IGNORE INTO core_maintenance_request VALUES(?,?,?,?,?,?,?,?,NULL)",
                (request_id, kind, subject, "requested", reason.strip(),
                 json.dumps(list(evidence_refs)), requester, moment.isoformat()),
            )
            row = db.execute(
                "SELECT * FROM core_maintenance_request WHERE request_id=?",
                (request_id,),
            ).fetchone()
        if row["reason"] != reason.strip():
            raise RuntimeError("maintenance request identity collision")
        return self._decode_request(row)

    @staticmethod
    def _decode_request(row: sqlite3.Row) -> MaintenanceRequest:
        return MaintenanceRequest(
            row["request_id"], row["kind"], row["subject"], row["status"],
            row["reason"], tuple(json.loads(row["evidence_refs_json"])),
            row["requested_by"], datetime.fromisoformat(row["requested_at"]),
            row["outcome_ref"],
        )

    def reconcile_request(self, outcome: OutcomeObservation) -> MaintenanceRequest:
        if not isinstance(outcome, OutcomeObservation):
            raise TypeError("outcome must be OutcomeObservation")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM core_maintenance_request WHERE request_id=?",
                (outcome.request_id,),
            ).fetchone()
            if row is None:
                raise LookupError("outcome does not match a Core maintenance request")
            current = self._decode_request(row)
            if current.status != "requested":
                return current
            if outcome.status is OutcomeStatus.SUCCEEDED_VERIFIED:
                status = "verified"
            elif outcome.status in {
                OutcomeStatus.OUTCOME_UNKNOWN,
                OutcomeStatus.SUCCEEDED_REPORTED_UNVERIFIED,
            }:
                status = "uncertain"
            elif outcome.status is OutcomeStatus.DENIED:
                status = "denied"
            else:
                status = "failed"
            outcome_ref = f"module-outcome:{outcome.request_id}"
            db.execute(
                "UPDATE core_maintenance_request SET status=?,outcome_ref=? "
                "WHERE request_id=? AND status='requested'",
                (status, outcome_ref, outcome.request_id),
            )
            row = db.execute(
                "SELECT * FROM core_maintenance_request WHERE request_id=?",
                (outcome.request_id,),
            ).fetchone()
        return self._decode_request(row)

    def learn_verified_outcomes(self, *, limit: int = 32) -> int:
        """Persist exact operational lessons; never beliefs or permissions."""
        if type(limit) is not int or not 1 <= limit <= 128:
            raise ValueError("limit must be in 1..128")
        learned = 0
        for outcome in self.observer.outcomes()[:limit]:
            if outcome.status is not OutcomeStatus.SUCCEEDED_VERIFIED:
                continue
            if not outcome.verification_method:
                continue
            lesson = (
                f"{outcome.module_id} capability {outcome.capability} had a "
                f"verified successful outcome via {outcome.verification_method}."
            )
            with closing(self._connect()) as db, db:
                changed = db.execute(
                    "INSERT OR IGNORE INTO core_maintenance_lesson VALUES(?,?,?,?,?,?,?)",
                    (outcome.request_id, outcome.module_id, outcome.capability,
                     outcome.status.value, outcome.verification_method,
                     _utc(outcome.settled_at).isoformat(), lesson),
                )
            learned += int(changed.rowcount == 1)
        return learned

    def prepare_development_handoff(
        self, principal: PrincipalContext, *, proposal: ModuleProposalRecord,
        manifest: ModuleManifest, test_targets: tuple[str, ...], now: datetime,
    ) -> WorkshopDevelopmentRequest:
        if proposal.action not in {
            ProposalAction.DEVELOP, ProposalAction.IMPROVE, ProposalAction.REPLACE,
        }:
            raise ValueError("proposal action does not require Workshop development")
        if proposal.target_module != manifest.name:
            raise ValueError("proposal target and manifest differ")
        return self.workshop.prepare(
            principal, manifest=manifest, test_targets=test_targets,
            proposal_ref=proposal.proposal_id, recorded_at=_utc(now),
        )

    def submit_handoff_to_engineering(
        self, principal: PrincipalContext, *, request: WorkshopDevelopmentRequest,
        allowed_paths: tuple[str, ...], success_metric: str, now: datetime,
    ) -> WorkshopDevelopmentRequest:
        if principal.principal_id != SPARKS_PRINCIPAL_ID:
            raise PermissionError("only authenticated owner may submit Workshop work")
        submitted = self.workshop.mark_submitted(
            principal, manifest_name=request.manifest.name,
            expected_revision=request.revision,
            submission_ref=f"core-b07:{request.request_id}", recorded_at=_utc(now),
        )
        diagnostic = ImprovementDiagnostic(
            diagnostic_id=request.request_id,
            source_ref=f"workshop:{request.request_id}",
            summary=f"Build reviewed module candidate {request.manifest.name}",
            details={
                "module": request.manifest.name,
                "version": request.manifest.version,
                "proposal_ref": request.proposal_ref,
            },
            allowed_paths=allowed_paths, tests=request.test_targets,
            success_metric=success_metric, observed_at=_utc(now), severity=55,
        )
        self.autonomous_work.record_diagnostic(diagnostic)
        return submitted

    def placement_assessment(self, module_id: str) -> str:
        rows = [row for row in self.awareness.project() if row.module_id == module_id]
        if not rows or not rows[0].placements:
            return "No verified placement observation is available; no move is proposed."
        placements = ", ".join(
            f"{component}@{host} ({mode})"
            for component, host, mode in rows[0].placements
        )
        return (
            f"Observed placement: {placements}. This is advisory only; host moves "
            "still require Platform admission, resources, leases and authorization."
        )

    @staticmethod
    def explain_proposal(proposal: ModuleProposalRecord) -> str:
        permissions = ", ".join(proposal.permissions_needed) or "none declared"
        return (
            f"I propose to {proposal.action.value} {proposal.target_module} because "
            f"{proposal.motivation} Expected benefit: {proposal.benefits} "
            f"Risks: {proposal.risks} Permissions that Platform must decide: "
            f"{permissions}. This proposal grants no authority and reports no work done."
        )

    def working_context(self, *, limit: int = 1800) -> str:
        if type(limit) is not int or not 400 <= limit <= 4000:
            raise ValueError("context limit must be 400..4000")
        with closing(self._connect()) as db:
            requests = db.execute(
                "SELECT * FROM core_maintenance_request ORDER BY requested_at DESC LIMIT 6"
            ).fetchall()
            lessons = db.execute(
                "SELECT lesson FROM core_maintenance_lesson ORDER BY settled_at DESC LIMIT 6"
            ).fetchall()
        lines = ["CORE MAINTENANCE CONTINUITY (requests are not permission or execution):"]
        for row in requests:
            lines.append(
                f'- {row["kind"]} {row["subject"]}: {row["status"]}; {row["reason"]}'
            )
        for row in lessons:
            lines.append("- verified lesson: " + row[0])
        if len(lines) == 1:
            lines.append("- No maintenance request or verified outcome is recorded.")
        return "\n".join(lines)[:limit]
