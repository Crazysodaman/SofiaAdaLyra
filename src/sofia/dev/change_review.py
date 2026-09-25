"""Evidence-linked engineering proposal screening.

This module classifies proposed paths. It never grants execution authority.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import re

_SHA = re.compile(r"[0-9a-f]{40}\Z")

class ReviewState(str, Enum):
    BLOCKED_PROTECTED = "blocked_protected"
    INVALID_PATH = "invalid_path"
    REQUIRES_REVIEW = "requires_review"

@dataclass(frozen=True)
class ChangeProposal:
    proposal_id: str
    base_sha: str
    affected_paths: tuple[str, ...]
    source_evidence_ids: tuple[str, ...]
    description: str
    test_plan: str
    rollback_plan: str

    def __post_init__(self) -> None:
        if not self.proposal_id.strip(): raise ValueError("proposal_id required")
        if _SHA.fullmatch(self.base_sha) is None: raise ValueError("base_sha must be a pinned lowercase 40-character SHA")
        if not self.affected_paths or len(set(self.affected_paths)) != len(self.affected_paths): raise ValueError("affected_paths must be nonempty and unique")
        if not self.source_evidence_ids: raise ValueError("source evidence references required")
        for name in ("description", "test_plan", "rollback_plan"):
            if not getattr(self, name).strip(): raise ValueError(f"{name} required")

@dataclass(frozen=True)
class ReviewFinding:
    state: ReviewState
    affected_path: str
    reason: str

_PROTECTED_COMPONENTS=frozenset({".git",".env","state","secret","secrets","credentials","backups","backup"})
_PROTECTED_ROOTS=(("src","sofia","constitution"),("src","sofia","identity"),("src","sofia","data"))
_PROTECTED_SUFFIXES=(".db",".sqlite",".sqlite3",".pem",".key")

def inspect(proposal: ChangeProposal) -> tuple[ReviewFinding, ...]:
    if not isinstance(proposal, ChangeProposal): raise TypeError("ChangeProposal required")
    out=[]
    for path in proposal.affected_paths:
        if (path.startswith("/") or "\\" in path or ":" in path or "\x00" in path or "//" in path or path.endswith("/") or any(x in ("",".","..") for x in path.split("/"))):
            out.append(ReviewFinding(ReviewState.INVALID_PATH,path,"untrusted relative path")); continue
        parts=tuple(x.casefold() for x in path.split("/"))
        if (any(x in _PROTECTED_COMPONENTS or x.startswith(".env.") for x in parts) or any(parts[:len(root)]==root for root in _PROTECTED_ROOTS) or parts[-1].endswith(_PROTECTED_SUFFIXES)):
            out.append(ReviewFinding(ReviewState.BLOCKED_PROTECTED,path,"protected state, identity, data or credentials")); continue
        out.append(ReviewFinding(ReviewState.REQUIRES_REVIEW,path,"independent authorization, diff review, tests and rollback required"))
    return tuple(out)
