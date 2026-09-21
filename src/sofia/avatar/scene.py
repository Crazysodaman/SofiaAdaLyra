"""Headless shared virtual props, with explicit proposal and acknowledgement.

No renderer, physical tool, desktop-control, authentication or event transport is
implemented here. The host must authenticate the actor and verify actual
renderer acknowledgements outside the model before calling acknowledge().
"""

from __future__ import annotations
from dataclasses import dataclass, replace
from enum import Enum
import re

_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z", re.ASCII)


class SceneError(ValueError):
    pass


class SceneConflict(RuntimeError):
    pass


class SceneDenied(PermissionError):
    pass


class Actor(str, Enum):
    SPARKS = "sparks"
    SOFIA = "sofia"


class Action(str, Enum):
    PICK_UP = "pick_up"
    PLACE = "place"
    OFFER = "offer"
    ACCEPT = "accept"
    DECLINE = "decline"


def _key(value: str) -> str:
    if not isinstance(value, str) or not _KEY.fullmatch(value):
        raise SceneError("invalid stable identifier")
    return value


@dataclass(frozen=True)
class Prop:
    prop_id: str
    label: str
    holder: Actor | None = None
    offered_to: Actor | None = None
    revision: int = 1

    def __post_init__(self):
        _key(self.prop_id)
        if not isinstance(self.label, str) or not self.label.strip() or len(self.label) > 160:
            raise SceneError("invalid prop label")
        if self.holder is not None and not isinstance(self.holder, Actor):
            raise SceneError("invalid holder")
        if self.offered_to is not None and (not isinstance(self.offered_to, Actor)
                                            or self.offered_to == self.holder):
            raise SceneError("invalid offer recipient")
        if self.offered_to is not None and self.holder is None:
            raise SceneError("only the holder can offer a prop")
        if type(self.revision) is not int or self.revision < 1:
            raise SceneError("invalid revision")


@dataclass(frozen=True)
class Proposal:
    operation_id: str
    prop_id: str
    actor: Actor
    action: Action
    expected_revision: int
    recipient: Actor | None = None


class Scene:
    """Single-scene virtual state; no network or external action capability.

    A trusted adapter must bind Actor.SPARKS to authenticated Sparks and
    Actor.SOFIA to the one authorized runtime. Public calls take typed actors,
    not usernames or raw LLM strings. PROPOSALS ARE NOT COMPLETED MOTIONS.
    """

    def __init__(self, props: tuple[Prop, ...]) -> None:
        if not isinstance(props, tuple) or any(not isinstance(p, Prop) for p in props):
            raise SceneError("props must be a tuple of Prop")
        if len({p.prop_id for p in props}) != len(props):
            raise SceneError("duplicate prop ID")
        self._props = {p.prop_id: p for p in props}
        self._pending: dict[str, Proposal] = {}
        self._finished: set[str] = set()
        self._stopped = False

    def read(self, prop_id: str) -> Prop:
        _key(prop_id)
        try:
            return self._props[prop_id]
        except KeyError as error:
            raise SceneError("unknown prop") from error

    def propose(
        self, *, operation_id: str, prop_id: str, actor: Actor,
        action: Action, expected_revision: int, recipient: Actor | None = None,
    ) -> Proposal:
        if self._stopped:
            raise SceneDenied("scene has been stopped")
        _key(operation_id)
        if operation_id in self._pending or operation_id in self._finished:
            raise SceneConflict("duplicate operation")
        if not isinstance(actor, Actor) or not isinstance(action, Action):
            raise SceneDenied("unrecognized actor or action")
        prop = self.read(prop_id)
        if type(expected_revision) is not int or prop.revision != expected_revision:
            raise SceneConflict("stale prop revision")
        if any(p.prop_id == prop_id for p in self._pending.values()):
            raise SceneConflict("another operation on this prop is pending")
        if action is Action.PICK_UP:
            allowed = prop.holder is None and prop.offered_to is None and recipient is None
        elif action is Action.PLACE:
            allowed = prop.holder is actor and prop.offered_to is None and recipient is None
        elif action is Action.OFFER:
            allowed = (prop.holder is actor and prop.offered_to is None
                       and isinstance(recipient, Actor) and recipient is not actor)
        elif action in (Action.ACCEPT, Action.DECLINE):
            allowed = prop.offered_to is actor and recipient is None
        else:
            allowed = False
        if not allowed:
            raise SceneDenied("action conflicts with holder, offer or recipient")
        proposal = Proposal(operation_id, prop_id, actor, action, expected_revision, recipient)
        self._pending[operation_id] = proposal
        return proposal

    def acknowledge(self, *, operation_id: str, renderer_succeeded: bool) -> Prop:
        """Only a trusted host should pass an independently verified receipt.

        False receipt or canceled action returns unchanged state; no false
        holder transition. A real renderer adapter MUST verify receipt origin,
        event ID, asset/scene version and actual result before calling this.
        """
        _key(operation_id)
        if self._stopped:
            raise SceneDenied("scene has been stopped")
        if type(renderer_succeeded) is not bool:
            raise SceneDenied("renderer receipt must be a strict boolean")
        if operation_id not in self._pending:
            raise SceneConflict("operation is missing, expired or already acknowledged")
        proposal = self._pending[operation_id]
        prop = self.read(proposal.prop_id)
        if prop.revision != proposal.expected_revision:
            raise SceneConflict("stale proposal")
        if renderer_succeeded:
            if proposal.action is Action.PICK_UP:
                updated = replace(prop, holder=proposal.actor, revision=prop.revision + 1)
            elif proposal.action is Action.PLACE:
                updated = replace(prop, holder=None, revision=prop.revision + 1)
            elif proposal.action is Action.OFFER:
                updated = replace(prop, offered_to=proposal.recipient,
                                  revision=prop.revision + 1)
            elif proposal.action is Action.ACCEPT:
                updated = replace(prop, holder=proposal.actor, offered_to=None,
                                  revision=prop.revision + 1)
            else:
                updated = replace(prop, offered_to=None, revision=prop.revision + 1)
            self._props[prop.prop_id] = updated
        else:
            updated = prop
        del self._pending[operation_id]
        self._finished.add(operation_id)
        return updated

    def cancel(self, *, operation_id: str) -> None:
        _key(operation_id)
        if operation_id not in self._pending:
            raise SceneConflict("no outstanding proposal")
        del self._pending[operation_id]
        self._finished.add(operation_id)

    def stop(self) -> None:
        self._stopped = True
        self._finished.update(self._pending)
        self._pending.clear()

    def snapshot(self) -> dict[str, object]:
        """Plain scene data; host owns private storage, snapshots and access."""
        if self._pending:
            raise SceneConflict("cannot snapshot while renderer operations are pending")
        return {
            "schema": 1,
            "props": [
                {"prop_id": p.prop_id, "label": p.label,
                 "holder": p.holder.value if p.holder else None,
                 "offered_to": p.offered_to.value if p.offered_to else None,
                 "revision": p.revision}
                for p in self._props.values()
            ],
            "finished": sorted(self._finished),
        }

    @classmethod
    def restore(cls, snapshot: dict[str, object]) -> Scene:
        if (not isinstance(snapshot, dict) or set(snapshot) != {"schema", "props", "finished"}
                or type(snapshot["schema"]) is not int or snapshot["schema"] != 1
                or not isinstance(snapshot["props"], list)
                or not isinstance(snapshot["finished"], list)):
            raise SceneError("invalid scene snapshot schema")
        try:
            props = []
            for raw in snapshot["props"]:
                if not isinstance(raw, dict) or set(raw) != {
                    "prop_id", "label", "holder", "offered_to", "revision"
                }:
                    raise SceneError("invalid prop snapshot")
                props.append(Prop(raw["prop_id"], raw["label"],
                                  Actor(raw["holder"]) if raw["holder"] is not None else None,
                                  Actor(raw["offered_to"]) if raw["offered_to"] is not None else None,
                                  raw["revision"]))
            finished = [_key(op) for op in snapshot["finished"]]
            if len(finished) != len(set(finished)):
                raise SceneError("duplicate completed operation")
            scene = cls(tuple(props))
            scene._finished.update(finished)
            return scene
        except SceneError:
            raise
        except (ValueError, TypeError, KeyError) as error:
            raise SceneError("invalid scene snapshot contents") from error
