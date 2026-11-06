from __future__ import annotations

from dataclasses import replace
from contextlib import closing, ExitStack
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import UUID

from sofia.platform.ops.fleet import FleetRemovalApproval
from sofia.platform.ops.fleet import FleetRegistry
from sofia.platform.ops.model import FleetHost, HostLifecycle, HostTelemetry
from sofia.platform.state.atomic_file import retire_legacy_file
from sofia.platform.state.model import StateClass, StateKey, StateRecord
from sofia.platform.state.plane import StatePlane
from sofia.platform.state.sqlite_plane import SQLiteStatePlane


class StatePlaneFleetRegistry(FleetRegistry):
    """Authoritative Fleet host state with recovery-safe legacy JSON import."""

    NAMESPACE = "ops-fleet-host"

    def __init__(
        self,
        state_plane: StatePlane,
        *,
        legacy_path: Path | None = None,
    ) -> None:
        super().__init__()
        if not isinstance(state_plane, StatePlane):
            raise TypeError("state_plane must be a StatePlane")
        self.state_plane = state_plane
        self.legacy_path = legacy_path
        self._load()
        self._import_legacy_if_needed()

    @staticmethod
    def _encode(host: FleetHost) -> bytes:
        telemetry = None
        if host.telemetry is not None:
            telemetry = {
                **host.telemetry.__dict__,
                "observed_at": host.telemetry.observed_at.isoformat(),
            }
        return json.dumps(
            {
                "host_id": host.host_id,
                "platform": host.platform,
                "architecture": host.architecture,
                "lifecycle": host.lifecycle.value,
                "trusted": host.trusted,
                "telemetry": telemetry,
                "tags": list(host.tags),
                "node_id": (
                    None if host.node_id is None else str(host.node_id)
                ),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    @staticmethod
    def _decode_payload(raw: dict) -> FleetHost:
        telemetry = raw.get("telemetry")
        if telemetry is not None:
            telemetry["observed_at"] = datetime.fromisoformat(
                telemetry["observed_at"]
            )
            telemetry = HostTelemetry(**telemetry)
        return FleetHost(
            host_id=raw["host_id"],
            platform=raw["platform"],
            architecture=raw["architecture"],
            lifecycle=HostLifecycle(raw["lifecycle"]),
            trusted=bool(raw["trusted"]),
            telemetry=telemetry,
            tags=tuple(raw.get("tags", ())),
            node_id=(
                None
                if raw.get("node_id") is None
                else UUID(raw["node_id"])
            ),
        )

    @classmethod
    def _decode(cls, record: StateRecord) -> FleetHost:
        return cls._decode_payload(json.loads(record.value.decode("utf-8")))

    def _load(self) -> None:
        self._hosts = {
            host.host_id: host
            for host in (
                self._decode(record)
                for record in self.state_plane.list_namespace(self.NAMESPACE)
            )
        }

    def _import_legacy_if_needed(self) -> None:
        if self.legacy_path is None or not self.legacy_path.is_file():
            return
        raw = json.loads(self.legacy_path.read_text(encoding="utf-8"))
        hosts = tuple(self._decode_payload(item) for item in raw.get("hosts", []))
        if len({host.host_id for host in hosts}) != len(hosts):
            raise ValueError("duplicate host in legacy Fleet registry")
        for host in hosts:
            key = StateKey(namespace=self.NAMESPACE, key=host.host_id)
            existing = self.state_plane.read(key)
            if existing is not None:
                # Canonical later observations win; partial imports must match.
                if existing.source == "legacy-json:fleet" and self._decode(existing) != host:
                    raise ValueError("conflicting partial legacy Fleet import")
                continue
            self._persist(host, source="legacy-json:fleet")
            self._hosts[host.host_id] = host
        for host in hosts:
            record = self.state_plane.read(StateKey(namespace=self.NAMESPACE, key=host.host_id))
            if record is None:
                raise RuntimeError("legacy Fleet import did not verify")
            if record.source == "legacy-json:fleet" and self._decode(record) != host:
                raise ValueError("conflicting partial legacy Fleet import")
        retire_legacy_file(self.legacy_path)

    def _persist(
        self,
        host: FleetHost,
        *,
        source: str = "ops:fleet",
    ) -> None:
        key = StateKey(
            namespace=self.NAMESPACE,
            key=host.host_id,
        )
        existing = self.state_plane.read(key)
        timestamp = (
            host.telemetry.observed_at
            if host.telemetry is not None
            else datetime.now().astimezone()
        )
        self.state_plane.write(
            StateRecord(
                key=key,
                state_class=StateClass.SHARED_AUTHORITATIVE,
                revision=1 if existing is None else existing.revision + 1,
                value=self._encode(host),
                updated_at=timestamp,
                source=source,
            ),
            expected_revision=None if existing is None else existing.revision,
        )

    def register_candidate(self, host: FleetHost) -> None:
        before = self._hosts.get(host.host_id)
        super().register_candidate(host)
        try:
            self._persist(host)
        except Exception:
            if before is None:
                self._hosts.pop(host.host_id, None)
            else:
                self._hosts[host.host_id] = before
            raise

    def transition(
        self,
        host_id: str,
        state: HostLifecycle,
    ) -> FleetHost:
        before = self._hosts[host_id]
        updated = super().transition(host_id, state)
        try:
            self._persist(updated)
        except Exception:
            self._hosts[host_id] = before
            raise
        return updated

    def refine_candidate_identity(
        self,
        host_id: str,
        *,
        platform: str,
        architecture: str,
        tags: tuple[str, ...] | None = None,
    ) -> FleetHost:
        before = self._hosts[host_id]
        updated = super().refine_candidate_identity(
            host_id,
            platform=platform,
            architecture=architecture,
            tags=tags,
        )
        try:
            self._persist(
                updated,
                source="ops:fleet-discovery-refine",
            )
        except Exception:
            self._hosts[host_id] = before
            raise
        return updated

    def authenticate_candidate(
        self,
        host_id: str,
        node_id: UUID,
    ) -> FleetHost:
        before = self._hosts[host_id]
        updated = super().authenticate_candidate(host_id, node_id)
        try:
            self._persist(
                updated,
                source="ops:fleet-authenticated-candidate",
            )
        except Exception:
            self._hosts[host_id] = before
            raise
        return updated

    def update_telemetry(
        self,
        host_id: str,
        telemetry: HostTelemetry,
    ) -> FleetHost:
        before = self._hosts[host_id]
        updated = super().update_telemetry(host_id, telemetry)
        try:
            self._persist(updated)
        except Exception:
            self._hosts[host_id] = before
            raise
        return updated

    def decommission(
        self,
        host_id: str,
        *,
        proposal_revision: str,
        approval: FleetRemovalApproval,
    ) -> FleetHost:
        from sofia.platform.distributed.identity_durable import DurableNodeIdentityRegistry
        from sofia.platform.distributed.endpoint_policy_durable import DurableEndpointPolicy
        from sofia.platform.distributed.durable import DurableRemoteAuthorization
        from sofia.platform.safe.execution_approval import ExecutionApprovalVerifier

        self._require_removal_reference(host_id, proposal_revision, approval)
        if not isinstance(self.state_plane, SQLiteStatePlane):
            raise PermissionError("removal requires canonical transactional SQLite state")
        plane = self.state_plane
        verifier = ExecutionApprovalVerifier(plane.path)
        now = datetime.now(timezone.utc)
        with ExitStack() as owners:
            identities = DurableNodeIdentityRegistry(plane.path)
            owners.callback(identities.close)
            endpoints = DurableEndpointPolicy(plane.path)
            owners.callback(endpoints.close)
            grants = DurableRemoteAuthorization(plane.path)
            owners.callback(grants.close)
            with plane._lock, closing(plane._connect()) as db, db:
                db.execute("BEGIN IMMEDIATE")
                key = StateKey(namespace=self.NAMESPACE, key=host_id)
                row = db.execute(
                    "SELECT * FROM state_plane_record WHERE namespace=? AND record_key=? AND principal_id=? AND audience=?",
                    plane._scope(key),
                ).fetchone()
                if row is None:
                    raise KeyError(host_id)
                current = plane._record(row)
                if current.state_class is not StateClass.SHARED_AUTHORITATIVE:
                    raise PermissionError("Fleet removal requires authoritative Fleet state")
                before = self._decode(current)
                # A fresh exact approval may clean up residual NET trust on a
                # legacy tombstone; this never reactivates or reuses identity.
                updated = (
                    replace(before, trusted=False)
                    if before.lifecycle is HostLifecycle.DECOMMISSIONED
                    else self._removed_host(before)
                )
                parameters = self._removal_parameters(current, proposal_revision)
                verified = verifier.consume(
                    approval_id=approval.approval_id, capability="fleet.decommission",
                    parameters=parameters, now=now, _transaction_db=db,
                )
                if before.node_id is not None:
                    identities._retire_in_transaction(db, before.node_id)
                    endpoints._revoke_in_transaction(db, before.node_id)
                    grants._revoke_node_in_transaction(db, before.node_id)
                plane._write_one(db, StateRecord(
                    key=key, state_class=StateClass.SHARED_AUTHORITATIVE,
                    revision=current.revision+1, value=self._encode(updated),
                    updated_at=now, source="ops:fleet:owner-decommission",
                ), current.revision)
                verifier.audit.append_in_transaction(
                    db, actor_id=verified.principal_id, event_type="fleet.decommissioned",
                    payload={**parameters, "approval_id":verified.approval_id},
                    occurred_at=now, event_id=f"fleet-removal:{verified.approval_id}",
                )
        self._hosts[host_id] = updated
        return updated

    def removal_parameters(self, host_id: str, *, proposal_revision: str) -> dict:
        """Return inert exact-target fields for the existing owner approval path."""
        current = self.state_plane.read(StateKey(namespace=self.NAMESPACE, key=host_id))
        if current is None:
            raise KeyError(host_id)
        return self._removal_parameters(current, proposal_revision)

    def _removal_parameters(self, current: StateRecord, proposal_revision: str) -> dict:
        if not isinstance(proposal_revision, str) or not proposal_revision.strip():
            raise ValueError("proposal_revision must be nonempty text")
        host = self._decode(current)
        return {
            "host_id":host.host_id, "proposal_revision":proposal_revision,
            "expected_registry_revision":current.revision,
            "node_id":None if host.node_id is None else str(host.node_id),
            "previous_lifecycle":host.lifecycle.value,
        }
