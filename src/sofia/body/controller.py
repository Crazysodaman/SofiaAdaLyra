from __future__ import annotations

from abc import ABC,abstractmethod
from dataclasses import dataclass
from datetime import datetime,timezone

from sofia.body.model import MotionKind,MotionRequest
from sofia.body.safety import EmergencyStopMonitor


class BodyExecutionError(RuntimeError):
    pass


class ServoBackend(ABC):
    @abstractmethod
    def execute(self,request:MotionRequest)->None:
        raise NotImplementedError

    @abstractmethod
    def stop_all(self)->None:
        raise NotImplementedError


@dataclass(frozen=True,slots=True)
class MotionApproval:
    approval_id:str
    request_id:str
    approved_by:str
    expires_at:datetime

    def __post_init__(self)->None:
        for name in ("approval_id","request_id","approved_by"):
            value=getattr(self,name)
            if not isinstance(value,str) or not value.strip():
                raise ValueError(f"{name} must be nonempty")
        if not isinstance(self.expires_at,datetime):
            raise TypeError("expires_at must be a datetime")
        if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
            raise ValueError("expires_at must be timezone-aware")


class BodyController:
    """Physical BODY boundary with independent E-stop gating."""

    def __init__(
        self,
        *,
        backend:ServoBackend,
        emergency_stop:EmergencyStopMonitor,
        max_estop_age_seconds:float=1.0,
    )->None:
        if not isinstance(backend,ServoBackend):
            raise TypeError("backend must be ServoBackend")
        if not isinstance(emergency_stop,EmergencyStopMonitor):
            raise TypeError("emergency_stop must be EmergencyStopMonitor")
        if not isinstance(max_estop_age_seconds,(int,float)) or max_estop_age_seconds<=0:
            raise ValueError("max_estop_age_seconds must be positive")
        self.backend=backend
        self.emergency_stop=emergency_stop
        self.max_estop_age_seconds=float(max_estop_age_seconds)

    def execute(
        self,
        request:MotionRequest,
        approval:MotionApproval,
        *,
        now:datetime|None=None,
    )->None:
        if not isinstance(request,MotionRequest):
            raise TypeError("request must be MotionRequest")
        if not isinstance(approval,MotionApproval):
            raise TypeError("approval must be MotionApproval")
        moment=now or datetime.now(timezone.utc)
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        if approval.approved_by!="Sparks":
            raise PermissionError("physical motion approval must come from Sparks")
        if approval.request_id!=request.request_id:
            raise PermissionError("motion approval belongs to another request")
        if moment>=approval.expires_at:
            raise PermissionError("motion approval expired")

        evidence=self.emergency_stop.observe()
        age=(moment-evidence.observed_at).total_seconds()
        if age<0 or age>self.max_estop_age_seconds:
            raise BodyExecutionError("hardware E-stop evidence is stale or clock-uncertain")
        if not evidence.hardware_verified:
            raise BodyExecutionError("independent hardware E-stop is not verified")
        if evidence.asserted:
            self.backend.stop_all()
            raise BodyExecutionError("hardware E-stop is asserted")

        if request.kind is MotionKind.STOP:
            self.backend.stop_all()
            return
        self.backend.execute(request)
