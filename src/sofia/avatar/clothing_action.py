"""Authoritative state-changing service for AVATAR clothing actions.

Parsing and autonomy policy live in separate pure modules. This service owns the
mutation boundary: resolve a requested wardrobe change, apply autonomy/privacy
policy, commit PresentationAuthority state, persist it, verify the matrix, then
describe only the committed result.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
import re
from threading import RLock

from sofia.safe.operator_stop import OperatorStopStore
from sofia.social.model import PrincipalContext

from .clothing_intent import (
    ClothingActionIntent,
    ClothingActionKind,
    ClothingActionParser,
    _clean_target,
    _normalize,
)
from .presentation import (
    PrivatePresentationGrant,
    PresentationState,
)
from .private_grant import PrivatePresentationGrantResolver
from .presentation_runtime import PresentationRuntimeBundle
from .wardrobe import (
    WardrobeConflict,
    WardrobeError,
    normalize_slots,
)
from .wardrobe_autonomy import (
    WardrobeAutonomyContext,
    WardrobeAutonomyPolicy,
)
from .wardrobe_planner import OutfitPlan, OutfitPlanner


class ClothingActionService:
    """Parse, decide, commit, persist, verify, then describe clothing changes."""

    def __init__(
        self,
        bundle: PresentationRuntimeBundle,
        *,
        autonomy: WardrobeAutonomyPolicy | None = None,
        context_provider: Callable[
            [], WardrobeAutonomyContext | None
        ] | None = None,
        adult_verified: bool = False,
        operator_stop_store: OperatorStopStore | None = None,
    ) -> None:
        if not isinstance(bundle, PresentationRuntimeBundle):
            raise TypeError("bundle must be PresentationRuntimeBundle")
        if autonomy is not None and not isinstance(
            autonomy,
            WardrobeAutonomyPolicy,
        ):
            raise TypeError(
                "autonomy must be WardrobeAutonomyPolicy or None"
            )
        if context_provider is not None and not callable(context_provider):
            raise TypeError(
                "context_provider must be callable or None"
            )
        if type(adult_verified) is not bool:
            raise TypeError("adult_verified must be bool")
        if operator_stop_store is not None and not isinstance(
            operator_stop_store,
            OperatorStopStore,
        ):
            raise TypeError(
                "operator_stop_store must be OperatorStopStore or None"
            )
        self.bundle = bundle
        self.autonomy = autonomy or WardrobeAutonomyPolicy()
        self.context_provider = context_provider
        self.parser = ClothingActionParser()
        self._grant_resolver = PrivatePresentationGrantResolver(
            state_path=bundle.store.database_path,
            adult_verified=adult_verified,
            operator_stop_store=operator_stop_store,
        )
        self._lock = RLock()
        self._blueprints = {
            blueprint.garment.item_id: blueprint
            for blueprint in bundle.catalog.blueprints
        }
        self._plans = {
            plan.outfit_id: plan
            for plan in bundle.catalog.presets
        }
        self._planner = OutfitPlanner(
            bundle.catalog.wardrobe,
            bundle.catalog.presets,
        )
        self._reviewed_preferences = (
            bundle.catalog.reviewed_preferences()
        )

    def handle(
        self,
        *,
        content: str,
        previous_user_content: str | None,
        operation_id: str,
        principal: PrincipalContext | None = None,
    ) -> str | None:
        """Serialize one wardrobe action across all conversation channels."""
        with self._lock:
            return self._handle_locked(
                content=content,
                previous_user_content=previous_user_content,
                operation_id=operation_id,
                principal=principal,
            )

    def _handle_locked(
        self,
        *,
        content: str,
        previous_user_content: str | None,
        operation_id: str,
        principal: PrincipalContext | None = None,
    ) -> str | None:
        """Return a deterministic reply when this is a clothing action."""
        if not isinstance(content, str):
            raise TypeError("content must be a string")
        if previous_user_content is not None and not isinstance(
            previous_user_content,
            str,
        ):
            raise TypeError(
                "previous_user_content must be a string or None"
            )
        if not isinstance(operation_id, str) or not operation_id.strip():
            raise ValueError("operation_id must be nonempty")
        if principal is not None and not isinstance(principal, PrincipalContext):
            raise TypeError("principal must be PrincipalContext or None")

        intent = self.parser.parse(content)
        if intent is None and self.parser.is_followup(content):
            if previous_user_content is None:
                return None
            prior = self.parser.parse(previous_user_content)
            if prior is None:
                return None
            intent = replace(prior, hypothetical=False)

        if intent is None:
            return None

        if intent.hypothetical:
            return self._hypothetical_reply(intent)

        if intent.kind is ClothingActionKind.UNDRESS:
            grant = self._private_grant(principal)
            if grant is None:
                return self._decline_private()
            return self._commit_nude(
                operation_id=operation_id,
                grant=grant,
            )

        if intent.kind is ClothingActionKind.WEAR:
            return self._wear(
                intent,
                operation_id=operation_id,
                principal=principal,
            )
        if intent.kind is ClothingActionKind.REMOVE:
            return self._remove(
                intent,
                operation_id=operation_id,
                principal=principal,
            )
        if intent.kind is ClothingActionKind.ADD:
            return self._add(
                intent,
                operation_id=operation_id,
                principal=principal,
            )
        if intent.kind is ClothingActionKind.SWAP:
            return self._swap(
                intent,
                operation_id=operation_id,
                principal=principal,
            )
        raise RuntimeError("unsupported clothing action kind")

    def _hypothetical_reply(self, intent: ClothingActionIntent) -> str:
        if intent.kind is ClothingActionKind.UNDRESS:
            return (
                "You can ask, but that would be a private presentation "
                "transition. I won't claim or commit it unless the runtime has "
                "the separate verified private-presentation grant. A request "
                "by itself does not change my wardrobe state."
            )
        return (
            "You can ask. I don't treat the request itself as a completed "
            "wardrobe change. I only claim a change after the current autonomy, "
            "authority, and wardrobe-matrix checks accept it and the new "
            "presentation is committed."
        )

    def _decline_private(self) -> str:
        return (
            "I'm keeping my current outfit. A nude/private presentation "
            "requires verified adult host authority, an authenticated private "
            "Sparks session, explicit current opt-in, and no active operator "
            "stop. Those requirements are not all satisfied, so my wardrobe "
            "state is unchanged."
        )

    def _private_grant(
        self,
        principal: PrincipalContext | None,
    ) -> PrivatePresentationGrant | None:
        return self._grant_resolver.resolve(
            principal=principal,
            explicit_current_opt_in=True,
        )

    def _commit_nude(
        self,
        *,
        operation_id: str,
        grant: PrivatePresentationGrant,
    ) -> str:
        current = self.bundle.authority.current

        def mutate() -> PresentationState:
            self.bundle.authority.propose_nude(
                operation_id=operation_id,
                expected_revision=current.revision,
                reason="user_clothing_action:undress",
                grant=grant,
            )
            return self.bundle.authority.commit_text(
                operation_id=operation_id,
                renderer_unavailable=True,
                grant=grant,
            )

        state = self.bundle.store.persist_mutation(
            self.bundle.authority,
            mutate,
        )
        if not isinstance(state, PresentationState):
            raise RuntimeError("nude presentation mutation returned invalid state")
        if self.bundle.current_matrix().item_ids:
            raise RuntimeError("nude presentation matrix must contain no garments")
        return (
            "I changed my AVATAR presentation to no clothing. The state is "
            "committed and persisted; this is headless presentation state, not "
            "a claim that a renderer displayed it."
        )

    def _wear(
        self,
        intent: ClothingActionIntent,
        *,
        operation_id: str,
        principal: PrincipalContext | None,
    ) -> str:
        target = intent.target or ""
        plan = self._resolve_outfit(target)
        if plan is not None:
            return self._commit_candidate(
                intent,
                operation_id=operation_id,
                candidate_item_ids=plan.item_ids,
                outfit_id=plan.outfit_id,
                lead=f"I changed into {plan.display_name or plan.outfit_id}.",
                principal=principal,
            )

        garment = self._resolve_blueprint(
            target,
            candidate_ids=tuple(self._blueprints),
        )
        if garment is None:
            return (
                f"I couldn't resolve '{target}' to one unique outfit or "
                "garment, so I didn't change my wardrobe state."
            )
        return self._add_blueprint(
            intent,
            garment_id=garment.garment.item_id,
            operation_id=operation_id,
            principal=principal,
        )

    def _remove(
        self,
        intent: ClothingActionIntent,
        *,
        operation_id: str,
        principal: PrincipalContext | None,
    ) -> str:
        target = intent.target or ""
        current = self.bundle.authority.current
        blueprint = self._resolve_blueprint(
            target,
            candidate_ids=current.item_ids,
        )
        if blueprint is None:
            return (
                f"I couldn't identify one currently worn garment matching "
                f"'{target}', so I left my wardrobe state unchanged."
            )
        candidate = tuple(
            item_id
            for item_id in current.item_ids
            if item_id != blueprint.garment.item_id
        )
        return self._commit_candidate(
            intent,
            operation_id=operation_id,
            candidate_item_ids=candidate,
            outfit_id=None,
            lead=f"I took off my {blueprint.garment.name}.",
            principal=principal,
        )

    def _add(
        self,
        intent: ClothingActionIntent,
        *,
        operation_id: str,
        principal: PrincipalContext | None,
    ) -> str:
        target = intent.target or ""
        plan = self._resolve_outfit(target)
        if plan is not None:
            return self._commit_candidate(
                intent,
                operation_id=operation_id,
                candidate_item_ids=plan.item_ids,
                outfit_id=plan.outfit_id,
                lead=f"I changed into {plan.display_name or plan.outfit_id}.",
                principal=principal,
            )
        blueprint = self._resolve_blueprint(
            target,
            candidate_ids=tuple(self._blueprints),
        )
        if blueprint is None:
            return (
                f"I couldn't resolve '{target}' to one unique garment, "
                "so I didn't change my wardrobe state."
            )
        return self._add_blueprint(
            intent,
            garment_id=blueprint.garment.item_id,
            operation_id=operation_id,
            principal=principal,
        )

    def _add_blueprint(
        self,
        intent: ClothingActionIntent,
        *,
        garment_id: str,
        operation_id: str,
        principal: PrincipalContext | None,
    ) -> str:
        current = self.bundle.authority.current
        if garment_id in current.item_ids:
            name = self._blueprints[garment_id].garment.name
            return f"I'm already wearing my {name}; no wardrobe change was needed."
        candidate = (*current.item_ids, garment_id)
        name = self._blueprints[garment_id].garment.name
        return self._commit_candidate(
            intent,
            operation_id=operation_id,
            candidate_item_ids=candidate,
            outfit_id=None,
            lead=f"I put on my {name}.",
            principal=principal,
        )

    def _swap(
        self,
        intent: ClothingActionIntent,
        *,
        operation_id: str,
        principal: PrincipalContext | None,
    ) -> str:
        target = intent.target or ""
        current = self.bundle.authority.current
        worn = self._resolve_blueprint(
            target,
            candidate_ids=current.item_ids,
        )
        if worn is None:
            return (
                f"I couldn't identify one currently worn garment matching "
                f"'{target}', so I didn't swap anything."
            )

        current_slots = frozenset(normalize_slots(worn.garment.slots))
        remainder = tuple(
            item_id
            for item_id in current.item_ids
            if item_id != worn.garment.item_id
        )
        candidates = []
        for blueprint in sorted(
            self.bundle.catalog.blueprints,
            key=lambda value: value.garment.item_id,
        ):
            garment = blueprint.garment
            if (
                garment.item_id == worn.garment.item_id
                or blueprint.private_only
                or garment.layer is not worn.garment.layer
                or frozenset(normalize_slots(garment.slots)) != current_slots
            ):
                continue
            trial = (*remainder, garment.item_id)
            try:
                selected = self.bundle.catalog.wardrobe.selection(trial)
            except (WardrobeError, WardrobeConflict):
                continue
            if selected.covered_default and not selected.private_only:
                candidates.append(blueprint)

        if not candidates:
            return (
                f"I don't have a compatible public replacement for my "
                f"{worn.garment.name}, so I kept it on."
            )

        replacement = candidates[0]
        return self._commit_candidate(
            intent,
            operation_id=operation_id,
            candidate_item_ids=(*remainder, replacement.garment.item_id),
            outfit_id=None,
            lead=(
                f"I swapped my {worn.garment.name} for my "
                f"{replacement.garment.name}."
            ),
            principal=principal,
        )

    def _resolve_outfit(self, target: str):
        query = _clean_target(target)
        if not query:
            return None

        bikini = re.search(
            r"\bbikini\s*(?:number\s*)?#?\s*0?([1-6])\b",
            query,
        )
        if bikini is not None:
            wanted = f"swim.bikini.{int(bikini.group(1)):02d}"
            return self.bundle.catalog.preset(wanted)

        aliases: dict[str, list[OutfitPlan]] = {}
        for plan in self.bundle.catalog.presets:
            for alias in (
                _normalize(plan.outfit_id),
                (
                    None
                    if not plan.display_name
                    else _normalize(plan.display_name)
                ),
            ):
                if alias is None:
                    continue
                aliases.setdefault(alias, []).append(plan)

        explicit = {
            "engineer outfit": "engineer.signature",
            "signature engineer outfit": "engineer.signature",
            "signature outfit": "engineer.signature",
            "light engineer outfit": "engineer.light",
            "lounge outfit": "lounge.relaxed",
            "relaxed lounge outfit": "lounge.relaxed",
            "covered fallback outfit": "fallback.covered",
        }
        if query in explicit:
            return self.bundle.catalog.preset(explicit[query])
        matches = aliases.get(query, ())
        return matches[0] if len(matches) == 1 else None

    def _resolve_blueprint(
        self,
        target: str,
        *,
        candidate_ids: tuple[str, ...],
    ):
        query = _clean_target(target)
        if not query:
            return None

        exact = []
        fuzzy = []
        for item_id in candidate_ids:
            blueprint = self._blueprints.get(item_id)
            if blueprint is None:
                continue
            aliases = {
                _normalize(blueprint.garment.item_id),
                _normalize(blueprint.garment.name),
            }
            if query in aliases:
                exact.append(blueprint)
                continue
            searchable = " ".join(sorted(aliases))
            tokens = query.split()
            if tokens and all(token in searchable for token in tokens):
                fuzzy.append(blueprint)

        matches = exact if exact else fuzzy
        if len(matches) != 1:
            return None
        return matches[0]

    def _commit_candidate(
        self,
        intent: ClothingActionIntent,
        *,
        operation_id: str,
        candidate_item_ids: tuple[str, ...],
        outfit_id: str | None,
        lead: str,
        principal: PrincipalContext | None,
    ) -> str:
        current = self.bundle.authority.current

        if not candidate_item_ids:
            return self._decline_private()

        try:
            selected = self.bundle.catalog.wardrobe.selection(
                candidate_item_ids
            )
        except (WardrobeError, WardrobeConflict) as exc:
            return (
                "I didn't change my outfit because that combination is not "
                f"valid in the wardrobe matrix: {exc}."
            )

        needs_private = selected.private_only or not selected.covered_default
        grant = self._private_grant(principal) if needs_private else None
        if needs_private and grant is None:
            return self._decline_private()

        autonomy_context = (
            None
            if self.context_provider is None
            else self.context_provider()
        )
        candidate_plan = (
            None if outfit_id is None else self._plans.get(outfit_id)
        )
        alternative_plan = None
        if (
            autonomy_context is not None
            and autonomy_context.wardrobe_context is not None
        ):
            try:
                proposal = self._planner.suggest(
                    autonomy_context.wardrobe_context,
                    preferences=self._reviewed_preferences,
                )
            except (WardrobeError, WardrobeConflict):
                proposal = None
            proposed_plan = (
                None
                if proposal is None
                else self._plans.get(proposal.outfit_id)
            )
            if (
                proposed_plan is not None
                and (
                    candidate_plan is None
                    or proposed_plan.outfit_id != candidate_plan.outfit_id
                )
            ):
                alternative_plan = proposed_plan

        decision = self.autonomy.decide_contextual(
            intent=intent,
            candidate_item_ids=selected.item_ids,
            private_only=selected.private_only,
            candidate_plan=candidate_plan,
            alternative_plan=alternative_plan,
            context=autonomy_context,
        )
        if (
            decision.accepted
            and candidate_item_ids == current.item_ids
        ):
            return (
                "That is already my current wardrobe state, "
                "so I left it unchanged."
            )

        if not decision.accepted:
            alternative = ""
            if decision.alternative_outfit_id is not None:
                plan = self._plans.get(decision.alternative_outfit_id)
                label = (
                    decision.alternative_outfit_id
                    if plan is None or not plan.display_name
                    else plan.display_name
                )
                alternative = f" I'd rather wear {label} instead."
            return (
                "I'm keeping my current outfit. "
                f"My wardrobe decision was: {decision.reason}."
                + alternative
            )

        dynamic_outfit = outfit_id is None
        if dynamic_outfit:
            suffix = re.sub(r"[^A-Za-z0-9]", "", operation_id)[-40:]
            outfit_id = f"dynamic.chat.{suffix}"
        committed_outfit_id = outfit_id
        if committed_outfit_id is None:
            raise RuntimeError("wardrobe mutation requires an outfit ID")

        def mutate() -> PresentationState:
            if dynamic_outfit:
                self.bundle.authority.register_outfit(
                    outfit_id=committed_outfit_id,
                    item_ids=selected.item_ids,
                    private_only=needs_private,
                )
            self.bundle.authority.propose_outfit(
                operation_id=operation_id,
                expected_revision=current.revision,
                outfit_id=committed_outfit_id,
                reason=f"user_clothing_action:{intent.kind.value}",
                private_only=needs_private,
                daily=False,
            )
            return self.bundle.authority.commit_text(
                operation_id=operation_id,
                renderer_unavailable=True,
                grant=grant,
            )

        state = self.bundle.store.persist_mutation(
            self.bundle.authority,
            mutate,
        )
        if not isinstance(state, PresentationState):
            raise RuntimeError("wardrobe mutation returned invalid state")

        matrix = self.bundle.current_matrix()
        if matrix.item_ids != state.item_ids:
            raise RuntimeError(
                "committed clothing state does not match wardrobe matrix"
            )

        names = tuple(
            self._blueprints[item_id].garment.name
            for item_id in state.item_ids
        )
        return (
            f"{lead} The change is committed. I'm now wearing: "
            + ", ".join(names)
            + "."
        )
