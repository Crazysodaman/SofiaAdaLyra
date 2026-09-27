from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import re

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("timestamp must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


class DevOperation(str, Enum):
    BUILD = "build"
    APPLY = "apply"
    ROLLBACK = "rollback"
    COMMIT = "commit"
    PUSH = "push"


def dev_request_fingerprint(
    operation: DevOperation,
    parameters: dict,
) -> str:
    if not isinstance(operation, DevOperation):
        raise TypeError("operation must be a DevOperation")
    if not isinstance(parameters, dict):
        raise TypeError("parameters must be a dict")
    filtered = {
        key: value
        for key, value in parameters.items()
        if key != "approval_id"
    }
    document = {
        "operation": operation.value,
        "parameters": filtered,
    }
    return sha256(
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class DevApproval:
    approval_id: str
    operation: DevOperation
    proposal_id: str
    request_fingerprint: str
    approved_by: str
    approved_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        for name in ("approval_id", "proposal_id", "approved_by"):
            value = getattr(self, name)
            if not isinstance(value, str) or _ID.fullmatch(value) is None:
                raise ValueError(f"{name} must be a bounded identifier")
        if not isinstance(self.operation, DevOperation):
            raise TypeError("operation must be a DevOperation")
        if not re.fullmatch(r"[0-9a-f]{64}", self.request_fingerprint):
            raise ValueError("request_fingerprint must be lowercase SHA-256")
        if _utc(self.expires_at) <= _utc(self.approved_at):
            raise ValueError("approval expiry must follow approval time")
