from __future__ import annotations

from datetime import timedelta
import os

from sofia.application.act_service import SofiaActService
from sofia.ops.capability import OpsToolService
from sofia.social.principals import SPARKS_PRINCIPAL_ID


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

    ops_service.enrollment.set_enrolled_notifier(enrolled)
    return True
