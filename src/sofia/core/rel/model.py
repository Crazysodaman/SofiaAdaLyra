from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class RelationshipContact:
    principal_id: str
    audience_id: str
    evidence_ref: str
    occurred_at: datetime
    display_name: str | None = None

    def __post_init__(self) -> None:
        for name in ("principal_id", "audience_id", "evidence_ref"):
            value=getattr(self,name)
            if not isinstance(value,str) or not value.strip():
                raise ValueError(f"{name} must be nonempty")
        if not isinstance(self.occurred_at,datetime):
            raise TypeError("occurred_at must be a datetime")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        if self.display_name is not None and (
            not isinstance(self.display_name,str) or not self.display_name.strip()
        ):
            raise ValueError("display_name must be None or nonempty")
