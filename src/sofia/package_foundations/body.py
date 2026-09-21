"""PKG-BODY: offline motion request validation; NEVER drives SSC-32 or a servo."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MotionProposal:
    joint_id: str
    pulse_us: int
    calibrated_min_us: int
    calibrated_max_us: int
    authorization_verified: bool = False
    hardware_ready_verified: bool = False
    emergency_stop_active: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.joint_id, str) or not self.joint_id.strip():
            raise ValueError('A known joint ID is required.')
        if any(type(value) is not int for value in (
            self.pulse_us, self.calibrated_min_us, self.calibrated_max_us
        )):
            raise TypeError('Pulse and calibrated bounds must be integers.')
        if not self.calibrated_min_us < self.calibrated_max_us:
            raise ValueError('A nonempty verified calibration interval is required.')
        for name in ('authorization_verified', 'hardware_ready_verified', 'emergency_stop_active'):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f'{name} must be boolean.')

    @property
    def eligible_for_independent_hardware_gate(self) -> bool:
        """Caller claims are NOT authenticated and this function never actuates."""
        return (self.calibrated_min_us <= self.pulse_us <= self.calibrated_max_us
                and self.authorization_verified and self.hardware_ready_verified
                and not self.emergency_stop_active)
