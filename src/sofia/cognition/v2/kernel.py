"""Production Turn Kernel and structured discourse coordination."""
from __future__ import annotations

from dataclasses import replace
from typing import Callable

from .contracts import (
    CoordinatedTurn,
    ConversationFocus,
    FocusReference,
    FocusTopic,
    PendingAction,
    ReferenceResolution,
    TurnKernelInput,
    UnresolvedRequest,
)
from .focus import ConversationFocusConflict, SQLiteConversationFocusStore
from .references import ConversationReferenceResolver, EntityCandidate


_QUESTION_WORDS = frozenset({
    "can", "could", "do", "does", "give", "how", "is", "show", "tell",
    "what", "when", "where", "which", "who", "why",
})
_ACTION_WORDS = frozenset({
    "apply", "change", "delete", "deploy", "edit", "install", "move",
    "reboot", "remove", "restart", "start", "stop", "update", "upgrade",
})


class ProductionTurnKernel:
    """Sole production owner of turn sequencing and conversation focus.

    Matrix v1 and NEURO remain temporary delegated planners during Batch 2.
    Their callbacks cannot change the kernel's audience partition or reference
    resolution. Batch 3 replaces the Matrix delegate behind this boundary.
    """

    def __init__(
        self,
        store: SQLiteConversationFocusStore,
        *,
        entity_provider: Callable[[], tuple[EntityCandidate, ...]] | None = None,
    ) -> None:
        if not isinstance(store, SQLiteConversationFocusStore):
            raise TypeError("store must be SQLiteConversationFocusStore")
        if entity_provider is not None and not callable(entity_provider):
            raise TypeError("entity_provider must be callable or None")
        self.store = store
        self.entity_provider = entity_provider
        self.resolver = ConversationReferenceResolver()

    def coordinate(
        self,
        turn: TurnKernelInput,
        *,
        planning_callback: Callable[[CoordinatedTurn], object],
        attention_callback: Callable[[CoordinatedTurn], object],
    ) -> CoordinatedTurn:
        """Resolve/commit focus, then sequence planning and attention."""
        if not isinstance(turn, TurnKernelInput):
            raise TypeError("turn must be TurnKernelInput")
        if not callable(planning_callback) or not callable(attention_callback):
            raise TypeError("kernel callbacks must be callable")
        coordinated = self._advance_focus(turn)
        planning_callback(coordinated)
        attention_callback(coordinated)
        return coordinated

    def _advance_focus(self, turn: TurnKernelInput) -> CoordinatedTurn:
        candidates = (
            () if self.entity_provider is None else self.entity_provider()
        )
        if not isinstance(candidates, tuple) or any(
            not isinstance(item, EntityCandidate) for item in candidates
        ):
            raise TypeError("entity_provider must return EntityCandidate tuple")
        for _ in range(3):
            current = self.store.load(
                session_id=turn.session_id,
                audience_id=turn.audience_id,
            )
            resolution, reference = self.resolver.resolve(
                turn.content,
                focus=current,
                candidates=candidates,
                turn_id=turn.turn_id,
            )
            updated = self._updated_focus(current, turn, resolution, reference)
            try:
                committed = self.store.commit(
                    updated,
                    expected_revision=current.revision,
                )
                return CoordinatedTurn(turn, committed, resolution)
            except ConversationFocusConflict:
                continue
        raise ConversationFocusConflict(
            "conversation focus changed repeatedly during turn coordination"
        )

    @staticmethod
    def _updated_focus(
        current: ConversationFocus,
        turn: TurnKernelInput,
        resolution: ReferenceResolution,
        reference: FocusReference | None,
    ) -> ConversationFocus:
        references = list(current.references)
        primary = current.primary_reference
        if reference is not None:
            references = [
                item for item in references
                if item.reference_id != reference.reference_id
            ]
            references.append(reference)
            references = references[-16:]
            primary = reference

        topics = list(current.topics)
        if primary is not None:
            topic_id = f"topic:{primary.subject_id}"
            topics = [item for item in topics if item.topic_id != topic_id]
            topics.append(FocusTopic(
                topic_id=topic_id,
                subject_ids=(primary.subject_id,),
                last_turn_id=turn.turn_id,
                salience=1.0,
            ))
            topics = [
                replace(item, salience=round(item.salience * 0.82, 3))
                if item.topic_id != topic_id else item
                for item in topics[-8:]
            ]

        words = tuple(
            word.strip(".,!?;:'\"()[]{}").casefold()
            for word in turn.content.split()
            if word.strip(".,!?;:'\"()[]{}")
        )
        is_question = (
            "?" in turn.content
            or (bool(words) and words[0] in _QUESTION_WORDS)
        )
        command_words = words[1:] if words[:1] == ("please",) else words
        is_action = bool(
            command_words
            and (
                command_words[0] in _ACTION_WORDS
                or command_words[:2] == ("do", "it")
            )
        )
        unresolved = [
            item for item in current.unresolved_requests
            if item.request_id != f"request:{turn.turn_id}"
        ]
        if is_question or is_action:
            unresolved.append(UnresolvedRequest(
                request_id=f"request:{turn.turn_id}",
                source_turn_id=turn.turn_id,
                subject_id=(None if primary is None else primary.subject_id),
                request_kind=("action" if is_action else "information"),
                created_at=turn.created_at,
            ))
        pending = [
            item for item in current.pending_actions
            if item.action_id != f"action:{turn.turn_id}"
        ]
        if is_action:
            pending.append(PendingAction(
                action_id=f"action:{turn.turn_id}",
                source_turn_id=turn.turn_id,
                subject_id=(None if primary is None else primary.subject_id),
                action_kind="requested-action",
                created_at=turn.created_at,
            ))
        return ConversationFocus(
            session_id=current.session_id,
            audience_id=current.audience_id,
            revision=current.revision + 1,
            primary_reference=primary,
            references=tuple(references),
            topics=tuple(topics),
            unresolved_requests=tuple(unresolved[-16:]),
            pending_actions=tuple(pending[-8:]),
        )

    def settle(
        self,
        coordinated: CoordinatedTurn,
        *,
        evidence_refs: tuple[str, ...],
    ) -> ConversationFocus:
        """Resolve only work proven by evidence/receipts; preserve unknown work."""
        if not isinstance(coordinated, CoordinatedTurn):
            raise TypeError("coordinated must be CoordinatedTurn")
        if not isinstance(evidence_refs, tuple):
            raise TypeError("evidence_refs must be tuple")
        factual = any(
            ref.startswith(("capability:", "environment:", "memory-retrieval:"))
            for ref in evidence_refs
        )
        executed = any(ref.startswith("execution-receipt:") for ref in evidence_refs)
        if not factual and not executed:
            return coordinated.focus
        target_subject = coordinated.resolution.subject_id
        for _ in range(3):
            current = self.store.load(
                session_id=coordinated.turn.session_id,
                audience_id=coordinated.turn.audience_id,
            )
            updated = ConversationFocus(
                session_id=current.session_id,
                audience_id=current.audience_id,
                revision=current.revision + 1,
                primary_reference=current.primary_reference,
                references=current.references,
                topics=current.topics,
                unresolved_requests=tuple(
                    item for item in current.unresolved_requests
                    if not (
                        (
                            item.source_turn_id == coordinated.turn.turn_id
                            or (
                                target_subject is not None
                                and item.subject_id == target_subject
                            )
                        )
                        and (
                            executed
                            or (factual and item.request_kind == "information")
                        )
                    )
                ),
                pending_actions=tuple(
                    item for item in current.pending_actions
                    if not (
                        executed
                        and (
                            item.source_turn_id == coordinated.turn.turn_id
                            or (
                                target_subject is not None
                                and item.subject_id == target_subject
                            )
                        )
                    )
                ),
            )
            try:
                return self.store.commit(updated, expected_revision=current.revision)
            except ConversationFocusConflict:
                continue
        raise ConversationFocusConflict("could not settle conversation focus")

    @staticmethod
    def prompt(coordinated: CoordinatedTurn) -> str | None:
        reference = coordinated.focus.primary_reference
        if reference is None:
            return None
        aliases = ", ".join(reference.aliases[:4]) or "none"
        return "\n".join((
            "TRUSTED CONVERSATION FOCUS (discourse only)",
            f"Primary subject id: {reference.subject_id}",
            f"Primary subject kind: {reference.kind}",
            f"Known aliases: {aliases}",
            f"Resolution source: {coordinated.resolution.source}",
            (
                "This preserves what the conversation refers to. It is not "
                "evidence that the subject exists, is reachable, or has any "
                "particular state. Use current evidence and normal authority "
                "for factual claims and actions."
            ),
        ))
