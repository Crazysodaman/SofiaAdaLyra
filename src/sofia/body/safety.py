from __future__ import annotations

from abc import ABC,abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True,slots=True)
class EmergencyStopEvidence:
    asserted:bool
    hardware_verified:bool
    observed_at:datetime
    source:str

    def __post_init__(self)->None:
        if not isinstance(self.asserted,bool):
            raise TypeError("asserted must be boolean")
        if not isinstance(self.hardware_verified,bool):
            raise TypeError("hardware_verified must be boolean")
        if not isinstance(self.observed_at,datetime):
            raise TypeError("observed_at must be a datetime")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if not isinstance(self.source,str) or not self.source.strip():
            raise ValueError("source must be nonempty")


class EmergencyStopMonitor(ABC):
    """Independent hardware E-stop observation boundary."""

    @abstractmethod
    def observe(self)->EmergencyStopEvidence:
        raise NotImplementedError
