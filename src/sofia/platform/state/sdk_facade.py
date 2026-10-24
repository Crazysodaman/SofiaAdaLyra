"""Platform implementation of the SDK state facade for isolated workers."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Callable, Mapping

from sofia.sdk import (
    AuthorityProjection,
    ComponentEndpoint,
    StateProjection,
)

from .model import StateRecord
from .plane import StateWrite
from .platform import StatePlatformService


GenerationValidator = Callable[[ComponentEndpoint], bool]
AuthorityValidator = Callable[
    [ComponentEndpoint, AuthorityProjection, str, str], bool
]


class PlatformSDKStateFacade:
    """Scoped JSON projections over the canonical Platform State Plane.

    Authentication and active-generation truth are injected by trusted
    Platform construction.  The facade itself neither authenticates a worker
    nor grants a namespace.  No path, connection, or backend object crosses
    the worker boundary.
    """

    MAX_VALUE_BYTES = 262_144

    def __init__(
        self,
        *,
        state: StatePlatformService,
        generation_is_active: GenerationValidator,
        authority_allows: AuthorityValidator,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        if not isinstance(state, StatePlatformService):
            raise TypeError("state must be StatePlatformService")
        if not callable(generation_is_active) or not callable(authority_allows):
            raise TypeError("trusted generation and authority validators required")
        if not callable(clock):
            raise TypeError("clock must be callable")
        self._state = state
        self._generation_is_active = generation_is_active
        self._authority_allows = authority_allows
        self._clock = clock

    def _admit(
        self,
        worker: ComponentEndpoint,
        authority: AuthorityProjection,
        namespace: str,
        operation: str,
    ) -> tuple[str | None, str | None]:
        if not isinstance(worker, ComponentEndpoint):
            raise TypeError("worker must be ComponentEndpoint")
        if not isinstance(authority, AuthorityProjection):
            raise TypeError("authority must be AuthorityProjection")
        authority.require_current(now=self._clock())
        if self._generation_is_active(worker) is not True:
            raise PermissionError("worker generation is not active")
        spec = self._state.namespace_spec(namespace)
        required_scope = f"state.{operation}:{namespace}"
        if required_scope not in authority.scopes:
            raise PermissionError("authority projection lacks exact state scope")
        if self._authority_allows(worker, authority, namespace, operation) is not True:
            raise PermissionError("Platform authority denied state operation")
        principal = authority.principal_id if spec.principal_scoped else None
        audience = authority.audience_id if spec.audience_scoped else None
        self._state.namespace_open(
            namespace, principal_id=principal, audience=audience,
        )
        return principal, audience

    @staticmethod
    def _projection(record: StateRecord) -> StateProjection:
        try:
            value = json.loads(record.value.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("state projection is not canonical JSON") from exc
        if not isinstance(value, dict):
            raise RuntimeError("state projection must contain a JSON object")
        return StateProjection(
            namespace=record.key.namespace,
            key=record.key.key,
            revision=record.revision,
            value_digest=sha256(record.value).hexdigest(),
            value=value,
        )

    def read_projection(
        self,
        *,
        worker: ComponentEndpoint,
        authority: AuthorityProjection,
        namespace: str,
        key: str,
    ) -> StateProjection | None:
        principal, audience = self._admit(
            worker, authority, namespace, "read",
        )
        handle = self._state.namespace_open(
            namespace, principal_id=principal, audience=audience,
        )
        record = self._state.plane.read(handle.key(key))
        return None if record is None else self._projection(record)

    def compare_and_set(
        self,
        *,
        worker: ComponentEndpoint,
        authority: AuthorityProjection,
        namespace: str,
        key: str,
        expected_revision: int | None,
        value: Mapping[str, object],
    ) -> StateProjection:
        principal, audience = self._admit(
            worker, authority, namespace, "write",
        )
        if expected_revision is not None and (
            type(expected_revision) is not int or expected_revision < 1
        ):
            raise ValueError("expected_revision must be positive or None")
        if not isinstance(value, Mapping):
            raise TypeError("value must be a mapping")
        try:
            encoded = json.dumps(
                dict(value), sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValueError("state value must be canonical JSON") from exc
        if len(encoded) > self.MAX_VALUE_BYTES:
            raise ValueError("state value exceeds SDK projection limit")
        spec = self._state.namespace_spec(namespace)
        if spec.append_only and expected_revision is not None:
            raise PermissionError("append-only namespace cannot be revised")
        handle = self._state.namespace_open(
            namespace, principal_id=principal, audience=audience,
        )
        revision = 1 if expected_revision is None else expected_revision + 1
        record = StateRecord(
            key=handle.key(key),
            state_class=spec.state_class,
            revision=revision,
            value=encoded,
            updated_at=self._clock(),
            source=f"sdk:{worker.component_id}:generation:{worker.generation}",
        )
        persisted, = self._state.write_transaction(
            (StateWrite(record, expected_revision),)
        )
        return self._projection(persisted)
