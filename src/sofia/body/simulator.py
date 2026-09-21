"""Synthetic servo state machine. Deliberately NO serial, USB or robot API."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


class SimulatedStop(RuntimeError):
    """The synthetic simulation has been latched stopped."""


@dataclass(frozen=True)
class ServoSpec:
    channel: str
    min_pulse_us: int
    max_pulse_us: int
    max_step_us: int
    initial_pulse_us: int

    def __post_init__(self) -> None:
        if not isinstance(self.channel, str) or not self.channel.strip():
            raise ValueError("channel must be named")
        values = (self.min_pulse_us, self.max_pulse_us, self.max_step_us, self.initial_pulse_us)
        if any(type(value) is not int for value in values):
            raise TypeError("pulse values must be integers")
        if not (500 <= self.min_pulse_us < self.max_pulse_us <= 2500):
            raise ValueError("invalid synthetic pulse envelope")
        if not 0 < self.max_step_us <= self.max_pulse_us - self.min_pulse_us:
            raise ValueError("invalid per-step delta")
        if not self.min_pulse_us <= self.initial_pulse_us <= self.max_pulse_us:
            raise ValueError("initial pulse outside envelope")


@dataclass(frozen=True)
class MotionPlan:
    revision: int
    targets: tuple[tuple[str, int], ...]


class SyntheticServoRig:
    """In-memory simulation only. A plan is NOT motor permission or execution."""

    def __init__(self, specs: tuple[ServoSpec, ...]) -> None:
        if not isinstance(specs, tuple) or not specs or any(not isinstance(s, ServoSpec) for s in specs):
            raise ValueError("nonempty ServoSpec tuple required")
        names = [spec.channel for spec in specs]
        if len(set(names)) != len(names):
            raise ValueError("duplicate servo channels")
        self._specs = {spec.channel: spec for spec in specs}
        self._positions = {spec.channel: spec.initial_pulse_us for spec in specs}
        self._revision = 0
        self._stopped = True  # external process cannot release an actual e-stop through this class

    @property
    def stopped(self) -> bool:
        return self._stopped

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def positions(self) -> Mapping[str, int]:
        return MappingProxyType(self._positions.copy())

    def start_simulation(self) -> None:
        """Local synthetic reset only; not an e-stop reset, unlock or grant."""
        self._positions = {channel: spec.initial_pulse_us for channel, spec in self._specs.items()}
        self._revision += 1
        self._stopped = False

    def stop_simulation(self) -> None:
        """Latch synthetic halt, invalidating outstanding plans."""
        self._stopped = True
        self._revision += 1

    def propose(self, targets: Mapping[str, int]) -> MotionPlan:
        if self._stopped:
            raise SimulatedStop("simulation stopped")
        if not isinstance(targets, Mapping) or not targets:
            raise ValueError("nonempty target mapping required")
        if any(not isinstance(key, str) for key in targets):
            raise ValueError("channel IDs must be strings")
        commands: list[tuple[str, int]] = []
        for channel, pulse in targets.items():
            if channel not in self._specs:
                raise ValueError("unknown channel")
            spec = self._specs[channel]
            if type(pulse) is not int:
                raise TypeError("pulse must be an integer")
            if not spec.min_pulse_us <= pulse <= spec.max_pulse_us:
                raise ValueError("pulse outside configured synthetic envelope")
            if abs(pulse - self._positions[channel]) > spec.max_step_us:
                raise ValueError("pulse exceeds simulated maximum step")
            commands.append((channel, pulse))
        return MotionPlan(self._revision, tuple(sorted(commands)))

    def apply_simulation(self, plan: MotionPlan) -> None:
        if self._stopped:
            raise SimulatedStop("simulation stopped")
        if not isinstance(plan, MotionPlan):
            raise TypeError("MotionPlan required")
        if plan.revision != self._revision:
            raise ValueError("stale plan")
        # Revalidate external plans atomically; never trust their stated revision.
        proposed = self.propose(dict(plan.targets))
        if proposed.targets != plan.targets or len(dict(plan.targets)) != len(plan.targets):
            raise ValueError("noncanonical or duplicate channels")
        for channel, pulse in plan.targets:
            self._positions[channel] = pulse
        self._revision += 1
