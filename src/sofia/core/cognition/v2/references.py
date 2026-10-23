"""Deterministic multi-entity reference resolution over structured focus."""
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
    """Resolve every explicit entity, while retaining one primary discourse focus."""

    def resolve(
        self,
        content: str,
        *,
        focus: ConversationFocus,
        candidates: tuple[EntityCandidate, ...] = (),
        turn_id: str,
    ) -> tuple[ReferenceResolution, FocusReference | None]:
        resolution, references = self.resolve_many(
            content, focus=focus, candidates=candidates, turn_id=turn_id,
        )
        return resolution, (None if not references else references[0])

    def resolve_many(
        self,
        content: str,
        *,
        focus: ConversationFocus,
        candidates: tuple[EntityCandidate, ...] = (),
        turn_id: str,
    ) -> tuple[ReferenceResolution, tuple[FocusReference, ...]]:
        if not isinstance(content, str) or not content.strip():
            raise ValueError("content must be nonempty")
        all_candidates = self._merge_candidates(focus, candidates)
        matches = tuple(_TOKEN.finditer(content))
        normalized_tokens = tuple(_normalized(item.group(0)) for item in matches)
        local_tokens = set(normalized_tokens)
        explicit_local = (
            "localhost" in local_tokens
            or "local" in local_tokens
            or (
                bool(local_tokens & {"this", "my"})
                and bool(local_tokens & {"computer", "host", "machine", "system"})
            )
        )
        resolved: list[FocusReference] = []
        if explicit_local:
            resolved.append(FocusReference(
                reference_id="reference:runtime-local-host",
                subject_id="runtime:local-host",
                kind="local-host",
                source_turn_id=turn_id,
                confidence=1.0,
                aliases=("local host",),
            ))

        exact: list[tuple[int, int, EntityCandidate, str]] = []
        for candidate in all_candidates:
            for alias in candidate.aliases:
                alias_tokens = tuple(
                    _normalized(item.group(0)) for item in _TOKEN.finditer(alias)
                )
                if not alias_tokens:
                    continue
                for index in self._matching_indices(normalized_tokens, alias_tokens):
                    exact.append((index, -len(_normalized(alias)), candidate, alias))
        exact.sort(key=lambda item: (item[0], item[1], item[2].subject_id))
        corrected_subject = None
        seen = {item.subject_id for item in resolved}
        for _, _, candidate, alias in exact:
            if candidate.subject_id in seen:
                continue
            alias_pattern = r"\s+".join(re.escape(part) for part in alias.split())
            if re.search(
                rf"\bnot\s+(?:the\s+)?{alias_pattern}\b",
                content,
                flags=re.IGNORECASE,
            ):
                corrected_subject = corrected_subject or candidate.subject_id
                continue
            resolved.append(self._reference(candidate, turn_id, 1.0))
            seen.add(candidate.subject_id)

        if resolved:
            primary = resolved[0]
            return ReferenceResolution(
                primary.subject_id,
                primary.reference_id,
                "correction" if corrected_subject is not None else (
                    "explicit-local" if explicit_local and len(resolved) == 1
                    else "explicit-multiple" if len(resolved) > 1
                    else "explicit"
                ),
                1.0,
                corrected_subject_id=corrected_subject,
            ), tuple(resolved)

        fuzzy = self._fuzzy(matches, all_candidates)
        if fuzzy is not None:
            score, candidate = fuzzy
            reference = self._reference(candidate, turn_id, score)
            return ReferenceResolution(
                reference.subject_id, reference.reference_id,
                "fuzzy-alias", round(score, 3),
            ), (reference,)

        for index, match in enumerate(matches):
            token = match.group(0)
            if (
                token[0].isupper()
                and _normalized(token) not in _NON_ENTITY
                and (index > 0 or len(matches) == 1)
            ):
                reference = FocusReference(
                    reference_id=f"reference:entity-{_normalized(token)}",
                    subject_id=f"entity:{_normalized(token)}",
                    kind="named-entity",
                    source_turn_id=turn_id,
                    confidence=0.75,
                    aliases=(token,),
                )
                return ReferenceResolution(
                    reference.subject_id, reference.reference_id,
                    "named-entity-candidate", 0.75,
                ), (reference,)

        if focus.primary_reference is not None and (
            any(_normalized(item.group(0)) in _PRONOUNS for item in matches)
            or len(matches) <= 8
        ):
            reference = focus.primary_reference
            return ReferenceResolution(
                reference.subject_id, reference.reference_id,
                "focused-reference", max(0.70, reference.confidence * 0.95),
            ), (reference,)
        return ReferenceResolution(None, None, "unresolved", 0.0), ()

    @staticmethod
    def _fuzzy(matches, candidates):
        best: tuple[float, EntityCandidate] | None = None
        for match in matches:
            token = match.group(0)
            normalized = _normalized(token)
            if len(normalized) < 4 or normalized in _NON_ENTITY:
                continue
            for candidate in candidates:
                for alias in candidate.aliases:
                    score = SequenceMatcher(None, normalized, _normalized(alias)).ratio()
                    if score >= 0.82 and (best is None or score > best[0]):
                        best = (score, candidate)
        return best

    @staticmethod
    def _matching_indices(content: tuple[str, ...], alias: tuple[str, ...]):
        if not alias or len(alias) > len(content):
            return ()
        return tuple(
            index for index in range(len(content) - len(alias) + 1)
            if content[index:index + len(alias)] == alias
        )

    @staticmethod
    def _candidate_for_reference(reference: FocusReference) -> EntityCandidate:
        return EntityCandidate(
            reference.subject_id, reference.kind, reference.aliases,
            reference.evidence_refs,
        )

    def _merge_candidates(self, focus, candidates):
        merged = {
            item.subject_id: self._candidate_for_reference(item)
            for item in focus.references
        }
        for candidate in candidates:
            merged[candidate.subject_id] = candidate
        return tuple(merged[key] for key in sorted(merged))

    @staticmethod
    def _reference(candidate, turn_id, confidence):
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
