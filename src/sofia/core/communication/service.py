"""Owner-gated shorthand interpretation boundary (Sofia Core B05).

Teaching and withdrawing shorthand is a host-side authority action performed
by the authenticated owner principal — never model output. The conversation
side only ever reads deterministic current mappings for the exact audience of
the current turn.
"""
from __future__ import annotations

import re

from sofia.core.communication.shorthand import (
    ShorthandRecord,
    ShorthandStatus,
    ShorthandStore,
)
from sofia.core.social.model import PrincipalContext
from sofia.core.social.principals import SPARKS_PRINCIPAL_ID


class CommunicationLearningService:
    """Owner-taught communication learning boundary."""

    def __init__(self, store: ShorthandStore) -> None:
        if not isinstance(store, ShorthandStore):
            raise TypeError("store must be a ShorthandStore")
        self._store = store

    @staticmethod
    def _require_owner(
        principal: PrincipalContext | None,
    ) -> tuple[str, str]:
        if not isinstance(principal, PrincipalContext):
            raise TypeError(
                "shorthand teaching requires an authenticated PrincipalContext"
            )
        if principal.principal_id != SPARKS_PRINCIPAL_ID:
            raise PermissionError(
                "only the authenticated owner can teach or withdraw shorthand"
            )
        return principal.principal_id, principal.audience_id

    def teach(
        self,
        *,
        principal: PrincipalContext,
        token: str,
        expansion: str,
        evidence_ref: str,
        note: str | None = None,
        expected_revision: int | None = None,
        now,
    ) -> ShorthandRecord:
        principal_id, audience_id = self._require_owner(principal)
        return self._store.hold(
            ShorthandRecord(
                token=token,
                principal_id=principal_id,
                audience_id=audience_id,
                expansion=expansion,
                note=note,
                evidence_ref=evidence_ref,
                status=ShorthandStatus.ACTIVE,
                revision=1 if expected_revision is None else expected_revision + 1,
                recorded_at=now,
            ),
            expected_revision=expected_revision,
        )

    def withdraw(
        self,
        *,
        principal: PrincipalContext,
        token: str,
        evidence_ref: str,
        note: str | None = None,
        expected_revision: int,
        now,
    ) -> ShorthandRecord:
        principal_id, audience_id = self._require_owner(principal)
        current = self._store.current(
            token, principal_id=principal_id, audience_id=audience_id,
        )
        if current is None or current.status is not ShorthandStatus.ACTIVE:
            raise LookupError("no active shorthand mapping for that token")
        return self._store.hold(
            ShorthandRecord(
                token=token,
                principal_id=principal_id,
                audience_id=audience_id,
                expansion=current.expansion,
                note=note,
                evidence_ref=evidence_ref,
                status=ShorthandStatus.WITHDRAWN,
                revision=current.revision + 1,
                recorded_at=now,
            ),
            expected_revision=current.revision,
        )

    def interpret(
        self,
        *,
        principal: PrincipalContext | None,
        text: str,
    ) -> tuple:
        """Deterministic whole-word readings of one current message."""
        audience_id = getattr(principal, "audience_id", None)
        principal_id = getattr(principal, "principal_id", None)
        if (
            not isinstance(principal_id, str)
            or not principal_id.strip()
            or not isinstance(audience_id, str)
            or not audience_id.strip()
            or not isinstance(text, str)
        ):
            return ()
        tokens = tuple(
            candidate.group(0).lower()
            for candidate in _WORD_RE.finditer(text)
        )
        return self._store.interpretations(
            tokens, principal_id=principal_id, audience_id=audience_id,
        )

    def taught(self, *, principal: PrincipalContext) -> tuple:
        principal_id, audience_id = self._require_owner(principal)
        return self._store.taught(
            principal_id=principal_id, audience_id=audience_id,
        )


_WORD_RE = re.compile(r"(?u)[A-Za-z][A-Za-z0-9'-]*")
