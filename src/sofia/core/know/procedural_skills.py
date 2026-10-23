"""Reviewable procedural skill specifications; no executable skill installer.

Stored as evidence-linked *candidates*. Promotion and invocation remain SAFE
capability gateway operations and cannot be self-authorized by LLM prose.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re


_DIGEST = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ProceduralSkillCandidate:
    name: str
    description: str
    revision_sha256: str
    supporting_evidence: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    private_scope: str
    proposer: str

    def __post_init__(self) -> None:
        if any(not isinstance(s,str) or not s.strip() for s in (
            self.name,self.description,self.private_scope,self.proposer
        )):
            raise ValueError("bounded skill identity and owner fields required")
        if len(self.name)>100 or len(self.description)>1000 or len(self.private_scope)>160:
            raise ValueError("skill metadata exceeds limits")
        if _DIGEST.fullmatch(self.revision_sha256) is None:
            raise ValueError("skill source revision must have SHA-256")
        if not self.supporting_evidence or any(not x or len(x)>300 for x in self.supporting_evidence):
            raise ValueError("independently reviewable skill evidence required")
        if any(not isinstance(x,str) or not x.strip() for x in self.required_capabilities):
            raise ValueError("capabilities must be named")
        if len(set(self.required_capabilities)) != len(self.required_capabilities):
            raise ValueError("duplicate skill capability")


@dataclass(frozen=True, slots=True)
class SkillReview:
    candidate_digest: str
    missing_capabilities: tuple[str, ...]
    eligible_for_human_review: bool
    authorized_to_execute: bool = False


def review_procedural_candidate(
    skill: ProceduralSkillCandidate, *, approved_capability_names: frozenset[str],
) -> SkillReview:
    if not isinstance(skill, ProceduralSkillCandidate):
        raise TypeError("typed skill candidate required")
    if not isinstance(approved_capability_names, frozenset):
        raise TypeError("host-provided capability allowlist required")
    missing = tuple(sorted(set(skill.required_capabilities) - approved_capability_names))
    payload = json.dumps({
        "name":skill.name,"revision":skill.revision_sha256,
        "capabilities":skill.required_capabilities,"scope":skill.private_scope,
        "evidence":skill.supporting_evidence,
    },sort_keys=True,separators=(",",":")).encode("utf-8")
    return SkillReview(
        sha256(payload).hexdigest(),missing,not missing,
        authorized_to_execute=False,
    )
