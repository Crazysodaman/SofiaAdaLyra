from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from uuid import UUID

from sofia.ops.fleet import FleetRemovalApproval
from sofia.ops.fleet import FleetRegistry
from sofia.ops.model import FleetHost, HostLifecycle, HostTelemetry
from sofia.state.atomic_file import retire_legacy_file
from sofia.state.model import StateClass, StateKey, StateRecord
from sofia.state.plane import StatePlane


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
        before = self._hosts[host_id]
        updated = super().decommission(
            host_id,
            proposal_revision=proposal_revision,
            approval=approval,
        )
        try:
            self._persist(updated, source="ops:fleet-decommission")
        except Exception:
            self._hosts[host_id] = before
            raise
        return updated
