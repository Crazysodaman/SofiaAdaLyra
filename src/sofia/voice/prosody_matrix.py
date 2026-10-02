"""Bounded prosody planning from trusted contextual influence."""
from dataclasses import dataclass
from sofia.cognition.matrix import ContextualInfluenceMatrix,ContextualInfluencePlan,InfluenceMode,InfluenceSignal,InfluenceSurface
from sofia.personality.influence import ContinuityInfluence
from .model import VoiceProsodyProfile,VoiceUrgency

@dataclass(frozen=True, slots=True)
class VoiceProsodyPlan:
    urgency: VoiceUrgency
    profile: VoiceProsodyProfile
    influence_plan: ContextualInfluencePlan
    reasons: tuple[str,...]

_TARGETS={"excitement":(1.08,.4,1.12,1.03,.9),"excited":(1.08,.4,1.12,1.03,.9),"joy":(1.06,.3,1.10,1.02,.92),"happy":(1.06,.3,1.10,1.02,.92),"sadness":(.90,-.35,.82,.90,1.16),"sad":(.90,-.35,.82,.90,1.16),"grief":(.88,-.45,.78,.88,1.20),"anger":(.98,-.2,1.14,1.05,.9),"angry":(.98,-.2,1.14,1.05,.9),"frustration":(.97,-.15,1.10,1.03,.94),"frustrated":(.97,-.15,1.10,1.03,.94),"determination":(.99,-.1,1.10,1.03,.92),"concern":(.95,0,1.04,.98,1.06),"worried":(.94,0,1.04,.98,1.08),"nervous":(.96,.1,1.06,.98,1.02),"affection":(.96,.05,.94,.95,1.08),"fondness":(.96,.05,.94,.95,1.08),"warmth":(.97,.05,.96,.96,1.06),"calm":(.95,-.05,.90,.94,1.10),"content":(.97,0,.94,.96,1.06),"curiosity":(1.03,.1,1.04,1,.98),"hope":(1.02,.1,1.04,1,.98)}
def _blend(b,t,s): return b+(t-b)*s
def _clamp(v,lo,hi): return max(lo,min(hi,v))

class VoiceProsodyMatrix:
    def __init__(self,influence_matrix=None): self._matrix=influence_matrix or ContextualInfluenceMatrix()
    def plan(self,influence: ContinuityInfluence,*,urgency: VoiceUrgency=VoiceUrgency.NORMAL):
        if not isinstance(influence,ContinuityInfluence): raise TypeError("influence must be ContinuityInfluence")
        if not isinstance(urgency,VoiceUrgency): raise TypeError("urgency must be VoiceUrgency")
        ip=self._matrix.plan(InfluenceSurface.VOICE_EXPRESSION,influence)
        rate=pitch=0.0; rate=energy=volume=pause=1.0; pitch=0.0; tags=[]; ambient=[]; reasons=[]
        name=None if influence.primary_emotion is None else influence.primary_emotion.casefold()
        target=None if name is None else _TARGETS.get(name)
        if ip.mode_for(InfluenceSignal.EMOTION) is not InfluenceMode.NONE and target is not None:
            s=_clamp(float(influence.primary_intensity),0,1)
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
