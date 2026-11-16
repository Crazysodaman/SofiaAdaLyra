"""Canonical backends bound to the existing management mutation dispatcher.

These registries add no authority of their own. Every handler delegates to an
already-composed canonical owner (``ModuleLifecycleCommandService`` or the OPS
Fleet enrollment/removal authority) and relies on the dispatcher for one-use
owner approval, STOP, generation/revision, idempotency and receipt fencing.

The canonical module and Fleet owners consume their own exact per-operation
SAFE approval inside the same request. The payload therefore carries an
``approval_ref`` distinct from the management-mutation ``approval_id``; neither
approval implies the other.

Module operations that require a freshly verified package, an authoritative
compatibility report or live adapter registrations cannot be reconstructed
from untrusted wire bytes. Those operations fail closed with a typed DENIED
instead of fabricating package evidence.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import re
from typing import Protocol
from uuid import UUID

from sofia.platform.run.management_mutation import (
    MutationDenied, MutationInvocation, MutationOperation, MutationRegistry,
    MutationRequestRejected,
)

MODULE_LIFECYCLE_OPERATION = "platform.module.lifecycle"
MODULE_LIFECYCLE_SCOPE = "module"
FLEET_ENROLL_OPERATION = "fleet.enroll"
FLEET_DECOMMISSION_OPERATION = "fleet.decommission"
FLEET_SCOPE = "fleet"

# Operations the canonical module owner already implements.
_MODULE_OPERATIONS = frozenset({
    "approve", "stage", "activate", "resume", "pause", "disable",
    "remove", "rollback", "update", "install", "quarantine",
})
# Operations that need no package, compatibility report or live adapter batch.
_MODULE_BOUND_OPERATIONS = frozenset({"approve", "pause", "disable", "remove"})

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_HOSTNAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.:-]{0,252}$")

_MODULE_FIELDS = frozenset({
    "operation", "module_id", "expected_module_revision",
    "package_digest", "approval_ref",
})
_FLEET_ENROLL_FIELDS = frozenset({
    "host_id", "node_id", "public_key_sha256", "endpoint_hostname",
    "endpoint_port", "approval_ref",
})
_FLEET_DECOMMISSION_FIELDS = frozenset({
    "host_id", "proposal_revision", "approval_ref",
})


class ModuleLifecycleOwner(Protocol):
    def describe(self, module_id: str) -> object | None:
        ...

    def approve(self, module_id: str, *, expected_revision: int,
                approval_id: str, now: datetime) -> object:
        ...

    def pause(self, module_id: str, *, expected_revision: int,
              approval_id: str, now: datetime) -> object:
        ...

    def disable(self, module_id: str, *, expected_revision: int,
                approval_id: str, now: datetime) -> object:
        ...

    def remove(self, module_id: str, *, expected_revision: int,
               approval_id: str, now: datetime) -> object:
        ...


class FleetEnrollmentOwner(Protocol):
    def enroll_candidate(self, payload: dict[str, object]) -> Mapping[str, object]:
        ...

    registry: object


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise MutationRequestRejected(f"{label} must be a bounded identifier")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise MutationRequestRejected(f"{label} must be a lowercase SHA-256")
    return value


def _positive_int(value: object, label: str, *, maximum: int) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise MutationRequestRejected(f"{label} is outside its bounded range")
    return value


def _canonical_uuid(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise MutationRequestRejected(f"{label} must be a canonical UUID")
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise MutationRequestRejected(
            f"{label} must be a canonical UUID"
        ) from error
    if parsed.int == 0 or str(parsed) != value:
        raise MutationRequestRejected(f"{label} must be a canonical UUID")
    return value


def _validate_module_payload(payload: Mapping[str, object]) -> None:
    if set(payload) != _MODULE_FIELDS:
        raise MutationRequestRejected(
            "module lifecycle payload fields are not exact"
        )
    operation = payload["operation"]
    if not isinstance(operation, str) or operation not in _MODULE_OPERATIONS:
        raise MutationRequestRejected("module lifecycle operation is unsupported")
    _identifier(payload["module_id"], "module_id")
    _positive_int(
        payload["expected_module_revision"], "expected_module_revision",
        maximum=2**53 - 1,
    )
    _digest(payload["package_digest"], "package_digest")
    _identifier(payload["approval_ref"], "approval_ref")


def module_lifecycle_mutation_registry(
    service: ModuleLifecycleOwner,
) -> MutationRegistry:
    """Bind ``platform.module.lifecycle`` to the canonical module owner."""
    from sofia.platform.application.module_lifecycle import (
        ModuleLifecycleCommandService,
    )

    if not isinstance(service, ModuleLifecycleCommandService):
        raise TypeError("canonical ModuleLifecycleCommandService required")
    for name in ("describe", "approve", "pause", "disable", "remove"):
        if not callable(getattr(service, name, None)):
            raise TypeError("canonical ModuleLifecycleCommandService required")

    def handle(invocation: MutationInvocation) -> None:
        payload = invocation.payload
        operation = payload["operation"]
        if operation not in _MODULE_BOUND_OPERATIONS:
            raise MutationDenied(
                "UNSUPPORTED_OPERATION",
                "module operation requires verified package or adapter evidence",
            )
        module_id = payload["module_id"]
        expected_revision = payload["expected_module_revision"]
        package_digest = payload["package_digest"]
        approval_ref = payload["approval_ref"]
        current = service.describe(module_id)
        if current is None:
            raise MutationDenied(
                "EVIDENCE_UNAVAILABLE",
                "canonical module lifecycle record is unavailable",
            )
        if (
            getattr(current, "revision", None) != expected_revision
        ):
            raise MutationDenied(
                "STALE_REVISION", "module lifecycle revision is stale"
            )
        if getattr(current, "package_digest", None) != package_digest:
            raise MutationDenied(
                "TARGET_MISMATCH", "module package digest differs"
            )
        try:
            if operation == "approve":
                service.approve(
                    module_id, expected_revision=expected_revision,
                    approval_id=approval_ref, now=invocation.now,
                )
            elif operation == "pause":
                service.pause(
                    module_id, expected_revision=expected_revision,
                    approval_id=approval_ref, now=invocation.now,
                )
            elif operation == "disable":
                service.disable(
                    module_id, expected_revision=expected_revision,
                    approval_id=approval_ref, now=invocation.now,
                )
            else:
                service.remove(
                    module_id, expected_revision=expected_revision,
                    approval_id=approval_ref, now=invocation.now,
                )
        except PermissionError as error:
            # The canonical owner raises PermissionError only from its exact
            # authority boundary, before it changes module state.
            raise MutationDenied(
                "NOT_PERMITTED", "canonical module authority rejected"
            ) from error

    return MutationRegistry((
        MutationOperation(
            name=MODULE_LIFECYCLE_OPERATION,
            scopes=frozenset({MODULE_LIFECYCLE_SCOPE}),
            handler=handle,
            validate_payload=_validate_module_payload,
        ),
    ))


def _validate_fleet_enroll_payload(payload: Mapping[str, object]) -> None:
    if set(payload) != _FLEET_ENROLL_FIELDS:
        raise MutationRequestRejected("Fleet enrollment payload fields are not exact")
    _identifier(payload["host_id"], "host_id")
    _canonical_uuid(payload["node_id"], "node_id")
    _digest(payload["public_key_sha256"], "public_key_sha256")
    hostname = payload["endpoint_hostname"]
    if not isinstance(hostname, str) or _HOSTNAME.fullmatch(hostname) is None:
        raise MutationRequestRejected("endpoint_hostname must be bounded")
    _positive_int(payload["endpoint_port"], "endpoint_port", maximum=65535)
    _identifier(payload["approval_ref"], "approval_ref")


def _validate_fleet_decommission_payload(payload: Mapping[str, object]) -> None:
    if set(payload) != _FLEET_DECOMMISSION_FIELDS:
        raise MutationRequestRejected("Fleet removal payload fields are not exact")
    _identifier(payload["host_id"], "host_id")
    _identifier(payload["proposal_revision"], "proposal_revision")
    _identifier(payload["approval_ref"], "approval_ref")


def fleet_mutation_registry(service: FleetEnrollmentOwner) -> MutationRegistry:
    """Bind canonical Fleet enrollment and removal authority.

    ``service`` is the existing ``OpsToolService`` composition: it resolves
    authenticated discovery evidence itself and never accepts a self-asserted
    peer identity from the wire. Its ``registry`` owns exact removal authority.
    """
    from sofia.platform.ops.capability import OpsToolService
    from sofia.platform.ops.fleet import FleetRemovalApproval
    from sofia.platform.ops.state_registry import StatePlaneFleetRegistry

    if not isinstance(service, OpsToolService):
        raise TypeError("canonical OpsToolService required")
    registry = service.registry
    if not isinstance(registry, StatePlaneFleetRegistry):
        raise TypeError("canonical transactional Fleet registry required")

    def enroll(invocation: MutationInvocation) -> None:
        payload = invocation.payload
        try:
            service.enroll_candidate({
                "host_id": payload["host_id"],
                "node_id": payload["node_id"],
                "public_key_sha256": payload["public_key_sha256"],
                "endpoint_hostname": payload["endpoint_hostname"],
                "endpoint_port": payload["endpoint_port"],
                "approval_id": payload["approval_ref"],
            })
        except PermissionError as error:
            raise MutationDenied(
                "NOT_PERMITTED", "canonical Fleet enrollment authority rejected"
            ) from error
        except KeyError as error:
            raise MutationDenied(
                "EVIDENCE_UNAVAILABLE",
                "canonical Fleet candidate evidence is unavailable",
            ) from error

    def decommission(invocation: MutationInvocation) -> None:
        payload = invocation.payload
        try:
            registry.decommission(
                payload["host_id"],
                proposal_revision=payload["proposal_revision"],
                approval=FleetRemovalApproval(
                    payload["approval_ref"],
                    payload["host_id"],
                    payload["proposal_revision"],
                    "person:sparks",
                    invocation.now,
                ),
            )
        except PermissionError as error:
            raise MutationDenied(
                "NOT_PERMITTED", "canonical Fleet removal authority rejected"
            ) from error
        except KeyError as error:
            raise MutationDenied(
                "EVIDENCE_UNAVAILABLE", "canonical Fleet host is unavailable"
            ) from error

    return MutationRegistry((
        MutationOperation(
            name=FLEET_ENROLL_OPERATION,
            scopes=frozenset({FLEET_SCOPE}),
            handler=enroll,
            validate_payload=_validate_fleet_enroll_payload,
        ),
        MutationOperation(
            name=FLEET_DECOMMISSION_OPERATION,
            scopes=frozenset({FLEET_SCOPE}),
            handler=decommission,
            validate_payload=_validate_fleet_decommission_payload,
        ),
    ))


__all__ = [
    "FLEET_DECOMMISSION_OPERATION",
    "FLEET_ENROLL_OPERATION",
    "FLEET_SCOPE",
    "MODULE_LIFECYCLE_OPERATION",
    "MODULE_LIFECYCLE_SCOPE",
    "ModuleLifecycleOwner",
    "fleet_mutation_registry",
    "module_lifecycle_mutation_registry",
]
