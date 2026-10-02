"""Typed contracts for Sofía's voice runtime and delivery planning."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class VoiceInputMode(str, Enum):
    TEXT_ONLY="text_only"; PUSH_TO_TALK="push_to_talk"; CONTINUOUS="continuous"

class VoiceRuntimeDisposition(str, Enum):
    READY="ready"; DEGRADED="degraded"; TEXT_ONLY="text_only"

class VoiceUrgency(str, Enum):
    NORMAL="normal"; IMPORTANT="important"; URGENT="urgent"

@dataclass(frozen=True, slots=True)
class VoiceRuntimeSignals:
    microphone_available: bool=False
    speaker_available: bool=False
    stt_available: bool=False
    stt_healthy: bool=False
    tts_available: bool=False
    tts_healthy: bool=False
    listening_enabled: bool=True
    speech_output_enabled: bool=True
    input_mode: VoiceInputMode=VoiceInputMode.PUSH_TO_TALK
    def __post_init__(self):
        for name in ("microphone_available","speaker_available","stt_available","stt_healthy","tts_available","tts_healthy","listening_enabled","speech_output_enabled"):
            if type(getattr(self,name)) is not bool: raise TypeError(f"{name} must be bool")
        if not isinstance(self.input_mode,VoiceInputMode): raise TypeError("input_mode must be VoiceInputMode")

@dataclass(frozen=True, slots=True)
class VoiceRuntimePlan:
    disposition: VoiceRuntimeDisposition
    requested_input_mode: VoiceInputMode
    effective_input_mode: VoiceInputMode
    can_listen: bool
    can_speak: bool
    fallback_to_text_input: bool
    fallback_to_text_output: bool
    reasons: tuple[str,...]
    def __post_init__(self):
        if not isinstance(self.disposition,VoiceRuntimeDisposition): raise TypeError("disposition must be VoiceRuntimeDisposition")
        if not isinstance(self.requested_input_mode,VoiceInputMode): raise TypeError("requested_input_mode must be VoiceInputMode")
        if not isinstance(self.effective_input_mode,VoiceInputMode): raise TypeError("effective_input_mode must be VoiceInputMode")
        for name in ("can_listen","can_speak","fallback_to_text_input","fallback_to_text_output"):
            if type(getattr(self,name)) is not bool: raise TypeError(f"{name} must be bool")
        if not isinstance(self.reasons,tuple) or not self.reasons or any(not isinstance(x,str) or not x.strip() for x in self.reasons): raise ValueError("reasons must be nonempty strings")
        if not self.can_listen and self.effective_input_mode is not VoiceInputMode.TEXT_ONLY: raise ValueError("non-listening plans must use text-only effective input")
        if self.can_listen and self.effective_input_mode is VoiceInputMode.TEXT_ONLY: raise ValueError("listening plans cannot use text-only effective input")

@dataclass(frozen=True, slots=True)
class VoiceProsodyProfile:
    rate_scale: float=1.0
    pitch_semitones: float=0.0
    energy_scale: float=1.0
    volume_scale: float=1.0
    pause_scale: float=1.0
    tone_tags: tuple[str,...]=()
    ambient_context: tuple[str,...]=()
    def __post_init__(self):
        bounds={"rate_scale":(0.75,1.25),"pitch_semitones":(-2.0,2.0),"energy_scale":(0.60,1.40),"volume_scale":(0.60,1.30),"pause_scale":(0.70,1.40)}
        for name,(lo,hi) in bounds.items():
            v=getattr(self,name)
            if not isinstance(v,(int,float)) or isinstance(v,bool): raise TypeError(f"{name} must be numeric")
            if not lo <= float(v) <= hi: raise ValueError(f"{name} must be in [{lo}, {hi}]")
        for name in ("tone_tags","ambient_context"):
            vals=getattr(self,name)
            if not isinstance(vals,tuple): raise TypeError(f"{name} must be a tuple")
            if any(not isinstance(v,str) or not v.strip() for v in vals): raise ValueError(f"{name} must contain nonempty strings")
