"""Service-owned, authority-fenced Platform management mutation dispatch.

Only an OS-authenticated Platform session may supply the peer identity,
current status, registry, approval verifier and receipt store. Untrusted JSON
is never a handler, identity, owner grant or approval.

Every admitted mutation requires an exact, one-use SAFE owner execution
approval. The request fingerprint binds the semantic request and the kernel
verified peer. Approval is consumed before handler execution and its consumed
owner proof is re-read after execution. A handler exception, a revoked owner
binding or a generation transition after execution produces OUTCOME_UNKNOWN,
never a false success.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import re
from threading import RLock
from uuid import uuid4

from sofia.platform.run.management_mutation_store import (
    ManagementMutationConflict, ManagementMutationReceiptStore,
)
from sofia.platform.safe.execution_approval import ExecutionApprovalVerifier
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.sdk.platform_management_mutation import (
    UntrustedManagementMutation, make_mutation_response,
    mutation_approval_parameters, mutation_fingerprint,
)

MANAGEMENT_MUTATION_CAPABILITY = "platform.management.mutate"
OPERATOR_STOP_ACTIVATE_OPERATION = "platform.operator.stop.activate"
OPERATOR_STOP_ACTIVATE_SCOPE = "operator"
CORE_AUTOSTART_ENABLE_OPERATION = "core.autostart.enable"
CORE_AUTOSTART_DISABLE_OPERATION = "core.autostart.disable"
CORE_AUTOSTART_SCOPE = "operator"

_CORE_AUTOSTART_FIELDS = frozenset({"core_id", "expected_revision", "enabled"})
_CORE_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)


class MutationRequestRejected(ValueError):
    """A syntactically valid operation payload is not acceptable."""


class MutationFailed(RuntimeError):
    """The handler failed *before* any effect; the mutation may be retried."""


_HANDLER_DENIAL_CODES = frozenset({
    "UNSUPPORTED_OPERATION",
    "EVIDENCE_UNAVAILABLE",
    "NOT_PERMITTED",
    "TARGET_MISMATCH",
    "STALE_REVISION",
    "INVALID_PAYLOAD",
})


class MutationDenied(RuntimeError):
    """The handler refused before any effect with a reviewed denial code.

    A handler may raise this only when it has established that no canonical
    state or external effect was changed. It never turns a failure into a
    success; the dispatcher records a durable DENIED receipt.
    """

    def __init__(self, code: str, detail: str) -> None:
        if code not in _HANDLER_DENIAL_CODES:
            raise ValueError("unreviewed management mutation denial code")
        if (
            not isinstance(detail, str)
            or not detail
            or len(detail) > 512
        ):
            raise ValueError("bounded management mutation denial detail required")
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True, slots=True)
class MutationInvocation:
    request: UntrustedManagementMutation
    authenticated_peer: str
    now: datetime

    @property
    def payload(self) -> Mapping[str, object]:
        return self.request.payload


@dataclass(frozen=True, slots=True)
class MutationOperation:
    name: str
    scopes: frozenset[str]
    handler: Callable[[MutationInvocation], None]
    validate_payload: Callable[[Mapping[str, object]], None] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("mutation operation name required")
        if (
            not isinstance(self.scopes, frozenset)
            or not self.scopes
            or any(not isinstance(scope, str) or not scope for scope in self.scopes)
        ):
            raise ValueError("mutation operation requires explicit scopes")
        if not callable(self.handler):
            raise TypeError("mutation handler must be callable")
        if self.validate_payload is not None and not callable(self.validate_payload):
            raise TypeError("mutation payload validator must be callable")


class MutationRegistry:
    """Explicit service-owned operation registry; clients cannot extend it."""

    def __init__(self, operations: tuple[MutationOperation, ...] = ()) -> None:
        if not isinstance(operations, tuple):
            raise TypeError("mutation operations must be a tuple")
        table: dict[str, MutationOperation] = {}
        for operation in operations:
            if not isinstance(operation, MutationOperation):
                raise TypeError("typed mutation operation required")
            if operation.name in table:
                raise ValueError("duplicate mutation operation")
            table[operation.name] = operation
        self._operations = table

    def resolve(self, name: str) -> MutationOperation | None:
        if not isinstance(name, str):
            return None
        return self._operations.get(name)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._operations))


def operator_stop_mutation_registry(
    stop: OperatorStopStore,
) -> MutationRegistry:
    """The only currently wired canonical backend: explicit operator STOP.

    Activating STOP is a reviewed canonical operator-stop effect. Lifting STOP
    is deliberately NOT exposed here because that canonical owner requires a
    separate FIDO2 approval bound to the exact stop revision.
    """
    if not isinstance(stop, OperatorStopStore):
        raise TypeError("canonical OperatorStopStore required")

    def validate(payload: Mapping[str, object]) -> None:
        if set(payload) != {"reason"}:
            raise MutationRequestRejected("operator STOP payload requires reason")
        reason = payload["reason"]
        if (
            not isinstance(reason, str)
            or not reason.strip()
            or len(reason) > 200
            or any(ord(char) < 0x20 or ord(char) == 0x7F for char in reason)
        ):
            raise MutationRequestRejected("operator STOP reason is invalid")

    def activate(invocation: MutationInvocation) -> None:
        stop.set(
            active=True, updated_by="Sparks",
            reason=invocation.payload["reason"].strip(),
            at=invocation.now,
        )

    return MutationRegistry((
        MutationOperation(
            name=OPERATOR_STOP_ACTIVATE_OPERATION,
            scopes=frozenset({OPERATOR_STOP_ACTIVATE_SCOPE}),
            handler=activate,
            validate_payload=validate,
        ),
    ))


def combined_mutation_registry(
    *registries: MutationRegistry,
) -> MutationRegistry:
    """Compose service-owned registries without adding or inheriting authority."""
    if not registries:
        raise TypeError("at least one service-owned mutation registry required")
    operations: list[MutationOperation] = []
    names: set[str] = set()
    for registry in registries:
        if not isinstance(registry, MutationRegistry):
            raise TypeError("service-owned mutation registry required")
        for name in registry.names:
            if name in names:
                raise ValueError("duplicate mutation operation")
            operation = registry.resolve(name)
            if operation is None:
                raise ValueError("mutation registry is inconsistent")
            names.add(name)
            operations.append(operation)
    return MutationRegistry(tuple(operations))


def core_autostart_mutation_registry(
    reconciler,
) -> MutationRegistry:
    """Bind owner-approved Core autostart enable/disable to the dispatcher.

    The handler uses the injected reconciler's service-owned installed-Core
    inventory and the canonical ``CoreAutostartPolicyStore``. It adds no
    approval store, peer identity or authority of its own: the dispatcher has
    already consumed the exact one-use SAFE approval and fenced STOP,
    generation, mutation revision and replay/idempotency.
    """
    from sofia.platform.run.core_autostart import (
        CoreAutostartConflict, CoreAutostartPolicyStore, CoreStartupReconciler,
        management_autostart_writer,
    )

    if not isinstance(reconciler, CoreStartupReconciler):
        raise TypeError("canonical CoreStartupReconciler required")
    store = reconciler.store
    if not isinstance(store, CoreAutostartPolicyStore):
        raise TypeError("canonical CoreAutostartPolicyStore required")
    write = management_autostart_writer(store)

    def _validate(expected_enabled: bool):
        def validate(payload: Mapping[str, object]) -> None:
            if set(payload) != _CORE_AUTOSTART_FIELDS:
                raise MutationRequestRejected(
                    "Core autostart payload fields are not exact"
                )
            core_id = payload["core_id"]
            if (
                not isinstance(core_id, str)
                or _CORE_UUID.fullmatch(core_id) is None
            ):
                raise MutationRequestRejected(
                    "core_id must be a canonical UUID"
                )
            expected_revision = payload["expected_revision"]
            if type(expected_revision) is not int or expected_revision < 1:
                raise MutationRequestRejected(
                    "expected_revision must be a positive integer"
                )
            enabled = payload["enabled"]
            if type(enabled) is not bool:
                raise MutationRequestRejected("enabled must be bool")
            if enabled is not expected_enabled:
                raise MutationRequestRejected(
                    "operation and enabled target disagree"
                )
        return validate

    def _handle(expected_enabled: bool):
        def handle(invocation: MutationInvocation) -> None:
            payload = invocation.payload
            core_id = payload["core_id"]
            expected_revision = payload["expected_revision"]
            enabled = payload["enabled"]
            if enabled is not expected_enabled:
                raise MutationDenied(
                    "INVALID_PAYLOAD", "operation and enabled target disagree"
                )
            try:
                installed = frozenset(reconciler.installed_ids())
            except Exception as error:
                raise MutationDenied(
                    "EVIDENCE_UNAVAILABLE",
                    "installed Core inventory is unavailable",
                ) from error
            if core_id not in installed:
                raise MutationDenied(
                    "TARGET_MISMATCH", "target Core is not installed"
                )
            try:
                current = store.policy(core_id)
            except Exception as error:
                raise MutationDenied(
                    "EVIDENCE_UNAVAILABLE",
                    "Core autostart policy is unavailable",
                ) from error
            if current is None:
                if expected_revision != 1:
                    raise MutationDenied(
                        "STALE_REVISION",
                        "new Core autostart policy must start at revision one",
                    )
            elif expected_revision != current.approved_revision + 1:
                raise MutationDenied(
                    "STALE_REVISION",
                    "Core autostart policy revision is stale",
                )
            fingerprint = mutation_fingerprint(
                invocation.request, invocation.authenticated_peer,
            )
            try:
                write(
                    core_id=core_id,
                    enabled=enabled,
                    expected_revision=expected_revision,
                    authorization_fingerprint=fingerprint,
                    now=invocation.now,
                )
            except PermissionError as error:
                raise MutationDenied(
                    "NOT_PERMITTED",
                    "Core autostart management authority rejected",
                ) from error
            except CoreAutostartConflict as error:
                raise MutationDenied(
                    "STALE_REVISION",
                    "Core autostart policy revision is stale",
                ) from error
        return handle

    return MutationRegistry((
        MutationOperation(
            name=CORE_AUTOSTART_ENABLE_OPERATION,
            scopes=frozenset({CORE_AUTOSTART_SCOPE}),
            handler=_handle(True),
            validate_payload=_validate(True),
        ),
        MutationOperation(
            name=CORE_AUTOSTART_DISABLE_OPERATION,
            scopes=frozenset({CORE_AUTOSTART_SCOPE}),
            handler=_handle(False),
            validate_payload=_validate(False),
        ),
    ))


def _approval_error_code(error: PermissionError) -> str:
    message = str(error).lower()
    if "does not exist" in message or "approval_id" in message:
        return "APPROVAL_MISSING"
    if "expired" in message:
        return "APPROVAL_EXPIRED"
    if "already consumed" in message or "could not be consumed" in message:
        return "APPROVAL_CONSUMED"
    if "not active yet" in message:
        return "APPROVAL_NOT_ACTIVE"
    if "lacks verified owner authentication" in message:
        return "APPROVAL_UNVERIFIED"
    if "revoc" in message:
        return "APPROVAL_REVOKED"
    if (
        "parameters do not match" in message
        or "another capability" in message
        or "not granted by the owner" in message
    ):
        return "APPROVAL_MISMATCH"
    return "NOT_PERMITTED"


class ManagementMutationDispatcher:
    """One serialized mutation path for the existing local management transport."""

    def __init__(
        self,
        *,
        current_status: Callable[[], Mapping[str, object]],
        registry: MutationRegistry,
        approvals: ExecutionApprovalVerifier,
        receipts: ManagementMutationReceiptStore,
        authorize_peer: Callable[[str, str, str], bool] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not callable(current_status):
            raise TypeError("service-owned current status callback required")
        if not isinstance(registry, MutationRegistry):
            raise TypeError("service-owned mutation registry required")
        if not isinstance(approvals, ExecutionApprovalVerifier):
            raise TypeError("canonical SAFE execution approval verifier required")
        if not isinstance(receipts, ManagementMutationReceiptStore):
            raise TypeError("canonical mutation receipt store required")
        if authorize_peer is not None and not callable(authorize_peer):
            raise TypeError("service-owned peer authorization callback required")
        self._status = current_status
        self._registry = registry
        self._approvals = approvals
        self._receipts = receipts
        self._authorize_peer = authorize_peer
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = RLock()

    @staticmethod
    def _current(status: Mapping[str, object]) -> tuple[str, int]:
        platform_id = status.get("platform_id")
        generation = status.get("generation")
        if not isinstance(platform_id, str) or not platform_id:
            raise PermissionError("canonical Platform identity unavailable")
        if type(generation) is not int or generation < 1:
            raise PermissionError("canonical Platform generation unavailable")
        if type(status.get("operator_stop")) is not bool:
            raise PermissionError("canonical operator STOP state unavailable")
        return platform_id, generation

    @staticmethod
    def _new_receipt_id() -> str:
        return "mutreceipt:" + uuid4().hex

    def dispatch(
        self, raw: bytes, *, authenticated_peer: str, now: datetime,
    ) -> dict[str, object]:
        if (
            not isinstance(authenticated_peer, str)
            or not authenticated_peer
            or len(authenticated_peer) > 160
        ):
            raise PermissionError("kernel verified OS peer required")
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise PermissionError("trusted current service time required")
        request = UntrustedManagementMutation.parse(raw, now=now)
        with self._lock:
            fingerprint = mutation_fingerprint(request, authenticated_peer)
            prior = self._receipts.lookup(request.idempotency_key)
            status = self._status()
            platform_id, generation = self._current(status)
            revision = self._receipts.current_revision()
            if prior is not None:
                if prior.request_fingerprint != fingerprint:
                    return make_mutation_response(
                        request, outcome="DENIED",
                        receipt_id=self._new_receipt_id(),
                        current_generation=generation,
                        current_revision=revision,
                        observed_at=self._clock(),
                        error_code="IDEMPOTENCY_MISMATCH",
                        detail="idempotency key already used for a different request",
                    )
                return make_mutation_response(
                    request, outcome=prior.outcome,
                    receipt_id=prior.receipt_id,
                    current_generation=prior.current_generation,
                    current_revision=prior.current_revision,
                    observed_at=self._clock(),
                    error_code=prior.error_code,
                    detail=prior.detail,
                )

            def deny(code: str, detail: str) -> dict[str, object]:
                receipt = self._receipts.record(
                    idempotency_key=request.idempotency_key,
                    request_fingerprint=fingerprint,
                    receipt_id=self._new_receipt_id(),
                    request_id=request.request_id,
                    correlation_id=request.correlation_id,
                    target_platform_id=request.target_platform_id,
                    operation=request.operation,
                    operation_scope=request.operation_scope,
                    outcome="DENIED",
                    current_generation=generation,
                    error_code=code,
                    detail=detail,
                    advance_revision=False,
                    now=now,
                )
                return make_mutation_response(
                    request, outcome=receipt.outcome,
                    receipt_id=receipt.receipt_id,
                    current_generation=receipt.current_generation,
                    current_revision=receipt.current_revision,
                    observed_at=self._clock(),
                    error_code=receipt.error_code,
                    detail=receipt.detail,
                )

            if platform_id != request.target_platform_id:
                return deny(
                    "TARGET_MISMATCH", "target Platform identity differs"
                )
            if status["operator_stop"] is True:
                return deny("STOPPED", "operator STOP prevents mutation")
            if generation != request.expected_generation:
                return deny("STALE_GENERATION", "Platform generation is stale")
            if revision != request.expected_revision:
                return deny("STALE_REVISION", "Platform mutation revision is stale")
            operation = self._registry.resolve(request.operation)
            if operation is None:
                return deny("UNKNOWN_OPERATION", "management operation is unknown")
            if request.operation_scope not in operation.scopes:
                return deny(
                    "SCOPE_NOT_PERMITTED",
                    "management operation scope is not permitted",
                )
            if operation.validate_payload is not None:
                try:
                    operation.validate_payload(request.payload)
                except MutationRequestRejected:
                    return deny(
                        "INVALID_PAYLOAD", "management operation payload is invalid"
                    )
                except (TypeError, ValueError):
                    return deny(
                        "INVALID_PAYLOAD", "management operation payload is invalid"
                    )
            if self._authorize_peer is not None:
                try:
                    permitted = self._authorize_peer(
                        authenticated_peer, request.operation,
                        request.operation_scope,
                    )
                except (PermissionError, RuntimeError):
                    permitted = False
                if permitted is not True:
                    return deny(
                        "NOT_PERMITTED", "peer is not enrolled for this operation"
                    )

            parameters = mutation_approval_parameters(request, authenticated_peer)
            try:
                self._approvals.consume(
                    approval_id=request.approval_id,
                    capability=MANAGEMENT_MUTATION_CAPABILITY,
                    parameters=parameters,
                    now=now,
                )
            except PermissionError as error:
                code = _approval_error_code(error)
                return deny(code, "owner approval rejected")
            except (TypeError, ValueError):
                return deny("APPROVAL_MISMATCH", "owner approval is invalid")

            # Approval consumption is a write. Re-fence immediately before the
            # effect so a generation transition cannot authorize a stale effect.
            # Failure to re-read canonical state is itself a fence: never
            # execute an effect whose current STOP/generation is unobservable.
            try:
                current_after_consume = self._status()
                after_platform, after_generation = self._current(
                    current_after_consume
                )
                state_changed = (
                    after_platform != platform_id
                    or after_generation != generation
                    or current_after_consume.get("operator_stop") is True
                )
            except (PermissionError, RuntimeError):
                after_platform, after_generation = platform_id, generation
                state_changed = True
            if state_changed:
                receipt = self._receipts.record(
                    idempotency_key=request.idempotency_key,
                    request_fingerprint=fingerprint,
                    receipt_id=self._new_receipt_id(),
                    request_id=request.request_id,
                    correlation_id=request.correlation_id,
                    target_platform_id=request.target_platform_id,
                    operation=request.operation,
                    operation_scope=request.operation_scope,
                    outcome="DENIED",
                    current_generation=after_generation,
                    error_code="STATE_CHANGED",
                    detail="Platform state changed before mutation execution",
                    advance_revision=False,
                    now=now,
                )
                return make_mutation_response(
                    request, outcome=receipt.outcome,
                    receipt_id=receipt.receipt_id,
                    current_generation=receipt.current_generation,
                    current_revision=receipt.current_revision,
                    observed_at=self._clock(),
                    error_code=receipt.error_code,
                    detail=receipt.detail,
                )

            outcome = "SUCCEEDED"
            error_code: str | None = None
            detail: str | None = None
            invocation = MutationInvocation(
                request=request, authenticated_peer=authenticated_peer, now=now,
            )
            try:
                operation.handler(invocation)
            except MutationDenied as error:
                outcome = "DENIED"
                error_code = error.code
                detail = error.detail
            except MutationFailed:
                outcome = "FAILED"
                error_code = "HANDLER_FAILED"
                detail = "operation failed before any effect"
            except Exception:
                outcome = "OUTCOME_UNKNOWN"
                error_code = "HANDLER_FAILED_UNKNOWN"
                detail = "handler failed; effect state is unknown"

            post_generation = generation
            try:
                post_status = self._status()
                post_platform, post_generation = self._current(post_status)
                post_stop = post_status.get("operator_stop")
            except (PermissionError, RuntimeError):
                post_platform, post_stop = platform_id, None
            try:
                proof_current = self._approvals.consumed_owner_proof_remains_current(
                    approval_id=request.approval_id,
                    capability=MANAGEMENT_MUTATION_CAPABILITY,
                    parameters=parameters,
                )
            except (PermissionError, RuntimeError, ValueError):
                proof_current = False
            if outcome != "OUTCOME_UNKNOWN":
                if post_platform != platform_id or post_generation != generation:
                    outcome = "OUTCOME_UNKNOWN"
                    error_code = "STATE_CHANGED"
                    detail = "Platform generation changed during mutation execution"
                elif post_stop is None:
                    outcome = "OUTCOME_UNKNOWN"
                    error_code = "STATE_CHANGED"
                    detail = "operator STOP state could not be revalidated"
                elif not proof_current:
                    outcome = "OUTCOME_UNKNOWN"
                    error_code = "AUTHORITY_REVOKED"
                    detail = "owner approval was revoked during mutation execution"
            elif not proof_current:
                error_code = "AUTHORITY_REVOKED"
                detail = "owner approval was revoked during mutation execution"

            advance_revision = outcome in {"SUCCEEDED", "OUTCOME_UNKNOWN"}
            try:
                receipt = self._receipts.record(
                    idempotency_key=request.idempotency_key,
                    request_fingerprint=fingerprint,
                    receipt_id=self._new_receipt_id(),
                    request_id=request.request_id,
                    correlation_id=request.correlation_id,
                    target_platform_id=request.target_platform_id,
                    operation=request.operation,
                    operation_scope=request.operation_scope,
                    outcome=outcome,
                    current_generation=post_generation,
                    error_code=error_code,
                    detail=detail,
                    advance_revision=advance_revision,
                    now=now,
                )
            except ManagementMutationConflict:
                # A concurrent identical request won the durable receipt.
                existing = self._receipts.lookup(request.idempotency_key)
                if existing is None or existing.request_fingerprint != fingerprint:
                    raise PermissionError(
                        "management mutation idempotency conflict"
                    ) from None
                receipt = existing
            return make_mutation_response(
                request, outcome=receipt.outcome,
                receipt_id=receipt.receipt_id,
                current_generation=receipt.current_generation,
                current_revision=receipt.current_revision,
                observed_at=self._clock(),
                error_code=receipt.error_code,
                detail=receipt.detail,
            )

