"""Bounded prosody planning from trusted contextual influence."""
from dataclasses import dataclass
from sofia.cognition.matrix import ContextualInfluenceMatrix,ContextualInfluencePlan,InfluenceMode,InfluenceSignal,InfluenceSurface
from sofia.personality.influence import ContinuityInfluence
from enum import Enum

class VoiceUrgency(str, Enum):
    NORMAL="normal"; IMPORTANT="important"; URGENT="urgent"

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


@dataclass(frozen=True, slots=True)
class VoiceProsodyPlan:
    urgency: VoiceUrgency
    profile: VoiceProsodyProfile
    influence_plan: ContextualInfluencePlan
    reasons: tuple[str,...]

_TARGETS = {
    "affection": (.96, .05, .94, .95, 1.08),
    "affectionate-uncertainty": (.94, .08, .92, .93, 1.14),
    "amusement": (1.05, .25, 1.08, 1.01, .94),
    "anger": (.98, -.20, 1.14, 1.05, .90),
    "anticipation": (1.04, .18, 1.07, 1.01, .94),
    "appreciation": (.97, .05, .95, .96, 1.06),
    "aversion": (.93, -.18, .91, .94, 1.10),
    "bashfulness": (.92, .18, .86, .88, 1.18),
    "caution": (.94, -.05, .94, .96, 1.12),
    "concern": (.95, 0, 1.04, .98, 1.06),
    "contentment": (.97, 0, .94, .96, 1.06),
    "curiosity": (1.03, .10, 1.04, 1.00, .98),
    "determination": (.99, -.10, 1.10, 1.03, .92),
    "disappointment": (.91, -.25, .84, .91, 1.16),
    "disgust": (.92, -.25, .93, .95, 1.08),
    "embarrassment": (.91, .12, .84, .88, 1.18),
    "excitement": (1.08, .40, 1.12, 1.03, .90),
    "fear": (1.01, .22, 1.08, .98, .92),
    "fondness": (.96, .05, .94, .95, 1.08),
    "frustration": (.97, -.15, 1.10, 1.03, .94),
    "gratitude": (.97, .08, .96, .97, 1.05),
    "hope": (1.02, .10, 1.04, 1.00, .98),
    "humiliation": (.88, -.30, .78, .84, 1.24),
    "jealousy": (.95, -.12, 1.02, .96, 1.08),
    "joy": (1.06, .30, 1.10, 1.02, .92),
    "longing": (.92, .08, .88, .91, 1.18),
    "nervousness": (.96, .10, 1.06, .98, 1.02),
    "playfulness": (1.06, .30, 1.08, 1.01, .92),
    "pride": (1.00, -.05, 1.08, 1.03, .95),
    "reflection": (.91, -.10, .86, .92, 1.20),
    "relief": (.93, -.05, .88, .94, 1.14),
    "romance": (.93, .08, .90, .92, 1.14),
    "sadness": (.90, -.35, .82, .90, 1.16),
    "sensuality": (.90, -.05, .88, .90, 1.18),
    "sexual-arousal": (.98, .15, 1.03, .94, 1.05),
    "sexual-attraction": (.94, .12, .94, .93, 1.10),
    "sexual-desire": (.92, .05, .96, .92, 1.12),
    "shame": (.88, -.28, .78, .84, 1.24),
    "surprise": (1.08, .45, 1.10, 1.02, .86),
    "tenderness": (.92, .05, .88, .91, 1.16),
    "uncertainty": (.94, .05, .92, .94, 1.12),
    "warmth": (.97, .05, .96, .96, 1.06),
}
def _blend(b,t,s): return b+(t-b)*s
def _clamp(v,lo,hi): return max(lo,min(hi,v))

class VoiceProsodyMatrix:
    def __init__(self,influence_matrix=None): self._matrix=influence_matrix or ContextualInfluenceMatrix()
    def plan(self,influence: ContinuityInfluence,*,urgency: VoiceUrgency=VoiceUrgency.NORMAL):
        if not isinstance(influence,ContinuityInfluence): raise TypeError("influence must be ContinuityInfluence")
        if not isinstance(urgency,VoiceUrgency): raise TypeError("urgency must be VoiceUrgency")
        ip=self._matrix.plan(InfluenceSurface.VOICE_EXPRESSION,influence)
        rate=pitch=0.0; rate=energy=volume=pause=1.0; pitch=0.0; tags=[]; ambient=[]; reasons=[]
        expression_emotion = influence.foreground_emotion or influence.primary_emotion
        name=None if expression_emotion is None else expression_emotion.casefold()
        target=None if name is None else _TARGETS.get(name)
        if ip.mode_for(InfluenceSignal.EMOTION) is not InfluenceMode.NONE and target is not None:
            s=_clamp(float(
                influence.foreground_intensity
                if influence.foreground_emotion is not None
                else min(influence.primary_intensity, .20)
            ),0,1)
            rate=_blend(rate,target[0],s); pitch=_blend(pitch,target[1],s); energy=_blend(energy,target[2],s); volume=_blend(volume,target[3],s); pause=_blend(pause,target[4],s)
            tags.append(f"emotion:{name}"); reasons.append("evidence-linked modeled emotion applied as bounded prosody")
        else: reasons.append("no reviewed evidence-linked emotion prosody adjustment applied")
        if ip.mode_for(InfluenceSignal.DAYPART) is not InfluenceMode.NONE:
            if influence.daypart=="night": rate*=.96; energy*=.94; volume*=.94; pause*=1.06
            elif influence.daypart=="evening": rate*=.99; energy*=.98; volume*=.98; pause*=1.02
            elif influence.daypart=="morning": rate*=1.01; energy*=1.02; volume*=1.01; pause*=.98
            tags.append(f"daypart:{influence.daypart}"); reasons.append("trusted daypart applied only as a subtle delivery bias")
        if ip.mode_for(InfluenceSignal.WEATHER) is InfluenceMode.EXPRESSION_ONLY and influence.weather_condition: ambient.append("weather:"+influence.weather_condition.casefold())
        if ip.mode_for(InfluenceSignal.SEASON) is InfluenceMode.EXPRESSION_ONLY and influence.season: ambient.append("season:"+influence.season.casefold())
        if urgency is VoiceUrgency.IMPORTANT: rate=max(rate,1.03); energy=max(energy,1.06); volume=max(volume,1.02); pause=min(pause,.96); tags.append("urgency:important"); reasons.append("important delivery raises clarity without changing authority")
        elif urgency is VoiceUrgency.URGENT: rate=max(rate,1.10); energy=max(energy,1.16); volume=max(volume,1.06); pause=min(pause,.84); tags.append("urgency:urgent"); reasons.append("urgent delivery prioritizes clarity without changing authority")
        p=VoiceProsodyProfile(round(_clamp(rate,.75,1.25),4),round(_clamp(pitch,-2,2),4),round(_clamp(energy,.6,1.4),4),round(_clamp(volume,.6,1.3),4),round(_clamp(pause,.7,1.4),4),tuple(tags),tuple(ambient))
        return VoiceProsodyPlan(urgency,p,ip,tuple(reasons))
