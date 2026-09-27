from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import uuid4

from sofia.evolve.revision import RevisionAdapter, RevisionScope
from sofia.state.model import StateClass, StateKey, StateRecord
from sofia.state.plane import StatePlane


_EMPTY_DIGEST = sha256(b"").hexdigest()


class StatePlaneRevisionAdapter(RevisionAdapter):
    """State-Plane-backed reviewed config/preference revision adapter."""

    def __init__(self, state_plane: StatePlane) -> None:
        if not isinstance(state_plane, StatePlane):
            raise TypeError("state_plane must be a StatePlane")
        self._state_plane = state_plane

    @staticmethod
    def _namespace(scope: RevisionScope) -> str:
        if scope is RevisionScope.CONFIG:
            return "evolve-config"
        if scope is RevisionScope.PREFERENCE:
            return "evolve-preference"
        raise TypeError("unknown RevisionScope")

    @staticmethod
    def _key(scope: RevisionScope, key: str) -> StateKey:
        if not isinstance(scope, RevisionScope):
            raise TypeError("scope must be a RevisionScope")
        if not isinstance(key, str) or not key.strip():
            raise ValueError("revision key must be nonempty")
        return StateKey(
            namespace=StatePlaneRevisionAdapter._namespace(scope),
            key=key,
        )

    def _record(self, scope: RevisionScope, key: str) -> StateRecord | None:
        return self._state_plane.read(self._key(scope, key))

    def read_digest(self, scope: RevisionScope, key: str) -> str:
        record = self._record(scope, key)
        if record is None:
            return _EMPTY_DIGEST
        return sha256(record.value).hexdigest()

    def validate(
        self,
        scope: RevisionScope,
        key: str,
        proposed_content: str,
    ) -> None:
        self._key(scope, key)
        if not isinstance(proposed_content, str):
            raise TypeError("proposed_content must be text")
        if len(proposed_content.encode("utf-8")) > 262_144:
            raise ValueError("reviewed revision content exceeds 256 KiB")
        if scope is RevisionScope.CONFIG:
            try:
                decoded = json.loads(proposed_content)
            except json.JSONDecodeError as exc:
                raise ValueError("config revision must be valid JSON") from exc
            if not isinstance(decoded, dict):
                raise ValueError("config revision must be a JSON object")
        elif not proposed_content.strip():
            raise ValueError("preference revision cannot be blank")

    def apply(
        self,
        scope: RevisionScope,
        key: str,
        *,
        expected_digest: str,
        proposed_content: str,
    ) -> str:
        self.validate(scope, key, proposed_content)
        state_key = self._key(scope, key)
        existing = self._state_plane.read(state_key)
        current = _EMPTY_DIGEST if existing is None else sha256(existing.value).hexdigest()
        if current != expected_digest:
            raise RuntimeError("revision source changed before apply")

        token = str(uuid4())
        rollback_key = StateKey(
            namespace="evolve-rollback",
            key=token,
        )
        rollback_payload = json.dumps(
            {
                "scope": scope.value,
                "key": key,
                "previous": (
                    None
                    if existing is None
                    else existing.value.decode("utf-8")
                ),
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        now = datetime.now(timezone.utc)
        self._state_plane.write(
            StateRecord(
                key=rollback_key,
                state_class=StateClass.PROTECTED,
                revision=1,
                value=rollback_payload,
                updated_at=now,
                source="evolve:rollback-material",
            ),
            expected_revision=None,
        )

        revision = 1 if existing is None else existing.revision + 1
        self._state_plane.write(
            StateRecord(
                key=state_key,
                state_class=StateClass.SHARED_AUTHORITATIVE,
                revision=revision,
                value=proposed_content.encode("utf-8"),
                updated_at=now,
                source="evolve:reviewed-revision",
            ),
            expected_revision=None if existing is None else existing.revision,
        )
        return token

    def rollback(
        self,
        scope: RevisionScope,
        key: str,
        *,
        expected_current_digest: str,
        rollback_token: str,
    ) -> None:
        state_key = self._key(scope, key)
        existing = self._state_plane.read(state_key)
        current = _EMPTY_DIGEST if existing is None else sha256(existing.value).hexdigest()
        if current != expected_current_digest:
            raise RuntimeError("revision target changed before rollback")
        material = self._state_plane.read(
            StateKey(namespace="evolve-rollback", key=rollback_token)
        )
        if material is None:
            raise RuntimeError("rollback material does not exist")
        payload = json.loads(material.value.decode("utf-8"))
        if payload.get("scope") != scope.value or payload.get("key") != key:
            raise RuntimeError("rollback material belongs to another revision")
        previous = payload.get("previous")
        restored = "" if previous is None else previous
        now = datetime.now(timezone.utc)
        revision = 1 if existing is None else existing.revision + 1
        self._state_plane.write(
            StateRecord(
                key=state_key,
                state_class=StateClass.SHARED_AUTHORITATIVE,
                revision=revision,
                value=restored.encode("utf-8"),
                updated_at=now,
                source=f"evolve:rollback:{rollback_token}",
            ),
            expected_revision=None if existing is None else existing.revision,
        )
