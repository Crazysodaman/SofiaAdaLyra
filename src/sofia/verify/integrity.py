"""Domain-level integrity checks beyond database structural integrity."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import re

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,191}$")


class IntegrityStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class IntegrityFinding:
    check_id: str
    status: IntegrityStatus
    detail: str

    def __post_init__(self) -> None:
        if not isinstance(self.check_id, str) or _ID.fullmatch(
            self.check_id
        ) is None:
            raise ValueError("check_id must be a bounded identifier")
        if not isinstance(self.status, IntegrityStatus):
            raise TypeError("status must be IntegrityStatus")
        if not isinstance(self.detail, str):
            raise TypeError("detail must be text")


class SemanticIntegrityCheck(ABC):
    @property
    @abstractmethod
    def check_id(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def run(self) -> IntegrityFinding:
        raise NotImplementedError


def run_semantic_checks(
    checks: tuple[SemanticIntegrityCheck, ...],
) -> tuple[IntegrityFinding, ...]:
    if not isinstance(checks, tuple):
        raise TypeError("checks must be a tuple")
    findings: list[IntegrityFinding] = []
    seen: set[str] = set()
    for check in checks:
        if not isinstance(check, SemanticIntegrityCheck):
            raise TypeError("checks must contain SemanticIntegrityCheck")
        finding = check.run()
        if not isinstance(finding, IntegrityFinding):
            raise TypeError("semantic check must return IntegrityFinding")
        if finding.check_id != check.check_id:
            raise ValueError("semantic check returned mismatched check_id")
        if finding.check_id in seen:
            raise ValueError("duplicate semantic integrity check_id")
        seen.add(finding.check_id)
        findings.append(finding)
    return tuple(findings)
