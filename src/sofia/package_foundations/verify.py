"""PKG-VERIFY: test-evidence metadata only; does not execute or attest tests."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re


class Environment(str, Enum):
    FIXTURE = 'fixture'
    WINDOWS = 'windows'
    LIVE_MODEL = 'live_model'
    HARDWARE = 'hardware'


class Outcome(str, Enum):
    PASSED = 'passed'
    FAILED = 'failed'
    NOT_RUN = 'not_run'


@dataclass(frozen=True)
class VerificationRecord:
    commit_sha: str
    environment: Environment
    outcome: Outcome
    evidence_ref: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.commit_sha, str) or not re.fullmatch(
            r'[a-fA-F0-9]{40}', self.commit_sha
        ):
            raise ValueError('Exact full commit SHA is required.')
        if not isinstance(self.environment, Environment) or not isinstance(self.outcome, Outcome):
            raise TypeError('Explicit environment and outcome are required.')
        if self.evidence_ref is not None and (
            not isinstance(self.evidence_ref, str) or not self.evidence_ref.strip()
        ):
            raise ValueError('Evidence reference must be nonempty if supplied.')

    @property
    def needs_external_validation(self) -> bool:
        """All reported passes need independent evidence; metadata is not attestation."""
        return self.outcome is Outcome.PASSED
