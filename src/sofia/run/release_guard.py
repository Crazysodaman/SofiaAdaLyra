"""Release-level rollback decision after repeated readiness failure."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReleaseRecoveryAction(str, Enum):
    RETRY_PROCESS = "retry_process"
    ROLLBACK_RELEASE = "rollback_release"
    QUARANTINE = "quarantine"


@dataclass(frozen=True, slots=True)
class ReleaseFailurePolicy:
    process_retry_limit: int = 3
    rollback_available: bool = True

    def __post_init__(self) -> None:
        if type(self.process_retry_limit) is not int or self.process_retry_limit < 0:
            raise ValueError("process_retry_limit must be nonnegative")
        if not isinstance(self.rollback_available, bool):
            raise TypeError("rollback_available must be boolean")


def recovery_action(
    *,
    consecutive_readiness_failures: int,
    policy: ReleaseFailurePolicy,
) -> ReleaseRecoveryAction:
    if (
        type(consecutive_readiness_failures) is not int
        or consecutive_readiness_failures < 0
    ):
        raise ValueError("consecutive_readiness_failures must be nonnegative")
    if not isinstance(policy, ReleaseFailurePolicy):
        raise TypeError("ReleaseFailurePolicy required")
    if consecutive_readiness_failures <= policy.process_retry_limit:
        return ReleaseRecoveryAction.RETRY_PROCESS
    if policy.rollback_available:
        return ReleaseRecoveryAction.ROLLBACK_RELEASE
    return ReleaseRecoveryAction.QUARANTINE
