"""Operator CLI for exact-approved Fleet release rollout."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from uuid import UUID, uuid4

from sofia.config.defaults import production_state_path
from sofia.distributed.authorization import RemoteGrant
from sofia.distributed.capability import create_configured_remote_fleet_service
from sofia.distributed.durable import DurableRemoteAuthorization
from sofia.ops.state_registry import StatePlaneFleetRegistry
from sofia.run.release_rollout import (
    ReleaseRolloutCoordinator,
    ReleaseRolloutTarget,
    RemoteFleetReleaseOperator,
    RolloutRing,
)
from sofia.safe.execution_approval import ExecutionApprovalVerifier
from sofia.state.factory import create_state_plane


def _targets(raw: str) -> tuple[ReleaseRolloutTarget, ...]:
    result = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError("targets must use host_id:ring")
        host_id, ring = item.rsplit(":", 1)
        result.append(
            ReleaseRolloutTarget(
                host_id.strip(),
                RolloutRing(ring.strip().casefold()),
            )
        )
    return tuple(result)


@contextmanager
def _temporary_release_grants(
    state_path: Path,
    node_ids: tuple[str, ...],
    *,
    now: datetime,
):
    """Materialize exact node/operation grants derived from one Sparks approval."""
    store = DurableRemoteAuthorization(state_path)
    grants = []
    try:
        for node_id_text in node_ids:
            node_id = UUID(node_id_text)
            for capability, operation in (
                ("release.manage", "stage"),
                ("release.manage", "activate"),
                ("release.manage", "rollback"),
            ):
                grant = RemoteGrant(
                    uuid4(),
                    node_id,
                    capability,
                    operation,
                    "Sparks",
                    now + timedelta(minutes=15),
                )
                store.add_approved_grant(grant)
                grants.append(grant)
        yield tuple(grants)
    finally:
        for grant in grants:
            store.revoke(grant.grant_id)
        store.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.run.release_rollout_cli"
    )
    parser.add_argument("--state-path")
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--targets", required=True)
    parser.add_argument("--approval-id", required=True)
    parser.add_argument("--rollout-id")
    args = parser.parse_args(argv)

    state_path = (
        Path(args.state_path)
        if args.state_path
        else production_state_path()
    )
    targets = _targets(args.targets)
    rollout_id = args.rollout_id or f"rollout-{uuid4()}"
    digest = args.manifest_sha256.casefold()
    exact = {
        "release_id": args.release_id,
        "manifest_sha256": digest,
        "targets": [
            {"host_id": target.host_id, "ring": target.ring.value}
            for target in targets
        ],
    }

    try:
        plane = create_state_plane(state_path)
        registry = StatePlaneFleetRegistry(
            plane,
            legacy_path=state_path.parent / "fleet.json",
        )
        node_ids = []
        for target in targets:
            host = registry.host(target.host_id)
            if host is None or not host.trusted or host.node_id is None:
                raise PermissionError(
                    "release target is not an enrolled trusted Fleet host: "
                    + target.host_id
                )
            node_ids.append(str(host.node_id))

        now = datetime.now(timezone.utc)
        approval = ExecutionApprovalVerifier(state_path).consume(
            approval_id=args.approval_id,
            capability="release.rollout.execute",
            parameters=exact,
            now=now,
        )
        if approval.approved_by != "Sparks":
            raise PermissionError("release rollout approval must come from Sparks")

        remote = create_configured_remote_fleet_service(state_path)
        if remote is None:
            raise RuntimeError(
                "release rollout requires pinned-mTLS Fleet transport"
            )

        def node_for(host_id: str) -> str:
            host = registry.host(host_id)
            if host is None or not host.trusted or host.node_id is None:
                raise PermissionError(
                    f"release target left trusted Fleet membership: {host_id}"
                )
            return str(host.node_id)

        with _temporary_release_grants(
            state_path,
            tuple(node_ids),
            now=now,
        ):
            result = ReleaseRolloutCoordinator(
                state_plane=plane,
                operator=RemoteFleetReleaseOperator(
                    remote_service=remote,
                    host_node_lookup=node_for,
                ),
            ).rollout(
                rollout_id=rollout_id,
                release_id=args.release_id,
                manifest_sha256=digest,
                targets=targets,
            )

        print(
            f"release rollout completed: rollout_id={result.rollout_id} "
            f"release_id={result.release_id} events={len(result.events)}"
        )
        return 0
    except Exception as exc:
        print(
            f"release rollout failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
