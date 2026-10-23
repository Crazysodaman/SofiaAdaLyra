"""GA-021..040 durable learning projections over existing production owners.

Nothing in this module executes work, grants authority, captures a screen,
promotes memory, or deploys a model. It records independently checkable links
between canonical evidence, RUN outcomes, LIFE procedures, and VERIFY results.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from typing import Iterable
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from sofia.core.goals.evidence import GoalEvidenceIndex
from sofia.core.goals.service import GoalService
from sofia.core.learning.contracts import DataUse
from sofia.platform.run.work import DurableWorkStore, WorkStatus
from sofia.core.social.model import AudienceKind, PrincipalContext
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard
from sofia.platform.verify.generalization_transfer import assess_signed_transfer


_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_FAILURE_CLASSES = {
    "tool_fault", "permission_denied", "stale_observation", "planning_error",
    "environment_drift", "unknown",
}
_EPISTEMIC = {"verified_fact", "supported_inference", "simulation", "speculation"}


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


def _id(value: str, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


def _text(value: str, label: str, maximum: int = 1200) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{label} must be bounded nonempty text")
    return value.strip()


def _digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _revoked_sources(db: sqlite3.Connection) -> set[str]:
    exists = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ml_source_revocation'"
    ).fetchone()
    if exists is None:
        return set()
    return {row[0] for row in db.execute("SELECT source_ref FROM ml_source_revocation")}


@dataclass(frozen=True, slots=True)
class FailureHypothesis:
    explanation: str
    falsifier: str
    discriminating_observation: str

    def __post_init__(self) -> None:
        _text(self.explanation, "hypothesis", 800)
        _text(self.falsifier, "falsifier", 800)
        _text(self.discriminating_observation, "discriminating observation", 800)


@dataclass(frozen=True, slots=True)
class EpisodePhase:
    kind: str
    summary: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.kind not in {"intent", "observation", "hypothesis", "action", "outcome", "correction"}:
            raise ValueError("unsupported episode phase")
        _text(self.summary, "phase summary", 1000)
        if (
            not self.evidence_refs
            or len(self.evidence_refs) > 16
            or len(set(self.evidence_refs)) != len(self.evidence_refs)
        ):
            raise ValueError("phase evidence must be nonempty, unique, and bounded")


class AdvancedGeneralizationStore:
    """One canonical, authority-free owner for GA-021..040 records."""

    PURPOSE = "generalization-lifelong-learning"

    def __init__(self, state_path: str | Path, *, goals: GoalService, admission, learning) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        self._evidence = GoalEvidenceIndex(self.path)
        self._work = DurableWorkStore(self.path)
        self._goals = goals
        self._admission = admission
        self._learning = learning
        self._skills = None
        with closing(self._connect()) as db, db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS ga_failure(
              failure_id TEXT PRIMARY KEY, principal_id TEXT NOT NULL,audience_id TEXT NOT NULL,
              objective TEXT NOT NULL,observed_state TEXT NOT NULL,job_id TEXT NOT NULL,
              attempted_actions_json TEXT NOT NULL,evidence_refs_json TEXT NOT NULL,
              error_text TEXT NOT NULL,uncertain INTEGER NOT NULL,failure_class TEXT NOT NULL,
              source_digest TEXT NOT NULL UNIQUE,occurred_at TEXT NOT NULL,retention_until TEXT NOT NULL,
              status TEXT NOT NULL CHECK(status IN('current','invalidated')));
            CREATE TABLE IF NOT EXISTS ga_failure_hypothesis(
              failure_id TEXT NOT NULL,hypothesis_id TEXT NOT NULL,explanation TEXT NOT NULL,
              falsifier TEXT NOT NULL,discriminating_observation TEXT NOT NULL,
              status TEXT NOT NULL CHECK(status IN('hypothesis','supported','rejected','invalidated')),
              evidence_refs_json TEXT NOT NULL,created_at TEXT NOT NULL,
              PRIMARY KEY(failure_id,hypothesis_id));
            CREATE TABLE IF NOT EXISTS ga_retry_plan(
              retry_id TEXT PRIMARY KEY,failure_id TEXT NOT NULL,job_id TEXT NOT NULL,
              justification TEXT NOT NULL,changed_action TEXT NOT NULL,max_attempts INTEGER NOT NULL,
              rollback_ref TEXT,status TEXT NOT NULL,created_at TEXT NOT NULL,
              UNIQUE(failure_id,job_id));
            CREATE TABLE IF NOT EXISTS ga_failure_study(
              failure_id TEXT NOT NULL,study_id TEXT NOT NULL,comparison_kind TEXT NOT NULL,
              bound_at TEXT NOT NULL,PRIMARY KEY(failure_id,study_id));
            CREATE TABLE IF NOT EXISTS ga_experience_episode(
              episode_id TEXT PRIMARY KEY,principal_id TEXT NOT NULL,audience_id TEXT NOT NULL,
              subject_id TEXT NOT NULL,context_tags_json TEXT NOT NULL,phases_json TEXT NOT NULL,
              source_refs_json TEXT NOT NULL,outcome_verified INTEGER NOT NULL,
              occurred_at TEXT NOT NULL,recorded_at TEXT NOT NULL,retention_until TEXT NOT NULL,
              status TEXT NOT NULL CHECK(status IN('current','corrected','revoked','expired')),
              correction_of TEXT,record_digest TEXT NOT NULL UNIQUE);
            CREATE INDEX IF NOT EXISTS ga_episode_scope ON ga_experience_episode(
              principal_id,audience_id,occurred_at DESC);
            CREATE TABLE IF NOT EXISTS ga_principle(
              principle_id TEXT PRIMARY KEY,principal_id TEXT NOT NULL,audience_id TEXT NOT NULL,
              statement TEXT NOT NULL,epistemic_status TEXT NOT NULL,confidence REAL NOT NULL,
              episode_ids_json TEXT NOT NULL,evidence_refs_json TEXT NOT NULL,
              status TEXT NOT NULL CHECK(status IN('candidate','verified','invalidated','revoked')),
              created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS ga_planning_influence(
              trace_id TEXT PRIMARY KEY,goal_id TEXT NOT NULL,principal_id TEXT NOT NULL,
              audience_id TEXT NOT NULL,episode_ids_json TEXT NOT NULL,reason TEXT NOT NULL,
              ablation TEXT NOT NULL CHECK(ablation IN('with_experience','without_experience')),
              created_at TEXT NOT NULL,authority INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS ga_environment_observation(
              observation_id TEXT PRIMARY KEY,principal_id TEXT NOT NULL,audience_id TEXT NOT NULL,
              environment_id TEXT NOT NULL,platform TEXT NOT NULL,route TEXT NOT NULL,
              version_id TEXT,permit_ref TEXT NOT NULL,evidence_ref TEXT NOT NULL,
              observed_at TEXT NOT NULL,expires_at TEXT NOT NULL,record_digest TEXT NOT NULL UNIQUE);
            CREATE TABLE IF NOT EXISTS ga_environment_model(
              model_id TEXT PRIMARY KEY,principal_id TEXT NOT NULL,audience_id TEXT NOT NULL,
              environment_id TEXT NOT NULL,revision INTEGER NOT NULL,status TEXT NOT NULL,
              transitions_json TEXT NOT NULL,evidence_refs_json TEXT NOT NULL,
              confidence REAL NOT NULL,contradictions_json TEXT NOT NULL,updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS ga_environment_experiment(
              experiment_id TEXT PRIMARY KEY,model_id TEXT NOT NULL,job_id TEXT NOT NULL,
              environment_kind TEXT NOT NULL,rival_hypotheses_json TEXT NOT NULL,
              discriminating_result TEXT,status TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS ga_transfer_application(
              transfer_id TEXT PRIMARY KEY,skill_id TEXT NOT NULL,source_environment TEXT NOT NULL,
              target_environment TEXT NOT NULL,target_platform TEXT NOT NULL,run_id TEXT NOT NULL,
              baseline_run_id TEXT NOT NULL,principal_id TEXT NOT NULL,audience_id TEXT NOT NULL,
              status TEXT NOT NULL,evidence_ref TEXT NOT NULL,created_at TEXT NOT NULL,
              UNIQUE(skill_id,target_environment,run_id));
            CREATE TABLE IF NOT EXISTS ga_blind_study(
              study_id TEXT PRIMARY KEY,principal_id TEXT NOT NULL,audience_id TEXT NOT NULL,
              revision TEXT NOT NULL,domain_a TEXT NOT NULL,domain_b TEXT NOT NULL,
              sealed_digest TEXT NOT NULL UNIQUE,assessment_json TEXT NOT NULL,
              evidence_supports_transfer INTEGER NOT NULL,resource_fit INTEGER NOT NULL,
              privacy_correct INTEGER NOT NULL,authority_correct INTEGER NOT NULL,
              rollback_ready INTEGER NOT NULL,restart_correct INTEGER NOT NULL,
              promotion_evidence_refs_json TEXT NOT NULL,promotion_eligible INTEGER NOT NULL,
              recorded_at TEXT NOT NULL,model_digest TEXT);
            CREATE TABLE IF NOT EXISTS ga_candidate_promotion_gate(
              candidate_id TEXT PRIMARY KEY,study_id TEXT NOT NULL UNIQUE,
              candidate_digest TEXT NOT NULL,principal_id TEXT NOT NULL,
              audience_id TEXT NOT NULL,claimed_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS ga_benchmark_registry(
              benchmark_id TEXT PRIMARY KEY,name TEXT NOT NULL,version TEXT NOT NULL,
              family TEXT NOT NULL,license_id TEXT NOT NULL,source_digest TEXT NOT NULL,
              private_holdout INTEGER NOT NULL,content_stored INTEGER NOT NULL DEFAULT 0,
              registered_at TEXT NOT NULL,UNIQUE(name,version));
            """)
            blind_columns = {
                row[1] for row in db.execute("PRAGMA table_info(ga_blind_study)")
            }
            if "model_digest" not in blind_columns:
                db.execute("ALTER TABLE ga_blind_study ADD COLUMN model_digest TEXT")

    def attach_skills(self, skills) -> None:
        self._skills = skills

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def _scoped_refs(self, refs: Iterable[str], principal: PrincipalContext) -> tuple:
        values = tuple(refs)
        if not values or len(values) > 32 or len(set(values)) != len(values):
            raise ValueError("nonempty unique bounded evidence refs required")
        records = tuple(self._evidence.lookup(ref) for ref in values)
        if any(record is None or record.principal_id != principal.principal_id or record.audience != principal.audience_id for record in records):
            raise PermissionError("evidence principal/audience scope mismatch")
        return records

    def _grant(self, principal: PrincipalContext, *, at: datetime):
        grant = self._learning.active_grant(
            principal_id=principal.principal_id, audience_id=principal.audience_id,
            purpose=self.PURPOSE,
            required=(DataUse.OBSERVATION, DataUse.STORAGE, DataUse.FEATURE_EXTRACTION),
            at=_utc(at),
        )
        if grant is None:
            raise PermissionError("active exact lifelong-learning data-use grant required")
        return grant

    def record_failure(
        self, *, principal: PrincipalContext, objective: str, observed_state: str,
        job_id: str, attempted_actions: tuple[str, ...], evidence_refs: tuple[str, ...],
        error_text: str, retention_until: datetime, now: datetime,
    ) -> str:
        moment = _utc(now); retained = _utc(retention_until)
        grant = self._grant(principal, at=moment)
        if retained <= moment or retained - moment > __import__('datetime').timedelta(days=365):
            raise ValueError("failure retention must be positive and bounded")
        if retained > _utc(grant.expires_at):
            raise PermissionError("failure retention exceeds data-use grant")
        records = self._scoped_refs(evidence_refs, principal)
        if not any(
            record.kind == "operation_receipt" and record.successful is not True
            for record in records
        ):
            raise PermissionError("failure requires a non-success operation receipt")
        job = self._work.get(job_id)
        if job.status not in {WorkStatus.FAILED, WorkStatus.UNCERTAIN, WorkStatus.BLOCKED, WorkStatus.CANCELLED}:
            raise PermissionError("failure requires a canonical non-success RUN outcome")
        if job.payload.get("principal_id") != principal.principal_id or job.payload.get("audience_id") != principal.audience_id:
            raise PermissionError("failure RUN scope mismatch")
        actions = tuple(_id(value, "action") for value in attempted_actions)
        if len(actions) > 16 or len(set(actions)) != len(actions):
            raise ValueError("attempted actions must be unique and bounded")
        reason = (job.reason or "").casefold() + " " + error_text.casefold()
        kind = "unknown"
        for tokens, value in ((('permission','denied','approval'), 'permission_denied'),
                              (('stale','expired'), 'stale_observation'),
                              (('tool','provider','adapter'), 'tool_fault'),
                              (('plan','dependency','precondition'), 'planning_error'),
                              (('changed','drift','version'), 'environment_drift')):
            if any(token in reason for token in tokens): kind = value; break
        body = {"scope": (principal.principal_id, principal.audience_id),
                "objective": _text(objective, "objective"), "state": _text(observed_state, "observed state"),
                "job": job_id, "actions": actions, "refs": evidence_refs,
                "error": _text(error_text, "error", 1600), "uncertain": job.status is WorkStatus.UNCERTAIN,
                "class": kind, "occurred": job.updated_at.isoformat()}
        digest = _digest(body); failure_id = "ga-failure:" + digest[:24]
        with closing(self._connect()) as db, db:
            db.execute("INSERT OR IGNORE INTO ga_failure VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (failure_id,principal.principal_id,principal.audience_id,body['objective'],body['state'],job_id,
                 json.dumps(actions),json.dumps(evidence_refs),body['error'],int(body['uncertain']),kind,digest,
                 job.updated_at.isoformat(),retained.isoformat(),'current'))
        return failure_id

    def reflect_failure(self, failure_id: str, *, principal: PrincipalContext,
                        hypotheses: tuple[FailureHypothesis, ...], now: datetime) -> tuple[str, ...]:
        if len(hypotheses) < 2 or len(hypotheses) > 8 or len({h.explanation for h in hypotheses}) != len(hypotheses):
            raise ValueError("two to eight distinct falsifiable hypotheses required")
        with closing(self._connect()) as db, db:
            failure = db.execute("SELECT principal_id,audience_id,status FROM ga_failure WHERE failure_id=?",(failure_id,)).fetchone()
            if failure is None or tuple(failure[:2]) != (principal.principal_id,principal.audience_id) or failure[2] != 'current':
                raise PermissionError("current scoped failure required")
            ids=[]
            for item in hypotheses:
                hid="ga-hypothesis:"+_digest(asdict(item))[:24]; ids.append(hid)
                db.execute("INSERT OR IGNORE INTO ga_failure_hypothesis VALUES(?,?,?,?,?,'hypothesis','[]',?)",
                           (failure_id,hid,item.explanation,item.falsifier,item.discriminating_observation,_utc(now).isoformat()))
        return tuple(ids)

    def plan_retry(self, failure_id: str, *, principal: PrincipalContext, job_id: str,
                   justification: str, changed_action: str, max_attempts: int,
                   rollback_ref: str | None, now: datetime) -> str:
        if type(max_attempts) is not int or not 1 <= max_attempts <= 3:
            raise ValueError("retry cap must be 1..3")
        job=self._work.get(job_id)
        with closing(self._connect()) as db, db:
            failure=db.execute("SELECT * FROM ga_failure WHERE failure_id=?",(failure_id,)).fetchone()
            if failure is None or (failure['principal_id'],failure['audience_id']) != (principal.principal_id,principal.audience_id):
                raise PermissionError("failure scope mismatch")
            prior=self._work.get(failure['job_id'])
            if prior.status is WorkStatus.UNCERTAIN and prior.fingerprint == job.fingerprint:
                raise PermissionError("uncertain external effect cannot be replayed")
            if job.payload.get('principal_id') != principal.principal_id or job.payload.get('audience_id') != principal.audience_id:
                raise PermissionError("retry RUN scope mismatch")
            if job.risk != 'read_only' and not rollback_ref:
                raise PermissionError("mutable retry requires rollback reference")
            prior_plan = db.execute(
                "SELECT retry_id,justification,changed_action,max_attempts,rollback_ref "
                "FROM ga_retry_plan WHERE failure_id=? AND job_id=?",
                (failure_id, job_id),
            ).fetchone()
            requested = (
                _text(justification,'justification'),
                _text(changed_action,'changed action'), max_attempts, rollback_ref,
            )
            if prior_plan is not None:
                if tuple(prior_plan[1:]) != requested:
                    raise PermissionError("retry replay changed immutable plan")
                return prior_plan[0]
            retry_id='ga-retry:'+uuid4().hex
            db.execute("INSERT INTO ga_retry_plan VALUES(?,?,?,?,?,?,?,'proposed',?)",
                       (retry_id,failure_id,job_id,*requested,_utc(now).isoformat()))
        return retry_id

    def record_episode(self, *, principal: PrincipalContext, subject_id: str,
                       context_tags: tuple[str, ...], phases: tuple[EpisodePhase, ...],
                       occurred_at: datetime, retention_until: datetime,
                       correction_of: str | None = None, now: datetime) -> str:
        ordered=("intent","observation","hypothesis","action","outcome")
        grant = self._grant(principal, at=now)
        kinds=tuple(phase.kind for phase in phases)
        if kinds not in {ordered, ordered + ("correction",)}:
            raise ValueError("episode requires ordered intent-observation-hypothesis-action-outcome")
        refs=tuple(dict.fromkeys(ref for phase in phases for ref in phase.evidence_refs))
        records=self._scoped_refs(refs,principal)
        outcome_refs=set(phases[4].evidence_refs)
        if not any(record.evidence_ref in outcome_refs and record.kind in {'operation_receipt','reviewed_evidence','external_observation'} and record.successful is not None for record in records):
            raise PermissionError("independently verified outcome evidence required")
        occurred=_utc(occurred_at); recorded=_utc(now); retained=_utc(retention_until)
        if occurred>recorded or retained<=recorded or retained-recorded>__import__('datetime').timedelta(days=365):
            raise ValueError("invalid episode chronology or retention")
        if retained > _utc(grant.expires_at):
            raise PermissionError("episode retention exceeds data-use grant")
        tags=tuple(sorted({_id(tag,'context tag') for tag in context_tags}))
        if not tags or len(tags)>16: raise ValueError("bounded context tags required")
        body={"scope":(principal.principal_id,principal.audience_id),
              "subject":_id(subject_id,'subject'),"tags":tags,"phases":[asdict(x) for x in phases],
              "refs":refs,"occurred":occurred.isoformat(),"correction_of":correction_of}
        digest=_digest(body); episode_id='ga-episode:'+digest[:24]
        with closing(self._connect()) as db, db:
            if correction_of:
                prior=db.execute("SELECT principal_id,audience_id,status FROM ga_experience_episode WHERE episode_id=?",(correction_of,)).fetchone()
                if prior is None or tuple(prior[:2]) != (principal.principal_id,principal.audience_id):
                    raise PermissionError("correction source scope mismatch")
                db.execute("UPDATE ga_experience_episode SET status='corrected' WHERE episode_id=?",(correction_of,))
            db.execute("INSERT OR IGNORE INTO ga_experience_episode VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (episode_id,principal.principal_id,principal.audience_id,body['subject'],json.dumps(tags),
                 json.dumps(body['phases'],sort_keys=True),json.dumps(refs),1,occurred.isoformat(),recorded.isoformat(),
                 retained.isoformat(),'current',correction_of,digest))
        return episode_id

    def retrieve_experiences(self, *, principal: PrincipalContext, tags: tuple[str, ...],
                             now: datetime, limit: int = 8) -> tuple[dict, ...]:
        if type(limit) is not int or not 1<=limit<=32: raise ValueError("limit must be 1..32")
        self._grant(principal, at=now)
        wanted=set(tags); moment=_utc(now)
        with closing(self._connect()) as db, db:
            rows=db.execute("SELECT * FROM ga_experience_episode WHERE principal_id=? AND audience_id=? "
                            "AND status='current' AND retention_until>? ORDER BY occurred_at DESC LIMIT 128",
                            (principal.principal_id,principal.audience_id,moment.isoformat())).fetchall()
            revoked = _revoked_sources(db)
        output=[]
        for row in rows:
            if set(json.loads(row['source_refs_json'])) & revoked: continue
            overlap=len(wanted & set(json.loads(row['context_tags_json'])))
            if overlap: output.append((overlap,row))
        output.sort(key=lambda item:(-item[0],item[1]['occurred_at'],item[1]['episode_id']))
        return tuple({"episode_id":row['episode_id'],"subject_id":row['subject_id'],"tags":tuple(json.loads(row['context_tags_json'])),
                      "phases":tuple(json.loads(row['phases_json'])),"authority":False} for _,row in output[:limit])

    def record_principle(self, *, principal: PrincipalContext, statement: str,
                         epistemic_status: str, confidence: float,
                         episode_ids: tuple[str, ...], evidence_refs: tuple[str, ...], now: datetime) -> str:
        if epistemic_status not in _EPISTEMIC or not 0<=confidence<=1: raise ValueError("invalid epistemic status/confidence")
        if not 1 <= len(episode_ids) <= 32 or len(set(episode_ids)) != len(episode_ids):
            raise ValueError("principle requires 1..32 unique source episodes")
        self._grant(principal, at=now)
        self._scoped_refs(evidence_refs,principal)
        with closing(self._connect()) as db, db:
            episodes=db.execute("SELECT episode_id FROM ga_experience_episode WHERE episode_id IN (%s) AND principal_id=? AND audience_id=? AND status='current'" % ','.join('?'*len(episode_ids)), (*episode_ids,principal.principal_id,principal.audience_id)).fetchall() if episode_ids else []
            if len(episodes)!=len(set(episode_ids)): raise PermissionError("current scoped source episodes required")
            status='verified' if epistemic_status=='verified_fact' and len(episode_ids)>=2 else 'candidate'
            pid='ga-principle:'+_digest((principal.principal_id,principal.audience_id,
                                         statement,episode_ids,evidence_refs))[:24]
            db.execute("INSERT OR IGNORE INTO ga_principle VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                       (pid,principal.principal_id,principal.audience_id,_text(statement,'principle'),epistemic_status,
                        confidence,json.dumps(episode_ids),json.dumps(evidence_refs),status,_utc(now).isoformat(),_utc(now).isoformat()))
        return pid

    def record_planning_influence(self, *, principal: PrincipalContext, goal_id: str,
                                  episode_ids: tuple[str, ...], reason: str,
                                  ablation: str, now: datetime) -> str:
        if ablation not in {'with_experience','without_experience'}: raise ValueError("explicit ablation required")
        if goal_id not in {goal.id for goal in self._goals.list_visible(principal)}: raise PermissionError("visible goal required")
        if ablation=='without_experience' and episode_ids: raise ValueError("without-experience trace cannot cite episodes")
        if ablation=='with_experience':
            found={x['episode_id'] for x in self.retrieve_experiences(principal=principal,tags=tuple({tag for eid in episode_ids for tag in self._episode_tags(eid)}),now=now,limit=32)}
            if set(episode_ids)-found: raise PermissionError("ineligible experience influence")
        trace='ga-influence:'+_digest((
            principal.principal_id, principal.audience_id, goal_id,
            episode_ids, reason, ablation,
        ))[:24]
        with closing(self._connect()) as db, db:
            values=(trace,goal_id,principal.principal_id,principal.audience_id,
                    json.dumps(episode_ids),_text(reason,'reason'),ablation,
                    _utc(now).isoformat())
            prior=db.execute(
                "SELECT goal_id,principal_id,audience_id,episode_ids_json,reason,"
                "ablation FROM ga_planning_influence WHERE trace_id=?", (trace,),
            ).fetchone()
            if prior is not None:
                if tuple(prior) != values[1:7]:
                    raise PermissionError("planning influence identity collision")
                return trace
            db.execute("INSERT INTO ga_planning_influence VALUES(?,?,?,?,?,?,?,?,0)", values)
        return trace

    def planning_advice(
        self, *, principal: PrincipalContext, goal_id: str,
        context_tags: tuple[str, ...], now: datetime,
    ) -> dict[str, object]:
        """Return bounded failure advice; never propose or authorize an action."""
        if goal_id not in {goal.id for goal in self._goals.list_visible(principal)}:
            raise PermissionError("visible goal required for planning advice")
        episodes = self.retrieve_experiences(
            principal=principal, tags=context_tags, now=now, limit=8,
        )
        failures: set[str] = set()
        successes: set[str] = set()
        for episode in episodes:
            phases = {phase["kind"]: phase for phase in episode["phases"]}
            action = phases.get("action")
            outcome = phases.get("outcome")
            if action is None or outcome is None:
                continue
            outcome_records = tuple(
                self._evidence.lookup(ref) for ref in outcome["evidence_refs"]
            )
            known = {record.successful for record in outcome_records if record is not None}
            if known not in ({True}, {False}):
                continue
            for ref in action["evidence_refs"]:
                record = self._evidence.lookup(ref)
                if (
                    record is None or record.principal_id != principal.principal_id
                    or record.audience != principal.audience_id
                    or record.kind not in {"operation_receipt", "reviewed_evidence"}
                    or not isinstance(record.assertion, str)
                    or _ID.fullmatch(record.assertion) is None
                ):
                    continue
                (successes if known == {True} else failures).add(record.assertion)
        failed_only = tuple(sorted(failures - successes))[:16]
        return {
            "episode_ids": tuple(item["episode_id"] for item in episodes),
            "avoid_capabilities": failed_only,
            "authority": False,
        }

    def _episode_tags(self, episode_id: str) -> tuple[str,...]:
        with closing(self._connect()) as db:
            row=db.execute("SELECT context_tags_json FROM ga_experience_episode WHERE episode_id=?",(episode_id,)).fetchone()
        return () if row is None else tuple(json.loads(row[0]))

    def propagate_revocations(self, *, now: datetime, limit: int = 128) -> dict[str,int]:
        moment = _utc(now)
        with closing(self._connect()) as db, db:
            revoked = _revoked_sources(db)
            episodes=db.execute(
                "SELECT episode_id,source_refs_json,retention_until FROM "
                "ga_experience_episode WHERE status='current' "
                "ORDER BY recorded_at,episode_id LIMIT ?", (limit,),
            ).fetchall()
            invalid=[]; expired=[]
            for row in episodes:
                if set(json.loads(row[1])) & revoked:
                    invalid.append(row[0])
                elif datetime.fromisoformat(row[2]) <= moment:
                    expired.append(row[0])
            for eid in invalid:
                db.execute("UPDATE ga_experience_episode SET status='revoked' WHERE episode_id=?",(eid,))
            for eid in expired:
                db.execute("UPDATE ga_experience_episode SET status='expired' WHERE episode_id=?",(eid,))
            invalid_lineage_refs = set(revoked)
            for row in db.execute(
                "SELECT source_refs_json FROM ga_experience_episode "
                "WHERE status IN('corrected','revoked','expired') "
                "ORDER BY recorded_at,episode_id LIMIT ?", (limit,),
            ).fetchall():
                invalid_lineage_refs.update(json.loads(row[0]))
            principles=db.execute("SELECT principle_id,episode_ids_json FROM ga_principle WHERE status IN('candidate','verified') LIMIT ?",(limit,)).fetchall()
            bad=[]
            for row in principles:
                sources=tuple(json.loads(row[1]))
                if not sources:
                    bad.append(row[0])
                    continue
                marks=','.join('?' for _ in sources)
                unusable=db.execute(
                    f"SELECT 1 FROM ga_experience_episode WHERE episode_id IN ({marks}) "
                    "AND status IN('corrected','revoked','expired') LIMIT 1", sources,
                ).fetchone()
                if unusable is not None:
                    bad.append(row[0])
            for pid in bad: db.execute("UPDATE ga_principle SET status='invalidated',updated_at=? WHERE principle_id=?",(moment.isoformat(),pid))
            failures = db.execute(
                "SELECT failure_id FROM ga_failure WHERE status='current' "
                "AND retention_until<=? ORDER BY retention_until,failure_id LIMIT ?",
                (moment.isoformat(), limit),
            ).fetchall()
            expired_failures = {row[0] for row in failures}
            for failure_id in expired_failures:
                db.execute(
                    "UPDATE ga_failure SET status='invalidated' WHERE failure_id=?",
                    (failure_id,),
                )
                db.execute(
                    "UPDATE ga_failure_hypothesis SET status='invalidated' "
                    "WHERE failure_id=? AND status='hypothesis'", (failure_id,),
                )
            studies = db.execute(
                "SELECT study_id,promotion_evidence_refs_json FROM ga_blind_study "
                "WHERE promotion_eligible=1 ORDER BY recorded_at,study_id LIMIT ?",
                (limit,),
            ).fetchall()
            invalid_studies = []
            for study in studies:
                evidence_map = json.loads(study[1])
                if isinstance(evidence_map, dict) and set(evidence_map.values()) & revoked:
                    invalid_studies.append(study[0])
            for study_id in invalid_studies:
                db.execute(
                    "UPDATE ga_blind_study SET promotion_eligible=0 WHERE study_id=?",
                    (study_id,),
                )
        skills_invalidated = 0
        if self._skills is not None:
            skills_invalidated = self._skills.invalidate_revoked_sources(
                invalid_lineage_refs, now=now, limit=limit,
            )
        learning_cleanup = {}
        enforce = getattr(self._learning, "enforce_retention", None)
        if callable(enforce):
            learning_cleanup = enforce(at=now, limit=limit)
        return {
            'episodes_revoked':len(invalid),
            'episodes_expired':len(expired),
            'principles_invalidated':len(bad),
            'failures_expired':len(expired_failures),
            'studies_invalidated':len(invalid_studies),
            'skills_invalidated': skills_invalidated,
            **{f"learning_{key}": value for key, value in learning_cleanup.items()},
        }

    def observe_environment(self, *, principal: PrincipalContext, environment_id: str,
                            platform: str, route: str, version_id: str | None,
                            permit_ref: str, evidence_ref: str, observed_at: datetime,
                            expires_at: datetime) -> str:
        if platform not in {'windows','linux','synthetic'} or route not in {'screen_read_only','api_read_only','command_read_only','digital_twin'}:
            raise ValueError("approved read-only observation route required")
        self._grant(principal, at=observed_at)
        self._admission()
        evidence=self._scoped_refs((evidence_ref,),principal)[0]
        if evidence.kind not in {'external_observation','reviewed_evidence','operation_receipt'}:
            raise PermissionError("typed observation evidence required")
        if not permit_ref.startswith(('screen-permit:','safe:','synthetic:')): raise PermissionError("exact observation permit required")
        expected_sources = {
            'screen_read_only': ('vision:', 'screen:'),
            'api_read_only': ('ops:', 'fleet:', 'synthetic:'),
            'command_read_only': ('ops:', 'fleet:', 'synthetic:'),
            'digital_twin': ('synthetic:', 'verify:'),
        }
        if not evidence.source.startswith(expected_sources[route]):
            raise PermissionError("observation evidence source conflicts with declared route")
        observed=_utc(observed_at); expires=_utc(expires_at)
        if expires<=observed: raise ValueError("observation expiry must follow observation")
        body=(principal.principal_id,principal.audience_id,environment_id,platform,route,
              version_id,permit_ref,evidence_ref,observed.isoformat())
        oid='ga-env-observation:'+_digest(body)[:24]
        with closing(self._connect()) as db, db:
            db.execute("INSERT OR IGNORE INTO ga_environment_observation VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                       (oid,principal.principal_id,principal.audience_id,_id(environment_id,'environment'),platform,route,version_id,permit_ref,evidence_ref,observed.isoformat(),expires.isoformat(),_digest(body)))
        return oid

    def model_environment(self, *, principal: PrincipalContext, environment_id: str,
                          transitions: tuple[dict, ...], evidence_refs: tuple[str, ...],
                          confidence: float, contradictions: tuple[str, ...], now: datetime) -> str:
        if not 0<=confidence<=1 or not transitions or len(transitions)>32: raise ValueError("bounded uncertain model required")
        self._grant(principal, at=now)
        self._scoped_refs(evidence_refs,principal)
        for item in transitions:
            if set(item)!={'from','action','to','prediction'} or not all(isinstance(v,str) and v.strip() for v in item.values()):
                raise ValueError("typed tentative transition required")
        environment=_id(environment_id,'environment')
        mid='ga-env-model:'+_digest((principal.principal_id,principal.audience_id,
                                     environment))[:24]
        with closing(self._connect()) as db, db:
            db.execute("INSERT INTO ga_environment_model VALUES(?,?,?,?,1,'tentative',?,?,?,?,?) ON CONFLICT(model_id) DO UPDATE SET revision=revision+1,status='tentative',transitions_json=excluded.transitions_json,evidence_refs_json=excluded.evidence_refs_json,confidence=excluded.confidence,contradictions_json=excluded.contradictions_json,updated_at=excluded.updated_at",
                       (mid,principal.principal_id,principal.audience_id,environment,json.dumps(transitions,sort_keys=True),json.dumps(evidence_refs),confidence,json.dumps(contradictions),_utc(now).isoformat()))
        return mid

    def detect_drift(self, model_id: str, *, principal: PrincipalContext,
                     observation_id: str, prior_version: str, now: datetime) -> bool:
        with closing(self._connect()) as db, db:
            model=db.execute("SELECT * FROM ga_environment_model WHERE model_id=?",(model_id,)).fetchone()
            obs=db.execute("SELECT * FROM ga_environment_observation WHERE observation_id=?",(observation_id,)).fetchone()
            if model is None or obs is None or (model['principal_id'],model['audience_id'])!=(principal.principal_id,principal.audience_id) or (obs['principal_id'],obs['audience_id'])!=(principal.principal_id,principal.audience_id): raise PermissionError("scoped model and observation required")
            drift=obs['version_id'] is None or obs['version_id']!=prior_version
            if drift: db.execute("UPDATE ga_environment_model SET status='stale',confidence=0,updated_at=? WHERE model_id=?",(_utc(now).isoformat(),model_id))
        return drift

    def plan_discriminating_experiment(
        self, model_id: str, *, principal: PrincipalContext, job_id: str,
        environment_kind: str, rival_hypotheses: tuple[str, ...], now: datetime,
    ) -> str:
        if environment_kind not in {"hephaestus", "synthetic_digital_twin"}:
            raise PermissionError("experiments require approved Hephaestus or synthetic environment")
        if not 2 <= len(rival_hypotheses) <= 8 or len(set(rival_hypotheses)) != len(rival_hypotheses):
            raise ValueError("two to eight distinct rival hypotheses required")
        job = self._work.get(job_id)
        if job.payload.get("principal_id") != principal.principal_id or job.payload.get("audience_id") != principal.audience_id:
            raise PermissionError("experiment RUN scope mismatch")
        if job.status not in {WorkStatus.QUEUED, WorkStatus.BLOCKED, WorkStatus.WAITING_APPROVAL}:
            raise PermissionError("experiment must reference admitted, unexecuted RUN work")
        if job.risk != "read_only" and not job.payload.get("approval_id"):
            raise PermissionError("mutable experiment requires existing approval request")
        with closing(self._connect()) as db, db:
            model = db.execute("SELECT principal_id,audience_id,status FROM ga_environment_model WHERE model_id=?", (model_id,)).fetchone()
            if model is None or tuple(model[:2]) != (principal.principal_id, principal.audience_id) or model[2] == "stale":
                raise PermissionError("current scoped tentative environment model required")
            prior = db.execute(
                "SELECT experiment_id,model_id,environment_kind,rival_hypotheses_json "
                "FROM ga_environment_experiment WHERE job_id=?",
                (job_id,),
            ).fetchone()
            if prior is not None:
                if (
                    prior[1] != model_id or prior[2] != environment_kind
                    or tuple(json.loads(prior[3])) != rival_hypotheses
                ):
                    raise PermissionError("experiment replay changed immutable plan")
                return prior[0]
            experiment_id = "ga-experiment:" + uuid4().hex
            db.execute("INSERT INTO ga_environment_experiment VALUES(?,?,?,?,?,NULL,'proposed',?)",
                       (experiment_id, model_id, job_id, environment_kind,
                        json.dumps(rival_hypotheses), _utc(now).isoformat()))
        return experiment_id

    def record_skill_transfer(
        self, *, principal: PrincipalContext, skill_id: str,
        source_environment: str, target_environment: str, target_platform: str,
        run_id: str, baseline_run_id: str, evidence_ref: str, now: datetime,
    ) -> dict:
        if source_environment == target_environment:
            raise ValueError("transfer target must be substantively different")
        if target_platform not in {"windows", "linux"}:
            raise ValueError("target platform must be Windows or Linux")
        self._grant(principal, at=now)
        transfer_evidence = self._scoped_refs((evidence_ref,), principal)[0]
        if (
            transfer_evidence.kind not in {"operation_receipt", "reviewed_evidence"}
            or transfer_evidence.successful is not True
            or not transfer_evidence.source.startswith(("verify:", "skill-transfer:"))
        ):
            raise PermissionError("independently verified transfer evidence required")
        if self._skills is None:
            raise RuntimeError("learned skill owner is not attached")
        visible = {skill.skill_id: skill for skill in self._skills.visible(principal=principal)}
        skill = visible.get(skill_id)
        if skill is None or skill.status != "verified":
            raise PermissionError("verified scoped learned skill required")
        with closing(self._connect()) as db, db:
            adapter = db.execute("SELECT 1 FROM ga_skill_adapter WHERE skill_id=? AND platform=?", (skill_id, target_platform)).fetchone()
            query = ("SELECT r.status,r.condition,r.split,r.principal_id,r.audience_id,"
                     "c.case_id,c.family_id,g.objective_success FROM ga_evaluation_run r "
                     "JOIN ga_case_grade g ON g.run_id=r.run_id JOIN ga_problem_case c "
                     "ON c.suite_id=r.suite_id AND c.case_id=g.case_id WHERE r.run_id=?")
            learned = db.execute(query, (run_id,)).fetchall()
            baseline = db.execute(query, (baseline_run_id,)).fetchall()
            if adapter is None or not learned or not baseline:
                raise PermissionError("platform adapter and paired completed runs required")
            if any(
                row[0] != 'completed' or row[2] != 'test'
                or tuple(row[3:5]) != (principal.principal_id, principal.audience_id)
                for row in learned + baseline
            ):
                raise PermissionError("paired transfer runs must be completed test runs")
            if learned[0][1] != 'learned' or baseline[0][1] != 'baseline':
                raise PermissionError("learned and baseline conditions required")
            learned_cases = {(row[5], row[6]) for row in learned}
            baseline_cases = {(row[5], row[6]) for row in baseline}
            if learned_cases != baseline_cases:
                raise PermissionError("paired runs must use the same withheld cases")
            learned_rate = sum(row[7] for row in learned) / len(learned)
            baseline_rate = sum(row[7] for row in baseline) / len(baseline)
            status = 'beneficial' if learned_rate > baseline_rate else 'no_benefit'
            transfer_id = 'ga-transfer:' + uuid4().hex
            db.execute("INSERT INTO ga_transfer_application VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                       (transfer_id, skill_id, _id(source_environment,'source environment'),
                        _id(target_environment,'target environment'), target_platform, run_id,
                        baseline_run_id, principal.principal_id, principal.audience_id,
                        status, evidence_ref, _utc(now).isoformat()))
        return {'transfer_id': transfer_id, 'learned_rate': learned_rate,
                'baseline_rate': baseline_rate, 'beneficial': learned_rate > baseline_rate,
                'authority': False}

    def register_benchmark(self, *, benchmark_id: str, name: str, version: str,
                           family: str, license_id: str, source_digest: str,
                           private_holdout: bool, now: datetime) -> None:
        if family not in {'time_horizon','episodic_memory','computer_use','unfamiliar_environment'} or _SHA.fullmatch(source_digest) is None:
            raise ValueError("licensed versioned benchmark metadata required")
        values = (_id(benchmark_id,'benchmark'),_text(name,'name',200),
                  _id(version,'version'),family,_id(license_id,'license'),source_digest,
                  int(private_holdout),0,_utc(now).isoformat())
        with closing(self._connect()) as db, db:
            prior = db.execute(
                "SELECT benchmark_id,name,version,family,license_id,source_digest,"
                "private_holdout,content_stored FROM ga_benchmark_registry "
                "WHERE benchmark_id=? OR (name=? AND version=?)",
                (values[0], values[1], values[2]),
            ).fetchone()
            if prior is not None:
                if tuple(prior) != values[:8]:
                    raise PermissionError("benchmark identity replay changed immutable metadata")
                return
            db.execute("INSERT INTO ga_benchmark_registry VALUES(?,?,?,?,?,?,?,?,?)", values)

    def record_blind_study(self, *, principal: PrincipalContext, evidence_bundle: object,
                           evaluator_key: Ed25519PublicKey,
                           check_evidence: dict[str, str], now: datetime) -> dict:
        assessment=assess_signed_transfer(evidence_bundle,evaluator_key=evaluator_key)
        self._grant(principal, at=now)
        required = {"resource_fit", "privacy_correct", "authority_correct", "rollback_ready", "restart_correct"}
        if not isinstance(check_evidence, dict) or set(check_evidence) != required:
            raise ValueError("exact promotion check evidence mapping required")
        records = self._scoped_refs(tuple(check_evidence.values()), principal)
        checks = {
            name: record.successful is True
            and record.kind in {"reviewed_evidence", "operation_receipt"}
            and record.source.startswith(("verify:", "safe:"))
            for (name, _), record in zip(check_evidence.items(), records)
        }
        with closing(self._connect()) as db:
            benchmark_rows = db.execute(
                "SELECT family,private_holdout FROM ga_benchmark_registry"
            ).fetchall()
        benchmark_families = {row[0] for row in benchmark_rows}
        benchmarks_ready = benchmark_families == {
            'time_horizon','episodic_memory','computer_use','unfamiliar_environment'
        } and any(row[1] for row in benchmark_rows)
        eligible=assessment.evidence_supports_transfer and all(checks.values()) and benchmarks_ready
        body=asdict(assessment)
        model_digest = evidence_bundle["sealed"]["statement"]["model_digest"]
        with closing(self._connect()) as db, db:
            prior = db.execute(
                "SELECT sealed_digest FROM ga_blind_study WHERE study_id=?",
                (assessment.study_id,),
            ).fetchone()
            sealed_digest = _digest(evidence_bundle)
            if prior is not None:
                if prior[0] != sealed_digest:
                    raise PermissionError("blind study identity replay changed signed evidence")
                raise PermissionError("blind study was already recorded")
            db.execute(
                "INSERT INTO ga_blind_study("
                "study_id,principal_id,audience_id,revision,domain_a,domain_b,"
                "sealed_digest,assessment_json,evidence_supports_transfer,resource_fit,"
                "privacy_correct,authority_correct,rollback_ready,restart_correct,"
                "promotion_evidence_refs_json,promotion_eligible,recorded_at,model_digest"
                ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (assessment.study_id,principal.principal_id,principal.audience_id,assessment.revision,
                 assessment.trained_family,assessment.unseen_family,sealed_digest,json.dumps(body,sort_keys=True),
                 int(assessment.evidence_supports_transfer),int(checks['resource_fit']),int(checks['privacy_correct']),
                 int(checks['authority_correct']),int(checks['rollback_ready']),int(checks['restart_correct']),
                 json.dumps(check_evidence,sort_keys=True),int(eligible),_utc(now).isoformat(),
                 model_digest),
            )
        return {'assessment':body,'promotion_eligible':eligible,
                'benchmarks_ready': benchmarks_ready,'deployment_authorized':False}

    def claim_candidate_promotion(
        self, *, study_id: str, candidate_id: str, candidate_digest: str,
        principal_id: str, audience_id: str, now: datetime,
        _transaction_db: sqlite3.Connection,
    ) -> None:
        """Consume a blind-transfer prerequisite inside ML's activation transaction.

        This check never grants deployment authority. CandidateRegistry must still
        validate its canonical deployment grant, independent evaluation, artifact,
        rollback lineage, and active baseline before calling this method.
        """
        if not isinstance(_transaction_db, sqlite3.Connection) or not _transaction_db.in_transaction:
            raise RuntimeError("candidate promotion gate requires the activation transaction")
        database_path = _transaction_db.execute("PRAGMA database_list").fetchone()[2]
        if Path(database_path).resolve() != self.path.resolve():
            raise PermissionError("promotion gate must share canonical state")
        _id(study_id, "study"); _id(candidate_id, "candidate")
        if _SHA.fullmatch(candidate_digest) is None:
            raise ValueError("candidate digest must be SHA-256")
        row = _transaction_db.execute(
            "SELECT principal_id,audience_id,model_digest,promotion_eligible,"
            "promotion_evidence_refs_json FROM ga_blind_study WHERE study_id=?",
            (study_id,),
        ).fetchone()
        if (
            row is None or tuple(row[:2]) != (principal_id, audience_id)
            or row[2] != candidate_digest or not bool(row[3])
        ):
            raise PermissionError("matching eligible blind-transfer study required")
        evidence_map = json.loads(row[4])
        if not isinstance(evidence_map, dict):
            raise PermissionError("promotion evidence mapping is corrupt")
        refs = tuple(evidence_map.values())
        principal = PrincipalContext(
            principal_id, audience_id, AudienceKind.PRIVATE,
        )
        current = self._scoped_refs(refs, principal)
        revoked = _revoked_sources(_transaction_db)
        if set(refs) & revoked or any(record.successful is not True for record in current):
            raise PermissionError("promotion evidence is no longer successful")
        try:
            _transaction_db.execute(
                "INSERT INTO ga_candidate_promotion_gate VALUES(?,?,?,?,?,?)",
                (candidate_id, study_id, candidate_digest, principal_id, audience_id,
                 _utc(now).isoformat()),
            )
        except sqlite3.IntegrityError as exc:
            prior = _transaction_db.execute(
                "SELECT study_id,candidate_digest,principal_id,audience_id FROM "
                "ga_candidate_promotion_gate WHERE candidate_id=?", (candidate_id,),
            ).fetchone()
            if prior is None or tuple(prior) != (
                study_id, candidate_digest, principal_id, audience_id,
            ):
                raise PermissionError("promotion study or candidate was already consumed") from exc

    def validate_candidate_promotion(
        self, *, candidate_id: str, candidate_digest: str,
        principal_id: str, audience_id: str, now: datetime,
    ) -> bool:
        """Recheck a claimed gate at point of use; false means baseline candidate."""
        _utc(now)
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT g.candidate_digest,g.principal_id,g.audience_id,"
                "s.promotion_eligible,s.promotion_evidence_refs_json "
                "FROM ga_candidate_promotion_gate g JOIN ga_blind_study s "
                "ON s.study_id=g.study_id WHERE g.candidate_id=?", (candidate_id,),
            ).fetchone()
            if row is None:
                return False
            if tuple(row[:3]) != (candidate_digest, principal_id, audience_id) or not bool(row[3]):
                raise PermissionError("candidate blind-transfer gate is no longer valid")
            evidence_map = json.loads(row[4])
            if not isinstance(evidence_map, dict):
                raise PermissionError("candidate promotion evidence mapping is corrupt")
            refs = tuple(evidence_map.values())
            revoked = _revoked_sources(db)
        principal = PrincipalContext(principal_id, audience_id, AudienceKind.PRIVATE)
        current = self._scoped_refs(refs, principal)
        if set(refs) & revoked or any(record.successful is not True for record in current):
            raise PermissionError("candidate promotion evidence was revoked")
        return True

    def bind_failure_study(
        self, failure_id: str, study_id: str, *, principal: PrincipalContext,
        comparison_kind: str, now: datetime,
    ) -> None:
        if comparison_kind not in {'failure_reflection_vs_controls'}:
            raise ValueError("unsupported failure-learning comparison")
        with closing(self._connect()) as db, db:
            failure = db.execute(
                "SELECT principal_id,audience_id FROM ga_failure WHERE failure_id=?",
                (failure_id,),
            ).fetchone()
            study = db.execute(
                "SELECT principal_id,audience_id FROM ga_blind_study WHERE study_id=?",
                (study_id,),
            ).fetchone()
            scope = (principal.principal_id, principal.audience_id)
            if failure is None or study is None or tuple(failure) != scope or tuple(study) != scope:
                raise PermissionError("scoped failure and independently assessed study required")
            db.execute(
                "INSERT OR IGNORE INTO ga_failure_study VALUES(?,?,?,?)",
                (failure_id, study_id, comparison_kind, _utc(now).isoformat()),
            )

    def diagnostics(self, *, principal: PrincipalContext) -> dict:
        with closing(self._connect()) as db:
            count=lambda table: db.execute(f"SELECT COUNT(*) FROM {table} WHERE principal_id=? AND audience_id=?",(principal.principal_id,principal.audience_id)).fetchone()[0]
            return {'failures':count('ga_failure'),'episodes':count('ga_experience_episode'),
                    'principles':count('ga_principle'),'environment_models':count('ga_environment_model'),
                    'blind_studies':count('ga_blind_study'),
                    'promotion_gates':count('ga_candidate_promotion_gate'),
                    'authority':False}
