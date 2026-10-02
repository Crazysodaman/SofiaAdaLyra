"""Authoritative natural-language AVATAR clothing actions.

The parser recognizes a deliberately small, reviewable set of clothing commands.
The service never treats model prose as proof of a change. It validates a
candidate wardrobe selection, passes it through an autonomy policy, commits the
PresentationAuthority, persists canonical state, verifies the persisted revision,
and only then returns text describing the committed result.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import re
from threading import RLock

from .presentation import PresentationState
from .runtime_state import PresentationRuntimeBundle
from .wardrobe import (
    WardrobeConflict,
    WardrobeError,
    normalize_slots,
)


def _normalize(value: str) -> str:
    value = value.casefold().replace("’", "'")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _clean_target(value: str) -> str:
    text = _normalize(value)
    text = re.sub(r"^(?:the|a|an|my|your|ur)\s+", "", text)
    text = re.sub(r"\s+(?:please)$", "", text)
    return text.strip()


class ClothingActionKind(str, Enum):
    WEAR = "wear"
    ADD = "add"
    REMOVE = "remove"
    SWAP = "swap"
    UNDRESS = "undress"


@dataclass(frozen=True, slots=True)
class ClothingActionIntent:
    kind: ClothingActionKind
    target: str | None = None
    hypothetical: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ClothingActionKind):
            raise TypeError("kind must be ClothingActionKind")
        if self.target is not None and (
            not isinstance(self.target, str) or not self.target.strip()
        ):
            raise ValueError("target must be None or nonempty")
        if type(self.hypothetical) is not bool:
            raise TypeError("hypothetical must be bool")


@dataclass(frozen=True, slots=True)
class WardrobeAutonomyDecision:
    accepted: bool
    reason: str

    def __post_init__(self) -> None:
        if type(self.accepted) is not bool:
            raise TypeError("accepted must be bool")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("autonomy reason must be nonempty")


class WardrobeAutonomyPolicy:
    """Replaceable host policy for one requested wardrobe state transition.

    The default policy accepts valid public clothing changes and refuses
    restricted/private transitions. A richer policy can later incorporate
    trusted preference/emotion/activity evidence without giving user prose or
    an LLM direct state authority.
    """

    def decide(
        self,
        *,
        intent: ClothingActionIntent,
        candidate_item_ids: tuple[str, ...],
        private_only: bool,
    ) -> WardrobeAutonomyDecision:
        if not isinstance(intent, ClothingActionIntent):
            raise TypeError("intent must be ClothingActionIntent")
        if not isinstance(candidate_item_ids, tuple):
            raise TypeError("candidate_item_ids must be a tuple")
        if type(private_only) is not bool:
            raise TypeError("private_only must be bool")
        if private_only or intent.kind is ClothingActionKind.UNDRESS:
            return WardrobeAutonomyDecision(
                False,
                "private presentation requires separate verified authority",
            )
        return WardrobeAutonomyDecision(
            True,
            "valid public wardrobe change accepted by host autonomy policy",
        )


class ClothingActionParser:
    _FOLLOW = re.compile(
        r"^\s*(?:do\s+it|go\s+ahead|yes[, ]+do\s+it|"
        r"please\s+do\s+it|ok(?:ay)?[, ]+do\s+it)\s*[?.!]*\s*$",
        re.IGNORECASE,
    )
    _IF_ASKED = re.compile(
        r"^\s*if\s+i\s+ask(?:ed)?\s+you\s+to\s+(.+?)"
        r"\s*,?\s*(?:would|will)\s+you\s*[?.!]*\s*$",
        re.IGNORECASE,
    )
    _QUESTION = re.compile(
        r"^\s*(?:would|will|can|could)\s+you\s+(.+?)\s*[?.!]*\s*$",
        re.IGNORECASE,
    )
    _UNDRESS = re.compile(
        r"^\s*(?:please\s+)?(?:undress|get\s+undressed|"
        r"take\s+off\s+(?:all|everything|all\s+your\s+clothes|"
        r"your\s+clothes))\s*[?.!]*\s*$",
        re.IGNORECASE,
    )
    _REMOVE_A = re.compile(
        r"^\s*(?:please\s+)?(?:take\s+off|remove)\s+"
        r"(?:your|ur|the)?\s*(.+?)\s*[?.!]*\s*$",
        re.IGNORECASE,
    )
    _REMOVE_B = re.compile(
        r"^\s*(?:please\s+)?take\s+(?:your|ur|the)?\s*(.+?)\s+off"
        r"\s*[?.!]*\s*$",
        re.IGNORECASE,
    )
    _SWAP = re.compile(
        r"^\s*(?:please\s+)?(?:swap|switch|change)\s+"
        r"(?:your|ur|the)?\s*(?!outfit\b)(.+?)\s*[?.!]*\s*$",
        re.IGNORECASE,
    )
    _CHANGE_OUTFIT = re.compile(
        r"^\s*(?:please\s+)?change\s+(?:your\s+)?outfit\s+"
        r"(?:to|into)\s+(.+?)\s*[?.!]*\s*$",
        re.IGNORECASE,
    )
    _WEAR = re.compile(
        r"^\s*(?:please\s+)?(?:change\s+into|wear)\s+"
        r"(?:your|ur|the)?\s*(.+?)\s*[?.!]*\s*$",
        re.IGNORECASE,
    )
    _ADD = re.compile(
        r"^\s*(?:please\s+)?put\s+on\s+"
        r"(?:your|ur|the)?\s*(.+?)\s*[?.!]*\s*$",
        re.IGNORECASE,
    )

    def parse(self, content: str) -> ClothingActionIntent | None:
        if not isinstance(content, str):
            raise TypeError("clothing action content must be a string")
        text = content.strip()
        if not text:
            return None

        hypothetical = self._IF_ASKED.fullmatch(text)
        if hypothetical is not None:
            inner = self._parse_direct(hypothetical.group(1))
            return (
                None
                if inner is None
                else replace(inner, hypothetical=True)
            )

        question = self._QUESTION.fullmatch(text)
        if question is not None:
            inner = self._parse_direct(question.group(1))
            return (
                None
                if inner is None
                else replace(inner, hypothetical=True)
            )

        return self._parse_direct(text)

    def is_followup(self, content: str) -> bool:
        if not isinstance(content, str):
            return False
        return self._FOLLOW.fullmatch(content.strip()) is not None

    def _parse_direct(self, text: str) -> ClothingActionIntent | None:
        if self._UNDRESS.fullmatch(text) is not None:
            return ClothingActionIntent(ClothingActionKind.UNDRESS)

        for pattern in (self._REMOVE_A, self._REMOVE_B):
            match = pattern.fullmatch(text)
            if match is not None:
                return ClothingActionIntent(
                    ClothingActionKind.REMOVE,
                    _clean_target(match.group(1)),
                )

        match = self._CHANGE_OUTFIT.fullmatch(text)
        if match is not None:
            return ClothingActionIntent(
                ClothingActionKind.WEAR,
                _clean_target(match.group(1)),
            )

        match = self._WEAR.fullmatch(text)
        if match is not None:
            return ClothingActionIntent(
                ClothingActionKind.WEAR,
                _clean_target(match.group(1)),
            )

        match = self._ADD.fullmatch(text)
        if match is not None:
            return ClothingActionIntent(
                ClothingActionKind.ADD,
                _clean_target(match.group(1)),
            )

        match = self._SWAP.fullmatch(text)
        if match is not None:
            return ClothingActionIntent(
                ClothingActionKind.SWAP,
                _clean_target(match.group(1)),
            )

        return None


class ClothingActionService:
    """Parse, decide, commit, persist, verify, then describe clothing changes."""

    def __init__(
        self,
        bundle: PresentationRuntimeBundle,
        *,
        autonomy: WardrobeAutonomyPolicy | None = None,
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
        self.bundle = bundle
        self.autonomy = autonomy or WardrobeAutonomyPolicy()
        self.parser = ClothingActionParser()
        self._lock = RLock()
        self._blueprints = {
            blueprint.garment.item_id: blueprint
            for blueprint in bundle.catalog.blueprints
        }
        self._base_outfits = {
            plan.outfit_id: plan.item_ids
            for plan in bundle.catalog.presets
        }

    def handle(
        self,
        *,
        content: str,
        previous_user_content: str | None,
        operation_id: str,
    ) -> str | None:
        """Serialize one wardrobe action across all conversation channels."""
        with self._lock:
            return self._handle_locked(
                content=content,
                previous_user_content=previous_user_content,
                operation_id=operation_id,
            )

    def _handle_locked(
        self,
        *,
        content: str,
        previous_user_content: str | None,
        operation_id: str,
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
            return self._decline_private()

        if intent.kind is ClothingActionKind.WEAR:
            return self._wear(
                intent,
                operation_id=operation_id,
            )
        if intent.kind is ClothingActionKind.REMOVE:
            return self._remove(
                intent,
                operation_id=operation_id,
            )
        if intent.kind is ClothingActionKind.ADD:
            return self._add(
                intent,
                operation_id=operation_id,
            )
        if intent.kind is ClothingActionKind.SWAP:
            return self._swap(
                intent,
                operation_id=operation_id,
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
            "wardrobe change; I decide at execution time and only claim it "
            "after the wardrobe matrix validates and the new presentation is "
            "committed."
        )

    def _decline_private(self) -> str:
        return (
            "I'm keeping my current outfit. A nude/private presentation "
            "requires a separate verified private-presentation grant, and this "
            "runtime does not currently have one. My wardrobe state is unchanged."
        )

    def _wear(
        self,
        intent: ClothingActionIntent,
        *,
        operation_id: str,
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
        )

    def _remove(
        self,
        intent: ClothingActionIntent,
        *,
        operation_id: str,
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
        )

    def _add(
        self,
        intent: ClothingActionIntent,
        *,
        operation_id: str,
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
        )

    def _add_blueprint(
        self,
        intent: ClothingActionIntent,
        *,
        garment_id: str,
        operation_id: str,
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
        )

    def _swap(
        self,
        intent: ClothingActionIntent,
        *,
        operation_id: str,
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

        aliases: dict[str, object] = {}
        for plan in self.bundle.catalog.presets:
            aliases[_normalize(plan.outfit_id)] = plan
            if plan.display_name:
                aliases[_normalize(plan.display_name)] = plan

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
        return aliases.get(query)

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
    ) -> str:
        current = self.bundle.authority.current
        if candidate_item_ids == current.item_ids:
            return "That is already my current wardrobe state, so I left it unchanged."

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

        if selected.private_only or not selected.covered_default:
            return self._decline_private()

        decision = self.autonomy.decide(
            intent=intent,
            candidate_item_ids=selected.item_ids,
            private_only=selected.private_only,
        )
        if not decision.accepted:
            return (
                "I'm keeping my current outfit. "
                f"My wardrobe decision was: {decision.reason}."
            )

        if outfit_id is None:
            suffix = re.sub(r"[^A-Za-z0-9]", "", operation_id)[-40:]
            outfit_id = f"dynamic.chat.{suffix}"
            self.bundle.authority.register_outfit(
                outfit_id=outfit_id,
                item_ids=selected.item_ids,
                private_only=False,
            )

        self.bundle.authority.propose_outfit(
            operation_id=operation_id,
            expected_revision=current.revision,
            outfit_id=outfit_id,
            reason=f"user_clothing_action:{intent.kind.value}",
            private_only=False,
            daily=False,
        )
        state = self.bundle.authority.commit_text(
            operation_id=operation_id,
            renderer_unavailable=True,
        )
        self.bundle.store.save(self.bundle.authority)
        self._verify_persisted(state)

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

    def _verify_persisted(self, state: PresentationState) -> None:
        restored = self.bundle.store.load(
            self.bundle.catalog.wardrobe,
            outfits=self._base_outfits,
        )
        persisted = restored.current
        if (
            persisted.revision != state.revision
            or persisted.outfit_id != state.outfit_id
            or persisted.item_ids != state.item_ids
        ):
            raise RuntimeError(
                "wardrobe state commit could not be verified in canonical storage"
            )
