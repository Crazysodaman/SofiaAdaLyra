"""Authenticated editor and renderer-acknowledged world interaction boundary."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

from sofia.social.model import PrincipalContext

from .world_model import (
    Transform, WorldInteractionDecision, WorldInteractionReceipt,
    aware, bounded_text, world_id,
)
from .world_store import VirtualWorldStore


class WorldEditor:
    _VERBS = frozenset({"inspect", "use", "open", "close", "sit", "read", "play", "water", "arrange"})

    def __init__(
        self, store: VirtualWorldStore, *, principal: PrincipalContext,
        owner_principal_id: str,
    ) -> None:
        if not isinstance(store, VirtualWorldStore):
            raise TypeError("store must be VirtualWorldStore")
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated PrincipalContext required")
        self.store, self.principal = store, principal
        self.owner_principal_id = world_id(owner_principal_id, "owner_principal_id")

    @property
    def audience_id(self) -> str:
        return self.principal.audience_id

    def rename_space(self, space_id: str, name: str, *, expected_revision: int,
                     evidence_ref: str, now: datetime):
        return self.store.update_space(
            space_id=space_id, owner_principal_id=self.owner_principal_id,
            audience_id=self.audience_id, expected_revision=expected_revision,
            actor_principal_id=self.principal.principal_id, evidence_ref=evidence_ref,
            now=now, name=name,
        )

    def archive_space(self, space_id: str, *, expected_revision: int,
                      evidence_ref: str, now: datetime, archived: bool = True):
        return self.store.update_space(
            space_id=space_id, owner_principal_id=self.owner_principal_id,
            audience_id=self.audience_id, expected_revision=expected_revision,
            actor_principal_id=self.principal.principal_id, evidence_ref=evidence_ref,
            now=now, archived=archived,
        )

    def arrange(
        self, object_id: str, transform: Transform, *, expected_revision: int,
        evidence_ref: str, now: datetime,
    ):
        return self.store.update_object(
            object_id=object_id, owner_principal_id=self.owner_principal_id,
            audience_id=self.audience_id, expected_revision=expected_revision,
            actor_principal_id=self.principal.principal_id, evidence_ref=evidence_ref,
            now=now, transform=transform,
        )

    def interact(
        self, *, object_id: str, verb: str, gesture: str | None,
        evidence_ref: str, now: datetime,
    ) -> WorldInteractionDecision:
        if verb not in self._VERBS:
            raise ValueError("unsupported virtual object interaction")
        if gesture is not None:
            world_id(gesture, "gesture")
        bounded_text(evidence_ref, "evidence_ref", 300)
        item = self.store.get_object(
            object_id, self.owner_principal_id, self.audience_id,
        )
        if item.archived or item.container_id is not None:
            raise ValueError("object is not present in the rendered scene")
        decision = WorldInteractionDecision(
            f"world-interaction:{uuid4()}", self.principal.principal_id,
            item.object_id, item.space_id, verb, gesture, item.revision,
            evidence_ref, aware(now),
        )
        with closing(self.store._connect()) as db, db:
            db.execute(
                "INSERT INTO world_interaction_decision VALUES(?,?,?,?,?,?,?,?,?)",
                (decision.interaction_id, decision.actor_id, decision.object_id,
                 decision.space_id, decision.verb, decision.gesture,
                 decision.object_revision, decision.evidence_ref,
                 decision.created_at.astimezone(timezone.utc).isoformat()),
            )
        return decision

    def acknowledge(
        self, interaction_id: str, *, rendered: bool, backend: str,
        detail: str, now: datetime,
    ) -> WorldInteractionReceipt:
        bounded_text(backend, "renderer backend", 160)
        status = "rendered" if rendered else "failed"
        receipt = WorldInteractionReceipt(
            f"world-interaction-receipt:{uuid4()}", interaction_id, status,
            backend, rendered, detail[:500], aware(now),
        )
        with closing(self.store._connect()) as db, db:
            decision = db.execute(
                "SELECT object_id,object_revision FROM world_interaction_decision WHERE interaction_id=?",
                (interaction_id,),
            ).fetchone()
            if decision is None:
                raise KeyError("unknown world interaction")
            current = db.execute(
                "SELECT revision FROM world_object WHERE object_id=?", (decision[0],)
            ).fetchone()
            if rendered and (current is None or int(current[0]) != int(decision[1])):
                raise RuntimeError("scene object changed before renderer acknowledgement")
            db.execute(
                "INSERT INTO world_interaction_receipt VALUES(?,?,?,?,?,?,?)",
                (receipt.receipt_id, receipt.interaction_id, receipt.status,
                 receipt.renderer_backend, int(receipt.acknowledged), receipt.detail,
                 receipt.occurred_at.astimezone(timezone.utc).isoformat()),
            )
        return receipt
