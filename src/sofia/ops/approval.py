"""Exact, durable-shaped operator approval evidence for final fleet removal."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class FleetRemovalApproval:
    approval_id:str; host_id:str; proposal_revision:str; approved_by:str; approved_at:datetime
    def __post_init__(self):
        if not all((self.approval_id.strip(),self.host_id.strip(),self.proposal_revision.strip(),self.approved_by.strip())):
            raise ValueError("complete removal approval evidence required")
        if self.approved_at.tzinfo is None: raise ValueError("approved_at must be timezone-aware")
        if self.approved_by!="Sparks": raise PermissionError("final fleet removal approval must come from Sparks")
