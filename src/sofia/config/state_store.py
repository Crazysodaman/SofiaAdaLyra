from __future__ import annotations

from datetime import datetime
import json

from sofia.config.authority import (
    ConfigurationPrecedence,
    ConfigurationResolver,
    ConfigurationValue,
)
from sofia.state.model import StateClass, StateKey, StateRecord
from sofia.state.plane import StatePlane


class StatePlaneConfigurationStore:
    """Persist configuration authority records through the shared State Plane."""

    NAMESPACE = "configuration"

    def __init__(self, state_plane: StatePlane) -> None:
        if not isinstance(state_plane, StatePlane):
            raise TypeError("state_plane must be a StatePlane")
        self._state_plane = state_plane

    @staticmethod
    def _record_key(value: ConfigurationValue) -> str:
        host = value.host_id or "*"
        return f"{value.key}|{int(value.precedence)}|{host}|{value.actor_id}"

    @staticmethod
    def _encode(value: ConfigurationValue) -> bytes:
        return json.dumps(
            {
                "key": value.key,
                "value": value.value,
                "precedence": int(value.precedence),
                "revision": value.revision,
                "source": value.source,
                "actor_id": value.actor_id,
                "observed_at": value.observed_at.isoformat(),
                "host_id": value.host_id,
                "expires_at": (
                    value.expires_at.isoformat()
                    if value.expires_at is not None
                    else None
                ),
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

    @staticmethod
    def _decode(record: StateRecord) -> ConfigurationValue:
        payload = json.loads(record.value.decode("utf-8"))
        return ConfigurationValue(
            key=payload["key"],
            value=payload["value"],
            precedence=ConfigurationPrecedence(payload["precedence"]),
            revision=payload["revision"],
            source=payload["source"],
            actor_id=payload["actor_id"],
            observed_at=datetime.fromisoformat(payload["observed_at"]),
            host_id=payload.get("host_id"),
            expires_at=(
                datetime.fromisoformat(payload["expires_at"])
                if payload.get("expires_at") is not None
                else None
            ),
        )

    def put(self, value: ConfigurationValue) -> ConfigurationValue:
        if not isinstance(value, ConfigurationValue):
            raise TypeError("value must be a ConfigurationValue")
        key = StateKey(
            namespace=self.NAMESPACE,
            key=self._record_key(value),
        )
        existing = self._state_plane.read(key)
        state_revision = 1 if existing is None else existing.revision + 1
        record = StateRecord(
            key=key,
            state_class=(
                StateClass.PROTECTED
                if value.precedence is ConfigurationPrecedence.PROTECTED_POLICY
                else StateClass.SHARED_AUTHORITATIVE
            ),
            revision=state_revision,
            value=self._encode(value),
            updated_at=value.observed_at,
            source=value.source,
        )
        self._state_plane.write(
            record,
            expected_revision=None if existing is None else existing.revision,
        )
        return value

    def values(self, key: str) -> tuple[ConfigurationValue, ...]:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("key must be nonempty")
        prefix = f"{key}|"
        return tuple(
            self._decode(record)
            for record in self._state_plane.list_namespace(self.NAMESPACE)
            if record.key.key.startswith(prefix)
        )

    def resolve(
        self,
        key: str,
        *,
        now: datetime,
        host_id: str | None = None,
    ) -> ConfigurationValue | None:
        return ConfigurationResolver.resolve(
            self.values(key),
            now=now,
            host_id=host_id,
        )
