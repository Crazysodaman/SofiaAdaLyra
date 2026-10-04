from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from sofia.state.model import StateKey, StateRecord
from sofia.state.namespaces import StateNamespaceSpec
from sofia.state.plane import StatePlane


def _encode(value: dict[str, Any]) -> bytes:
    if not isinstance(value, dict):
        raise TypeError("State Plane JSON value must be an object")
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _decode(record: StateRecord) -> dict[str, Any]:
    try:
        value = json.loads(record.value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("State Plane record contains invalid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("State Plane JSON record must contain an object")
    return value


class JsonStateRepository:
    """Typed namespace facade over the backend-neutral State Plane."""

    def __init__(self, state_plane: StatePlane, spec: StateNamespaceSpec) -> None:
        if not isinstance(state_plane, StatePlane):
            raise TypeError("state_plane must be a StatePlane")
        if not isinstance(spec, StateNamespaceSpec):
            raise TypeError("spec must be a StateNamespaceSpec")
        self.state_plane = state_plane
        self.spec = spec

    def _key(
        self,
        key: str,
        *,
        principal_id: str | None,
        audience: str | None,
    ) -> StateKey:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("record key must be nonempty")
        if self.spec.principal_scoped:
            if not isinstance(principal_id, str) or not principal_id.strip():
                raise ValueError(
                    f"{self.spec.name} requires an authenticated principal"
                )
        elif principal_id is not None:
            raise ValueError(
                f"{self.spec.name} is not principal-scoped"
            )
        if self.spec.audience_scoped:
            if not isinstance(audience, str) or not audience.strip():
                raise ValueError(
                    f"{self.spec.name} requires an audience"
                )
        elif audience is not None:
            raise ValueError(
                f"{self.spec.name} is not audience-scoped"
            )
        return StateKey(
            namespace=self.spec.name,
            key=key.strip(),
            principal_id=principal_id.strip() if principal_id else None,
            audience=audience.strip() if audience else None,
        )

    def get(
        self,
        key: str,
        *,
        principal_id: str | None = None,
        audience: str | None = None,
    ) -> tuple[dict[str, Any], StateRecord] | None:
        record = self.state_plane.read(
            self._key(
                key,
                principal_id=principal_id,
                audience=audience,
            )
        )
        if record is None:
            return None
        if record.state_class is not self.spec.state_class:
            raise ValueError(
                f"{self.spec.name} record has the wrong StateClass"
            )
        return _decode(record), record

    def create(
        self,
        key: str,
        value: dict[str, Any],
        *,
        updated_at: datetime,
        source: str,
        principal_id: str | None = None,
        audience: str | None = None,
    ) -> StateRecord:
        state_key = self._key(
            key,
            principal_id=principal_id,
            audience=audience,
        )
        return self.state_plane.write(
            StateRecord(
                key=state_key,
                state_class=self.spec.state_class,
                revision=1,
                value=_encode(value),
                updated_at=updated_at,
                source=source,
            ),
            expected_revision=None,
        )

    def put(
        self,
        key: str,
        value: dict[str, Any],
        *,
        updated_at: datetime,
        source: str,
        principal_id: str | None = None,
        audience: str | None = None,
    ) -> StateRecord:
        if self.spec.append_only:
            raise PermissionError(
                f"{self.spec.name} is append-only; use create()"
            )
        state_key = self._key(
            key,
            principal_id=principal_id,
            audience=audience,
        )
        existing = self.state_plane.read(state_key)
        return self.state_plane.write(
            StateRecord(
                key=state_key,
                state_class=self.spec.state_class,
                revision=1 if existing is None else existing.revision + 1,
                value=_encode(value),
                updated_at=updated_at,
                source=source,
            ),
            expected_revision=None if existing is None else existing.revision,
        )


    def list(
        self,
        *,
        principal_id: str | None = None,
        audience: str | None = None,
    ) -> tuple[tuple[dict[str, Any], StateRecord], ...]:
        # StatePlane None means the unscoped partition, never "all principals".
        if self.spec.principal_scoped and (
            not isinstance(principal_id, str) or not principal_id.strip()
        ):
            raise ValueError(
                f"{self.spec.name} list requires an authenticated principal"
            )
        if self.spec.audience_scoped and (
            not isinstance(audience, str) or not audience.strip()
        ):
            raise ValueError(
                f"{self.spec.name} list requires an audience"
            )
        records = self.state_plane.list_namespace(
            self.spec.name,
            principal_id=principal_id,
            audience=audience,
        )
        result: list[tuple[dict[str, Any], StateRecord]] = []
        for record in records:
            if record.state_class is not self.spec.state_class:
                raise ValueError(
                    f"{self.spec.name} record has the wrong StateClass"
                )
            result.append((_decode(record), record))
        return tuple(result)
