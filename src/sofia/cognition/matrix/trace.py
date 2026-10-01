"""Durable, content-minimal matrix trace storage for debugging and UI status."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime
import json
from pathlib import Path
import sqlite3

from .model import (
    AuthorityDecision,
    AuthorityPlan,
    CognitionExecutionStep,
    CognitionExecutionTrace,
    ContextPlan,
    DomainContribution,
    EvidenceKind,
    EvidenceMatrix,
    EvidenceRecord,
    EvidenceRequirement,
    EvidenceState,
    HistoryPolicy,
    MatrixConfidence,
    MatrixDomain,
    MatrixIntent,
    MatrixRelevance,
    MatrixRoute,
    MatrixTrace,
    ResponseContract,
    ResponseStrategy,
    ResponseValidation,
    ResponseValidationDisposition,
    RoutingPlan,
    TurnEnvelope,
    TurnMatrix,
)


class MatrixTraceStore:
    """Store matrix decisions without duplicating conversation message text."""

    def __init__(self, database_path: Path | str) -> None:
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.path), timeout=10.0)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def _initialize(self) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS cognition_matrix_trace (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    schema_version INTEGER NOT NULL,
                    intent TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    history_policy TEXT NOT NULL,
                    response_strategy TEXT NOT NULL,
                    domains_json TEXT NOT NULL,
                    context_json TEXT,
                    extensions_json TEXT,
                    ambiguous INTEGER NOT NULL,
                    shadow INTEGER NOT NULL,
                    context_active INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cognition_matrix_trace_session
                ON cognition_matrix_trace(session_id, created_at)
                """
            )
            columns = {
                row["name"]
                for row in db.execute(
                    "PRAGMA table_info(cognition_matrix_trace)"
                ).fetchall()
            }
            if "context_json" not in columns:
                db.execute(
                    "ALTER TABLE cognition_matrix_trace "
                    "ADD COLUMN context_json TEXT"
                )
            if "context_active" not in columns:
                db.execute(
                    "ALTER TABLE cognition_matrix_trace "
                    "ADD COLUMN context_active INTEGER NOT NULL DEFAULT 0"
                )
            if "extensions_json" not in columns:
                db.execute(
                    "ALTER TABLE cognition_matrix_trace "
                    "ADD COLUMN extensions_json TEXT"
                )

    @staticmethod
    def _domains_json(turn: TurnMatrix) -> str:
        return json.dumps(
            [
                {
                    "domain": item.domain.value,
                    "relevance": item.relevance.name,
                    "reason": item.reason,
                }
                for item in turn.domains
            ],
            separators=(",", ":"),
            sort_keys=True,
        )

    @staticmethod
    def _context_json(context: ContextPlan | None) -> str | None:
        if context is None:
            return None
        return json.dumps(
            {
                "included_domains": [
                    item.value for item in context.included_domains
                ],
                "excluded_domains": [
                    item.value for item in context.excluded_domains
                ],
                "history_policy": context.history_policy.value,
                "max_history_messages": context.max_history_messages,
            },
            separators=(",", ":"),
            sort_keys=True,
        )

    @staticmethod
    def _extensions_json(trace: MatrixTrace) -> str | None:
        if (
            trace.evidence is None
            and trace.authority is None
            and trace.response_contract is None
            and trace.response_validation is None
            and trace.routing is None
            and trace.cognition_execution is None
        ):
            return None

        evidence = None
        if trace.evidence is not None:
            evidence = {
                "requirements": [
                    {
                        "key": item.key,
                        "kind": item.kind.value,
                        "required": item.required,
                    }
                    for item in trace.evidence.requirements
                ],
                "records": [
                    {
                        "key": item.key,
                        "state": item.state.value,
                        "source_ref": item.source_ref,
                    }
                    for item in trace.evidence.records
                ],
            }

        authority = None
        if trace.authority is not None:
            authority = {
                "decision": trace.authority.decision.value,
                "requested_action": trace.authority.requested_action,
                "reason": trace.authority.reason,
            }

        contract = None
        if trace.response_contract is not None:
            contract = {
                "require_grounded_claims": (
                    trace.response_contract.require_grounded_claims
                ),
                "prohibited_claims": list(
                    trace.response_contract.prohibited_claims
                ),
                "requires_execution_receipt": (
                    trace.response_contract.requires_execution_receipt
                ),
                "authority_decision": (
                    trace.response_contract.authority_decision.value
                ),
            }

        validation = None
        if trace.response_validation is not None:
            validation = {
                "disposition": trace.response_validation.disposition.value,
                "reasons": list(trace.response_validation.reasons),
            }

        routing = None
        if trace.routing is not None:
            routing = {
                "route": trace.routing.route.value,
                "reason": trace.routing.reason,
            }

        cognition_execution = None
        if trace.cognition_execution is not None:
            cognition_execution = {
                "serial": trace.cognition_execution.serial,
                "actual_route": trace.cognition_execution.actual_route,
                "steps": [
                    {
                        "role": step.role,
                        "model": step.model,
                        "host": step.host,
                        "succeeded": step.succeeded,
                    }
                    for step in trace.cognition_execution.steps
                ],
                "fallback_count": trace.cognition_execution.fallback_count,
                "verification_passes": (
                    trace.cognition_execution.verification_passes
                ),
            }

        return json.dumps(
            {
                "evidence": evidence,
                "authority": authority,
                "response_contract": contract,
                "response_validation": validation,
                "routing": routing,
                "cognition_execution": cognition_execution,
            },
            separators=(",", ":"),
            sort_keys=True,
        )

    @staticmethod
    def _trace(row: sqlite3.Row) -> MatrixTrace:
        domains_raw = json.loads(row["domains_json"])
        domains = tuple(
            DomainContribution(
                domain=MatrixDomain(item["domain"]),
                relevance=MatrixRelevance[item["relevance"]],
                reason=item["reason"],
            )
            for item in domains_raw
        )
        context_raw = row["context_json"]
        context = None
        if context_raw:
            payload = json.loads(context_raw)
            context = ContextPlan(
                included_domains=tuple(
                    MatrixDomain(item)
                    for item in payload["included_domains"]
                ),
                excluded_domains=tuple(
                    MatrixDomain(item)
                    for item in payload["excluded_domains"]
                ),
                history_policy=HistoryPolicy(payload["history_policy"]),
                max_history_messages=int(
                    payload["max_history_messages"]
                ),
            )
        evidence = None
        authority = None
        response_contract = None
        response_validation = None
        routing = None
        cognition_execution = None

        extensions_raw = row["extensions_json"]
        if extensions_raw:
            extensions = json.loads(extensions_raw)

            evidence_payload = extensions.get("evidence")
            if evidence_payload is not None:
                evidence = EvidenceMatrix(
                    requirements=tuple(
                        EvidenceRequirement(
                            key=item["key"],
                            kind=EvidenceKind(item["kind"]),
                            required=bool(item["required"]),
                        )
                        for item in evidence_payload["requirements"]
                    ),
                    records=tuple(
                        EvidenceRecord(
                            key=item["key"],
                            state=EvidenceState(item["state"]),
                            source_ref=item.get("source_ref"),
                        )
                        for item in evidence_payload["records"]
                    ),
                )

            authority_payload = extensions.get("authority")
            if authority_payload is not None:
                authority = AuthorityPlan(
                    decision=AuthorityDecision(
                        authority_payload["decision"]
                    ),
                    requested_action=authority_payload.get(
                        "requested_action"
                    ),
                    reason=authority_payload.get("reason", ""),
                )

            contract_payload = extensions.get("response_contract")
            if contract_payload is not None:
                response_contract = ResponseContract(
                    require_grounded_claims=bool(
                        contract_payload["require_grounded_claims"]
                    ),
                    prohibited_claims=tuple(
                        contract_payload["prohibited_claims"]
                    ),
                    requires_execution_receipt=bool(
                        contract_payload["requires_execution_receipt"]
                    ),
                    authority_decision=AuthorityDecision(
                        contract_payload["authority_decision"]
                    ),
                )

            validation_payload = extensions.get("response_validation")
            if validation_payload is not None:
                response_validation = ResponseValidation(
                    disposition=ResponseValidationDisposition(
                        validation_payload["disposition"]
                    ),
                    reasons=tuple(validation_payload["reasons"]),
                )

            routing_payload = extensions.get("routing")
            if routing_payload is not None:
                routing = RoutingPlan(
                    route=MatrixRoute(routing_payload["route"]),
                    reason=routing_payload["reason"],
                )

            execution_payload = extensions.get("cognition_execution")
            if execution_payload is not None:
                cognition_execution = CognitionExecutionTrace(
                    serial=int(execution_payload["serial"]),
                    actual_route=execution_payload["actual_route"],
                    steps=tuple(
                        CognitionExecutionStep(
                            role=item["role"],
                            model=item.get("model"),
                            host=item.get("host"),
                            succeeded=bool(item["succeeded"]),
                        )
                        for item in execution_payload.get("steps", ())
                    ),
                    fallback_count=int(
                        execution_payload.get("fallback_count", 0)
                    ),
                    verification_passes=int(
                        execution_payload.get("verification_passes", 0)
                    ),
                )

        created_at = datetime.fromisoformat(row["created_at"])
        envelope = TurnEnvelope(
            message_id=row["message_id"],
            session_id=row["session_id"],
            content="[not stored in matrix trace]",
            created_at=created_at,
            principal_id=row["principal_id"] or None,
            channel=row["channel"],
        )
        return MatrixTrace(
            envelope=envelope,
            turn=TurnMatrix(
                intent=MatrixIntent(row["intent"]),
                confidence=MatrixConfidence(row["confidence"]),
                history_policy=HistoryPolicy(row["history_policy"]),
                response_strategy=ResponseStrategy(
                    row["response_strategy"]
                ),
                domains=domains,
                ambiguous=bool(row["ambiguous"]),
                schema_version=int(row["schema_version"]),
            ),
            created_at=created_at,
            context=context,
            evidence=evidence,
            authority=authority,
            response_contract=response_contract,
            response_validation=response_validation,
            routing=routing,
            cognition_execution=cognition_execution,
            shadow=bool(row["shadow"]),
            context_active=bool(row["context_active"]),
        )

    def record(self, trace: MatrixTrace) -> None:
        if not isinstance(trace, MatrixTrace):
            raise TypeError("trace must be MatrixTrace")
        with closing(self._connect()) as db, db:
            db.execute(
                """
                INSERT INTO cognition_matrix_trace (
                    message_id,session_id,principal_id,channel,
                    schema_version,intent,confidence,history_policy,
                    response_strategy,domains_json,context_json,
                    extensions_json,ambiguous,shadow,context_active,created_at
                )
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(message_id) DO UPDATE SET
                    session_id=excluded.session_id,
                    principal_id=excluded.principal_id,
                    channel=excluded.channel,
                    schema_version=excluded.schema_version,
                    intent=excluded.intent,
                    confidence=excluded.confidence,
                    history_policy=excluded.history_policy,
                    response_strategy=excluded.response_strategy,
                    domains_json=excluded.domains_json,
                    context_json=excluded.context_json,
                    extensions_json=excluded.extensions_json,
                    ambiguous=excluded.ambiguous,
                    shadow=excluded.shadow,
                    context_active=excluded.context_active,
                    created_at=excluded.created_at
                """,
                (
                    trace.envelope.message_id,
                    trace.envelope.session_id,
                    trace.envelope.principal_id or "",
                    trace.envelope.channel,
                    trace.turn.schema_version,
                    trace.turn.intent.value,
                    trace.turn.confidence.value,
                    trace.turn.history_policy.value,
                    trace.turn.response_strategy.value,
                    self._domains_json(trace.turn),
                    self._context_json(trace.context),
                    self._extensions_json(trace),
                    int(trace.turn.ambiguous),
                    int(trace.shadow),
                    int(trace.context_active),
                    trace.created_at.isoformat(),
                ),
            )

    def get(self, message_id: str) -> MatrixTrace | None:
        if not isinstance(message_id, str) or not message_id.strip():
            raise ValueError("message_id must be nonempty")
        with closing(self._connect()) as db:
            row = db.execute(
                """
                SELECT * FROM cognition_matrix_trace
                WHERE message_id=?
                """,
                (message_id,),
            ).fetchone()
        return None if row is None else self._trace(row)

    def latest(self, *, session_id: str | None = None) -> MatrixTrace | None:
        with closing(self._connect()) as db:
            if session_id is None:
                row = db.execute(
                    """
                    SELECT * FROM cognition_matrix_trace
                    ORDER BY created_at DESC LIMIT 1
                    """
                ).fetchone()
            else:
                if not isinstance(session_id, str) or not session_id.strip():
                    raise ValueError("session_id must be nonempty")
                row = db.execute(
                    """
                    SELECT * FROM cognition_matrix_trace
                    WHERE session_id=?
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (session_id,),
                ).fetchone()
        return None if row is None else self._trace(row)

    def latest_with_execution(
        self,
        *,
        session_id: str | None = None,
        limit: int = 100,
    ) -> MatrixTrace | None:
        """Return the newest trace that records an actual cognitive execution."""
        if type(limit) is not int or limit < 1:
            raise ValueError("limit must be a positive int")
        with closing(self._connect()) as db:
            if session_id is None:
                rows = db.execute(
                    """
                    SELECT * FROM cognition_matrix_trace
                    WHERE extensions_json IS NOT NULL
                    ORDER BY created_at DESC LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            else:
                if not isinstance(session_id, str) or not session_id.strip():
                    raise ValueError("session_id must be nonempty")
                rows = db.execute(
                    """
                    SELECT * FROM cognition_matrix_trace
                    WHERE session_id=? AND extensions_json IS NOT NULL
                    ORDER BY created_at DESC LIMIT ?
                    """,
                    (session_id, limit),
                ).fetchall()
        for row in rows:
            trace = self._trace(row)
            if trace.cognition_execution is not None:
                return trace
        return None

    def count(self) -> int:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT COUNT(*) AS count FROM cognition_matrix_trace"
            ).fetchone()
        return int(row["count"])
