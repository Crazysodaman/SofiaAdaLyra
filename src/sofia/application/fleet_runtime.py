from __future__ import annotations

from datetime import timedelta
import json
import os

from sofia.application.act_service import SofiaActService
from sofia.ops.bootstrap import (
    AgentPackage,
    BootstrapDisposition,
    InstallAuthority,
)
from sofia.ops.capability import OpsToolService
from sofia.ops.discovery import FleetDiscoveryBootstrapCoordinator
from sofia.social.principals import SPARKS_PRINCIPAL_ID
from sofia.state.model import StateClass, StateKey, StateRecord


def configure_fleet_enrollment_notices(
    *,
    ops_service: OpsToolService,
    act_service: SofiaActService,
) -> bool:
    """
    Bind authenticated Fleet enrollment to a deduped ACT operational notice.

    No delivery channel is invented. If no approved notification destination is
    configured, enrollment remains functional and no notice is queued.
    """
    if not isinstance(ops_service, OpsToolService):
        raise TypeError("ops_service must be an OpsToolService")
    if not isinstance(act_service, SofiaActService):
        raise TypeError("act_service must be a SofiaActService")

    destination = os.environ.get(
        "SOFIA_NOTIFICATION_HA_SERVICE",
        "",
    ).strip()
    if not destination:
        ops_service.enrollment.set_enrolled_notifier(None)
        return False
    if (
        "/" in destination
        or not destination.replace("_", "").replace("-", "").isalnum()
    ):
        raise ValueError(
            "SOFIA_NOTIFICATION_HA_SERVICE must be one notify service name"
        )

    def enrolled(host, binding, enrollment, peer) -> None:
        observed = peer.observed_at
        notice_id = (
            f"fleet-enrolled:{host.host_id}:{enrollment.node.node_id}"
        )
        evidence_id = (
            f"fleet-peer:{enrollment.node.node_id}:"
            f"{peer.public_key_sha256[:16]}"
        )
        tags = ", ".join(host.tags) if host.tags else "none"
        try:
            act_service.queue_system_notice(
                notice_id=notice_id,
                recipient_id=SPARKS_PRINCIPAL_ID,
                channel="home_assistant",
                destination=destination,
                evidence_id=evidence_id,
                content=(
                    f"Fleet enrolled {host.host_id} as {enrollment.node.name}. "
                    f"Platform {host.platform}/{host.architecture}; "
                    f"trust verified by {peer.verifier}; tags: {tags}."
                ),
                created_at=observed,
                expires_at=observed + timedelta(days=7),
            )
        except Exception as exc:
            plane = getattr(ops_service.registry, "state_plane", None)
            if plane is None:
                return
            key = StateKey(
                namespace="ops-fleet-notice-failure",
                key=notice_id,
            )
            existing = plane.read(key)
            payload = json.dumps(
                {
                    "host_id": host.host_id,
                    "node_id": str(enrollment.node.node_id),
                    "error_type": type(exc).__name__,
                    "observed_at": observed.isoformat(),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            plane.write(
                StateRecord(
                    key=key,
                    state_class=StateClass.SHARED_AUTHORITATIVE,
                    revision=1 if existing is None else existing.revision + 1,
                    value=payload,
                    updated_at=observed,
                    source="ops:fleet-enrollment-notice",
                ),
                expected_revision=None if existing is None else existing.revision,
            )

    ops_service.enrollment.set_enrolled_notifier(enrolled)
    return True



def create_fleet_candidate_notifier(
    *,
    act_service: SofiaActService,
):
    """Return a deduped notice callback for newly discovered untrusted hosts."""
    if not isinstance(act_service, SofiaActService):
        raise TypeError("act_service must be a SofiaActService")
    destination = os.environ.get(
        "SOFIA_NOTIFICATION_HA_SERVICE",
        "",
    ).strip()
    if not destination:
        return None
    if (
        "/" in destination
        or not destination.replace("_", "").replace("-", "").isalnum()
    ):
        raise ValueError(
            "SOFIA_NOTIFICATION_HA_SERVICE must be one notify service name"
        )

    def discovered(host, observation) -> None:
        observed = observation.observed_at
        node_text = (
            str(observation.observed_node_id)
            if observation.observed_node_id is not None
            else "unverified"
        )
        act_service.queue_system_notice(
            notice_id=f"fleet-candidate:{host.host_id}",
            recipient_id=SPARKS_PRINCIPAL_ID,
            channel="home_assistant",
            destination=destination,
            evidence_id=(
                f"fleet-discovery:{host.host_id}:"
                f"{observation.source}"
            ),
            content=(
                f"New Fleet candidate discovered: {host.host_id} "
                f"({host.platform}/{host.architecture}). "
                f"Node evidence: {node_text}. "
                "The machine is untrusted and not enrolled yet."
            ),
            created_at=observed,
            expires_at=observed + timedelta(days=7),
        )

    return discovered



def create_fleet_bootstrap_coordinator(
    *,
    configuration,
    act_service: SofiaActService,
    installer_factory=None,
):
    """Compose discovery bootstrap planning from explicit production policy."""
    policy = configuration.fleet_bootstrap
    if not policy.enabled:
        return None
    if not policy.package_sha256 or not policy.package_source:
        raise ValueError(
            "Fleet bootstrap is enabled but the approved package SHA-256 "
            "and source are not both configured"
        )
    authority = InstallAuthority(policy.authority)
    package = AgentPackage(
        package_id=policy.package_id,
        version=policy.package_version,
        sha256=policy.package_sha256,
        source=policy.package_source,
        protocol_version=policy.protocol_version,
        signer_key_id=policy.signer_key_id,
    )
    notifier = create_fleet_bootstrap_plan_notifier(
        act_service=act_service,
    )
    return FleetDiscoveryBootstrapCoordinator(
        package=package,
        authority=authority,
        installer_factory=installer_factory,
        operator_notifier=notifier,
    )


def create_fleet_bootstrap_plan_notifier(
    *,
    act_service: SofiaActService,
):
    """Notify Sparks only when a candidate needs explicit bootstrap action."""
    if not isinstance(act_service, SofiaActService):
        raise TypeError("act_service must be a SofiaActService")
    destination = os.environ.get(
        "SOFIA_NOTIFICATION_HA_SERVICE",
        "",
    ).strip()
    if not destination:
        return None
    if (
        "/" in destination
        or not destination.replace("_", "").replace("-", "").isalnum()
    ):
        raise ValueError(
            "SOFIA_NOTIFICATION_HA_SERVICE must be one notify service name"
        )

    def notify(plan) -> None:
        if plan.disposition is not BootstrapDisposition.ASK_OPERATOR:
            return
        host_id = plan.candidate.host_id
        content = (
            plan.operator_message
            or (
                f"Fleet candidate {host_id} needs bootstrap authorization "
                "or a configured trusted installer."
            )
        )
        act_service.queue_system_notice(
            notice_id=f"fleet-bootstrap:{host_id}",
            recipient_id=SPARKS_PRINCIPAL_ID,
            channel="home_assistant",
            destination=destination,
            evidence_id=(
                f"fleet-bootstrap-plan:{host_id}:"
                f"{plan.package.sha256[:16]}"
            ),
            content=content,
            created_at=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ),
            expires_at=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ) + timedelta(days=7),
        )

    return notify
