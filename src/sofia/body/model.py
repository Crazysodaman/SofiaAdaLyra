from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class MotionKind(str,Enum):
    POSE="pose"
    STEP="step"
    STOP="stop"


@dataclass(frozen=True,slots=True)
class ServoCommand:
    channel:int
    pulse_us:int
    move_time_ms:int

    def __post_init__(self)->None:
        if type(self.channel) is not int or not 0<=self.channel<=31:
            raise ValueError("servo channel must be in 0..31")
        if type(self.pulse_us) is not int or not 500<=self.pulse_us<=2500:
            raise ValueError("servo pulse must be in 500..2500 us")
        if type(self.move_time_ms) is not int or not 20<=self.move_time_ms<=10000:
            raise ValueError("move_time_ms must be in 20..10000")


@dataclass(frozen=True,slots=True)
class MotionRequest:
    request_id:str
    kind:MotionKind
    commands:tuple[ServoCommand,...]

    def __post_init__(self)->None:
        if not isinstance(self.request_id,str) or not self.request_id.strip():
            raise ValueError("request_id must be nonempty")
        if not isinstance(self.kind,MotionKind):
            raise TypeError("kind must be MotionKind")
        if not isinstance(self.commands,tuple):
            raise TypeError("commands must be a tuple")
        if self.kind is MotionKind.STOP:
            if self.commands:
                raise ValueError("STOP request cannot contain servo commands")
        elif not self.commands:
            raise ValueError("motion request requires servo commands")
        channels=[item.channel for item in self.commands]
        if len(channels)!=len(set(channels)):
            raise ValueError("motion request contains duplicate servo channels")
