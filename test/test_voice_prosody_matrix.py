from dataclasses import replace
from sofia.cognition.matrix import InfluenceMode,InfluenceSignal,InfluenceSurface
from sofia.personality.influence import ContinuityInfluence
from sofia.voice import VoiceProsodyMatrix,VoiceUrgency
def influence(**x):
    v=dict(
        daypart="evening",
        season="autumn",
        daylight="night",
        weather_condition="rainy",
        temperature_c=12.0,
        weather_freshness="current",
        location_freshness="current",
        primary_emotion_evidence_refs=("emotion:event-1",),
        emotional_tone="warm",
        primary_emotion="fondness",
        primary_intensity=.62,
        active_emotions=("fondness",),
        daypart_evidence_refs=("runtime.clock", "environment.location:test"),
        season_evidence_refs=("runtime.clock", "environment.location:test"),
        weather_evidence_refs=("environment.weather:test",),
    )
    v.update(x)
    return ContinuityInfluence(**v)
def numeric(p): return (p.rate_scale,p.pitch_semitones,p.energy_scale,p.volume_scale,p.pause_scale)
def test_voice_surface_bounds_context_strengths():
    m=VoiceProsodyMatrix().plan(influence()).influence_plan;assert m.surface is InfluenceSurface.VOICE_EXPRESSION;assert m.mode_for(InfluenceSignal.EMOTION) is InfluenceMode.BOUNDED_BIAS;assert m.mode_for(InfluenceSignal.DAYPART) is InfluenceMode.BOUNDED_BIAS;assert m.mode_for(InfluenceSignal.WEATHER) is InfluenceMode.EXPRESSION_ONLY;assert m.mode_for(InfluenceSignal.SEASON) is InfluenceMode.EXPRESSION_ONLY
def test_evidence_linked_excitement_increases_rate_and_energy():
    a=VoiceProsodyMatrix().plan(influence(daypart="afternoon",primary_emotion="excitement",primary_intensity=.8)).profile;b=VoiceProsodyMatrix().plan(influence(daypart="afternoon",primary_emotion=None,primary_intensity=0,primary_emotion_evidence_refs=(),active_emotions=())).profile;assert a.rate_scale>b.rate_scale and a.energy_scale>b.energy_scale
def test_unsupported_emotion_cannot_change_numeric_prosody():
    a=VoiceProsodyMatrix().plan(influence(daypart="afternoon",primary_emotion="excitement",primary_intensity=1,primary_emotion_evidence_refs=())).profile;b=VoiceProsodyMatrix().plan(influence(daypart="afternoon",primary_emotion=None,primary_intensity=0,primary_emotion_evidence_refs=(),active_emotions=())).profile;assert numeric(a)==numeric(b)
def test_night_delivery_is_subtle_not_a_personality_rewrite():
    b=influence(primary_emotion=None,primary_intensity=0,primary_emotion_evidence_refs=(),active_emotions=());n=VoiceProsodyMatrix().plan(replace(b,daypart="night")).profile;a=VoiceProsodyMatrix().plan(replace(b,daypart="afternoon")).profile;assert n.rate_scale<a.rate_scale and n.volume_scale<a.volume_scale and n.pause_scale>a.pause_scale and n.rate_scale>=.95
def test_urgent_delivery_overrides_night_softening_for_clarity():
    p=VoiceProsodyMatrix().plan(influence(daypart="night",primary_emotion="calm",primary_intensity=.8),urgency=VoiceUrgency.URGENT).profile;assert p.rate_scale>=1.10 and p.energy_scale>=1.16 and p.volume_scale>=1.06 and p.pause_scale<=.84
def test_weather_and_season_are_expression_only_not_numeric_prosody_controls():
    a=VoiceProsodyMatrix().plan(influence(daypart="afternoon")).profile;b=VoiceProsodyMatrix().plan(influence(daypart="afternoon",weather_condition="clear",season="summer")).profile;assert numeric(a)==numeric(b);assert a.ambient_context!=b.ambient_context
def test_stale_weather_and_missing_season_are_not_invented_as_ambient_context():
    p=VoiceProsodyMatrix().plan(influence(weather_condition="rainy",weather_freshness="stale",season=None)).profile;assert not any(x.startswith("weather:") for x in p.ambient_context);assert not any(x.startswith("season:") for x in p.ambient_context)
