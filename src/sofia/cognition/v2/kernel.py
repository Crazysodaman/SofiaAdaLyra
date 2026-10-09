"""Production Turn Kernel and structured discourse coordination."""
from __future__ import annotations

from dataclasses import replace
from typing import Callable

from .contracts import (
    AcquisitionState,
    CoordinatedTurn,
    ConversationFocus,
    EpistemicState,
    EvidenceAtom,
    FocusReference,
    FocusTopic,
    PendingAction,
    TurnKernelInput,
    UnresolvedRequest,
)
from .focus import ConversationFocusConflict, SQLiteConversationFocusStore
from .matrix import MatrixV2Planner
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

    The v2 Matrix planner owns semantic planning. Legacy safety/privacy
    projections remain downstream compatibility enforcement until the final
    v1-removal batch; callbacks cannot change the kernel's audience partition
    or reference resolution.
    """

    def __init__(
        self,
        store: SQLiteConversationFocusStore,
        *,
        entity_provider: Callable[[], tuple[EntityCandidate, ...]] | None = None,
        matrix_planner: MatrixV2Planner | None = None,
    ) -> None:
        if not isinstance(store, SQLiteConversationFocusStore):
            raise TypeError("store must be SQLiteConversationFocusStore")
        if entity_provider is not None and not callable(entity_provider):
            raise TypeError("entity_provider must be callable or None")
        self.store = store
        self.entity_provider = entity_provider
        self.resolver = ConversationReferenceResolver()
        self.matrix_planner = matrix_planner or MatrixV2Planner()

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
        neuro_snapshot = attention_callback(coordinated)
        if neuro_snapshot is not None:
            coordinated = replace(
                coordinated,
                plan=self.matrix_planner.plan(
                    coordinated.turn,
                    coordinated.focus,
                    neuro_snapshot=neuro_snapshot,
                ),
            )
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
            resolution, references = self.resolver.resolve_many(
                turn.content,
                focus=current,
                candidates=candidates,
                turn_id=turn.turn_id,
            )
            updated = self._updated_focus(current, turn, references)
            plan = self.matrix_planner.plan(turn, updated)
            updated = self._with_planned_requests(updated, turn, plan)
            try:
                committed = self.store.commit(
                    updated,
                    expected_revision=current.revision,
                )
                return CoordinatedTurn(
                    turn,
                    committed,
                    resolution,
                    plan,
                )
            except ConversationFocusConflict:
                continue
        raise ConversationFocusConflict(
            "conversation focus changed repeatedly during turn coordination"
        )

    @staticmethod
    def _updated_focus(
        current: ConversationFocus,
        turn: TurnKernelInput,
        turn_references: tuple[FocusReference, ...],
    ) -> ConversationFocus:
        references = list(current.references)
        primary = current.primary_reference
        if turn_references:
            turn_ids = {item.reference_id for item in turn_references}
            references = [
                item for item in references if item.reference_id not in turn_ids
            ]
            references.extend(turn_references)
            references = references[-16:]
            primary = turn_references[0]

        topics = list(current.topics)
        active_references = turn_references or (() if primary is None else (primary,))
        active_topic_ids = {f"topic:{item.subject_id}" for item in active_references}
        topics = [
            replace(item, salience=round(item.salience * 0.82, 3))
            for item in topics
            if item.topic_id not in active_topic_ids
        ]
        for index, item in enumerate(active_references):
            topics.append(FocusTopic(
                topic_id=f"topic:{item.subject_id}",
                subject_ids=(item.subject_id,),
                last_turn_id=turn.turn_id,
                salience=(1.0 if index == 0 else 0.9),
            ))
        topics = topics[-8:]

        words = tuple(
            word.strip(".,!?;:'\"()[]{}").casefold()
            for word in turn.content.split()
            if word.strip(".,!?;:'\"()[]{}")
        )
        command_words = words[1:] if words[:1] == ("please",) else words
        is_action = bool(
            command_words
            and (
                command_words[0] in _ACTION_WORDS
                or command_words[:2] == ("do", "it")
            )
        )
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
            unresolved_requests=current.unresolved_requests,
            pending_actions=tuple(pending),
        )

    @staticmethod
    def _with_planned_requests(current, turn, plan):
        """Persist one unresolved unit for every exact planned evidence need."""
        words = tuple(
            word.strip(".,!?;:'\"()[]{}").casefold()
            for word in turn.content.split()
            if word.strip(".,!?;:'\"()[]{}")
        )
        is_question = "?" in turn.content or (
            bool(words) and words[0] in _QUESTION_WORDS
        )
        command_words = words[1:] if words[:1] == ("please",) else words
        is_action = bool(command_words and (
            command_words[0] in _ACTION_WORDS
            or command_words[:2] == ("do", "it")
        ))
        unresolved = [
            item for item in current.unresolved_requests
            if item.source_turn_id != turn.turn_id
        ]
        if plan.evidence_needs:
            unresolved.extend(
                UnresolvedRequest(
                    request_id=f"request:{turn.turn_id}:need:{index}",
                    source_turn_id=turn.turn_id,
                    subject_id=need.subject_id,
                    request_kind="information",
                    created_at=turn.created_at,
                    predicate=need.predicate,
                    scope_id=need.scope_id,
                )
                for index, need in enumerate(plan.evidence_needs, start=1)
            )
        elif is_question:
            unresolved.append(UnresolvedRequest(
                request_id=f"request:{turn.turn_id}",
                source_turn_id=turn.turn_id,
                subject_id=(
                    None if current.primary_reference is None
                    else current.primary_reference.subject_id
                ),
                request_kind="information",
                created_at=turn.created_at,
            ))
        if is_action:
            unresolved.append(UnresolvedRequest(
                request_id=f"request:{turn.turn_id}:action",
                source_turn_id=turn.turn_id,
                subject_id=(
                    None if current.primary_reference is None
                    else current.primary_reference.subject_id
                ),
                request_kind="action",
                created_at=turn.created_at,
            ))
        return replace(current, unresolved_requests=tuple(unresolved))

    def settle(
        self,
        coordinated: CoordinatedTurn,
        *,
        evidence_refs: tuple[str, ...],
        evidence: tuple[EvidenceAtom, ...] = (),
    ) -> ConversationFocus:
        """Resolve only work proven by evidence/receipts; preserve unknown work."""
        if not isinstance(coordinated, CoordinatedTurn):
            raise TypeError("coordinated must be CoordinatedTurn")
        if not isinstance(evidence_refs, tuple):
            raise TypeError("evidence_refs must be tuple")
        if not isinstance(evidence, tuple) or any(
            not isinstance(item, EvidenceAtom) for item in evidence
        ):
            raise TypeError("evidence must contain EvidenceAtom values")
        factual = tuple(
            item for item in evidence
            if item.evidence_id in evidence_refs
            and item.acquisition_state is AcquisitionState.CURRENT
            and item.epistemic_state not in {
                EpistemicState.HYPOTHESIS,
                EpistemicState.UNKNOWN,
            }
        )
        executed = any(ref.startswith("execution-receipt:") for ref in evidence_refs)
        if not factual and not executed:
            return coordinated.focus
        exact_keys = {
            (item.subject_id, item.predicate, item.scope_id) for item in factual
        }
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
                        item.request_kind == "information"
                        and (
                            (
                                item.predicate is not None
                                and (item.subject_id, item.predicate, item.scope_id)
                                in exact_keys
                            )
                            or (
                                item.predicate is None
                                and item.source_turn_id == coordinated.turn.turn_id
                                and bool(factual)
                            )
                        )
                    )
                    and not (
                        item.request_kind == "action"
                        and executed
                        and item.source_turn_id == coordinated.turn.turn_id
                    )
                ),
                pending_actions=tuple(
                    item for item in current.pending_actions
                    if not (
                        executed
                        and (
                            item.source_turn_id == coordinated.turn.turn_id
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
