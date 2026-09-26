"""Synthetic robotics fixtures; real Gaia hardware is a separate gated adapter."""
from .simulator import MotionPlan, ServoSpec, SimulatedStop, SyntheticServoRig

__all__ = ["MotionPlan", "ServoSpec", "SimulatedStop", "SyntheticServoRig"]
