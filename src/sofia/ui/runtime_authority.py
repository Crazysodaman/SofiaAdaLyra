"""Deferred runtime chat authority record for roadmap step #10.

The live desktop does not consume this record to move chat/state ownership.
Any future use requires redundancy, fencing, and one-writer mobility acceptance.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from re import fullmatch

from sofia.state.model import StateClass, StateKey, StateRecord
from sofia.state.plane import StatePlane


class RuntimeAuthorityState(str, Enum):
    READY = "ready"
    DEGRADED = "degraded"


@dataclass(frozen=True, slots=True)
class RuntimeChatAuthority:
    host_id: str
    endpoint: str
    authority_epoch: int
    server_public_key_sha256: str
    state: RuntimeAuthorityState

    def __post_init__(self) -> None:
        if not isinstance(self.host_id, str) or not self.host_id.strip():
            raise ValueError("host_id required")
        if not isinstance(self.endpoint, str) or not self.endpoint.startswith("https://"):
            raise ValueError("endpoint must be an https URL")
        if type(self.authority_epoch) is not int or self.authority_epoch < 1:
            raise ValueError("authority_epoch must be positive")
        if fullmatch(r"[0-9a-f]{64}", self.server_public_key_sha256) is None:
            raise ValueError("server pin must be lowercase SHA-256")
        if not isinstance(self.state, RuntimeAuthorityState):
            raise TypeError("state must be RuntimeAuthorityState")


class RuntimeChatAuthorityStore:
    """
    Durable consumer boundary for OPS/RUN-published runtime chat authority.

    This store does not decide leadership. Only a higher-level OPS/RUN authority
    holder may publish records. UI consumes them and otherwise stays local.
    """

    NAMESPACE = "runtime-chat-authority"
    KEY = "active"

    def __init__(self, state_plane: StatePlane) -> None:
        if not isinstance(state_plane, StatePlane):
            raise TypeError("state_plane must be a StatePlane")
        self._state_plane = state_plane

    def current(self) -> RuntimeChatAuthority | None:
        record = self._state_plane.read(
            StateKey(namespace=self.NAMESPACE, key=self.KEY)
        )
        if record is None:
            return None
        raw = json.loads(record.value.decode("utf-8"))
        return RuntimeChatAuthority(
            host_id=raw["host_id"],
            endpoint=raw["endpoint"],
            authority_epoch=int(raw["authority_epoch"]),
            server_public_key_sha256=raw["server_public_key_sha256"],
            state=RuntimeAuthorityState(raw["state"]),
        )

    def publish(
        self,
        authority: RuntimeChatAuthority,
        *,
        source: str,
        updated_at,
    ) -> RuntimeChatAuthority:
        if not isinstance(authority, RuntimeChatAuthority):
            raise TypeError("authority must be RuntimeChatAuthority")
        if not isinstance(source, str) or not source.startswith("ops-run:"):
            raise PermissionError("runtime authority publication requires OPS/RUN source")
        current = self._state_plane.read(
            StateKey(namespace=self.NAMESPACE, key=self.KEY)
        )
        if current is not None:
            existing = self.current()
            if existing is not None and authority.authority_epoch < existing.authority_epoch:
                raise PermissionError("runtime authority epoch may not roll back")
        payload = json.dumps(
            {
                "host_id": authority.host_id,
                "endpoint": authority.endpoint,
                "authority_epoch": authority.authority_epoch,
                "server_public_key_sha256": authority.server_public_key_sha256,
                "state": authority.state.value,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self._state_plane.write(
            StateRecord(
                key=StateKey(namespace=self.NAMESPACE, key=self.KEY),
                state_class=StateClass.SHARED_AUTHORITATIVE,
                revision=1 if current is None else current.revision + 1,
                value=payload,
                updated_at=updated_at,
                source=source,
            ),
            expected_revision=None if current is None else current.revision,
        )
        return authority
