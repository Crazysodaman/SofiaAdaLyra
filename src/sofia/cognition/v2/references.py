"""Deterministic entity/reference resolution over structured focus state."""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re

from .contracts import ConversationFocus, FocusReference, ReferenceResolution


_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{1,119}")
_PRONOUNS = frozenset({
    "he", "her", "hers", "him", "his", "it", "its", "she", "that",
    "them", "their", "theirs", "they", "this", "those",
})
_NON_ENTITY = frozenset({
    "and", "are", "can", "could", "do", "does", "give", "how", "i",
    "cpu", "figures", "gpu", "me", "memory", "my", "not", "numbers",
    "please", "ram", "readout", "so", "stats", "the", "these", "well",
    "what", "when", "where", "which", "who", "why", "would", "you", "your",
})


def _normalized(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


@dataclass(frozen=True, slots=True)
class EntityCandidate:
    subject_id: str
    kind: str
    aliases: tuple[str, ...]
    evidence_refs: tuple[str, ...] = ()


class ConversationReferenceResolver:
    """Resolve exact aliases first, then bounded typo/pronoun continuity."""

    def resolve(
        self,
        content: str,
        *,
        focus: ConversationFocus,
        candidates: tuple[EntityCandidate, ...] = (),
        turn_id: str,
    ) -> tuple[ReferenceResolution, FocusReference | None]:
        if not isinstance(content, str) or not content.strip():
            raise ValueError("content must be nonempty")
        all_candidates = self._merge_candidates(focus, candidates)
        tokens = tuple(_TOKEN.finditer(content))
        normalized_tokens = tuple(
            _normalized(match.group(0)) for match in tokens
        )

        local_tokens = {_normalized(match.group(0)) for match in tokens}
        if (
            "localhost" in local_tokens
            or "local" in local_tokens
            or (
                "this" in local_tokens
                and local_tokens & {"computer", "host", "machine", "system"}
            )
            or (
                "my" in local_tokens
                and local_tokens & {"computer", "host", "machine", "system"}
            )
        ):
            reference = FocusReference(
                reference_id="reference:runtime-local-host",
                subject_id="runtime:local-host",
                kind="local-host",
                source_turn_id=turn_id,
                confidence=1.0,
                aliases=("local host",),
            )
            return (
                ReferenceResolution(
                    subject_id=reference.subject_id,
                    reference_id=reference.reference_id,
                    source="explicit-local",
                    confidence=1.0,
                ),
                reference,
            )

        exact = []
        for candidate in all_candidates:
            for alias in candidate.aliases:
                alias_tokens = tuple(
                    _normalized(match.group(0))
                    for match in _TOKEN.finditer(alias)
                )
                value = _normalized(alias)
                if value and self._contains_tokens(normalized_tokens, alias_tokens):
                    exact.append((len(value), candidate, alias))
        exact.sort(key=lambda item: item[0], reverse=True)
        if exact:
            selected, corrected = self._correction(content, exact)
            if selected is None:
                selected = exact[0][1]
            reference = self._reference(selected, turn_id, 1.0)
            return (
                ReferenceResolution(
                    subject_id=reference.subject_id,
                    reference_id=reference.reference_id,
                    source=("correction" if corrected is not None else "explicit"),
                    confidence=1.0,
                    corrected_subject_id=corrected,
                ),
                reference,
            )

        for match in tokens:
            token = match.group(0)
            normalized = _normalized(token)
            if len(normalized) < 4 or normalized in _NON_ENTITY:
                continue
            best: tuple[float, EntityCandidate] | None = None
            for candidate in all_candidates:
                for alias in candidate.aliases:
                    score = SequenceMatcher(
                        None, normalized, _normalized(alias)
                    ).ratio()
                    if score >= 0.82 and (best is None or score > best[0]):
                        best = (score, candidate)
            if best is not None:
                reference = self._reference(best[1], turn_id, best[0])
                return (
                    ReferenceResolution(
                        subject_id=reference.subject_id,
                        reference_id=reference.reference_id,
                        source="fuzzy-alias",
                        confidence=round(best[0], 3),
                    ),
                    reference,
                )

        # A capitalized non-initial token is a bounded new named-entity
        # candidate. It remains a discourse reference, never existence proof.
        for index, match in enumerate(tokens):
            token = match.group(0)
            if (
                token[0].isupper()
                and _normalized(token) not in _NON_ENTITY
                and (index > 0 or len(tokens) == 1)
            ):
                reference = FocusReference(
                    reference_id=f"reference:entity-{_normalized(token)}",
                    subject_id=f"entity:{_normalized(token)}",
                    kind="named-entity",
                    source_turn_id=turn_id,
                    confidence=0.75,
                    aliases=(token,),
                )
                return (
                    ReferenceResolution(
                        subject_id=reference.subject_id,
                        reference_id=reference.reference_id,
                        source="named-entity-candidate",
                        confidence=0.75,
                    ),
                    reference,
                )

        if focus.primary_reference is not None and (
            any(_normalized(match.group(0)) in _PRONOUNS for match in tokens)
            or len(tokens) <= 8
        ):
            reference = focus.primary_reference
            return (
                ReferenceResolution(
                    subject_id=reference.subject_id,
                    reference_id=reference.reference_id,
                    source="focused-reference",
                    confidence=max(0.70, reference.confidence * 0.95),
                ),
                reference,
            )

        return ReferenceResolution(None, None, "unresolved", 0.0), None

    @staticmethod
    def _candidate_for_reference(reference: FocusReference) -> EntityCandidate:
        return EntityCandidate(
            subject_id=reference.subject_id,
            kind=reference.kind,
            aliases=reference.aliases,
            evidence_refs=reference.evidence_refs,
        )

    def _merge_candidates(
        self,
        focus: ConversationFocus,
        candidates: tuple[EntityCandidate, ...],
    ) -> tuple[EntityCandidate, ...]:
        merged = {
            item.subject_id: self._candidate_for_reference(item)
            for item in focus.references
        }
        for candidate in candidates:
            merged[candidate.subject_id] = candidate
        return tuple(merged[key] for key in sorted(merged))

    @staticmethod
    def _reference(
        candidate: EntityCandidate,
        turn_id: str,
        confidence: float,
    ) -> FocusReference:
        safe_subject = re.sub(r"[^A-Za-z0-9_.-]", "-", candidate.subject_id)
        return FocusReference(
            reference_id=f"reference:{safe_subject}",
            subject_id=candidate.subject_id,
            kind=candidate.kind,
            source_turn_id=turn_id,
            confidence=round(confidence, 3),
            aliases=candidate.aliases,
            evidence_refs=candidate.evidence_refs,
        )

    @staticmethod
    def _contains_tokens(content: tuple[str, ...], alias: tuple[str, ...]) -> bool:
        if not alias or len(alias) > len(content):
            return False
        return any(
            content[index:index + len(alias)] == alias
            for index in range(len(content) - len(alias) + 1)
        )

    @staticmethod
    def _correction(content, exact):
        """Return the positively named subject and any explicitly negated one."""
        if "not" not in content.casefold():
            return exact[0][1], None
        negated = []
        positive = []
        for _, candidate, alias in exact:
            alias_pattern = r"\s+".join(
                re.escape(part) for part in alias.split()
            )
            pattern = rf"\bnot\s+(?:the\s+)?{alias_pattern}\b"
            if re.search(pattern, content, flags=re.IGNORECASE):
                negated.append(candidate)
            else:
                positive.append(candidate)
        corrected = None if not negated else negated[0].subject_id
        selected = None if not positive else positive[0]
        return selected, corrected
