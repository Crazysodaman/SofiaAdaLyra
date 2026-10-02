from sofia.voice import VoiceInputMode,VoiceRuntimeDisposition,VoiceRuntimeMatrix,VoiceRuntimeSignals
def ready_signals(**x):
    v=dict(microphone_available=True,speaker_available=True,stt_available=True,stt_healthy=True,tts_available=True,tts_healthy=True,listening_enabled=True,speech_output_enabled=True,input_mode=VoiceInputMode.PUSH_TO_TALK);v.update(x);return VoiceRuntimeSignals(**v)
def test_full_voice_stack_is_ready():
    p=VoiceRuntimeMatrix().evaluate(ready_signals());assert p.disposition is VoiceRuntimeDisposition.READY;assert p.can_listen and p.can_speak;assert p.effective_input_mode is VoiceInputMode.PUSH_TO_TALK
def test_missing_microphone_falls_back_to_text_input_without_disabling_tts():
    p=VoiceRuntimeMatrix().evaluate(ready_signals(microphone_available=False));assert p.disposition is VoiceRuntimeDisposition.DEGRADED;assert not p.can_listen and p.can_speak;assert p.fallback_to_text_input
def test_unhealthy_tts_keeps_listening_but_requires_text_output():
    p=VoiceRuntimeMatrix().evaluate(ready_signals(tts_healthy=False));assert p.can_listen and not p.can_speak;assert p.fallback_to_text_output
def test_no_voice_evidence_fails_closed_to_text_only():
    p=VoiceRuntimeMatrix().evaluate(VoiceRuntimeSignals());assert p.disposition is VoiceRuntimeDisposition.TEXT_ONLY;assert not p.can_listen and not p.can_speak
def test_explicit_text_only_input_is_not_reported_as_failed_voice_input():
    p=VoiceRuntimeMatrix().evaluate(ready_signals(input_mode=VoiceInputMode.TEXT_ONLY));assert not p.can_listen and p.can_speak;assert not p.fallback_to_text_input
def test_explicit_voice_controls_override_healthy_devices_and_engines():
    p=VoiceRuntimeMatrix().evaluate(ready_signals(listening_enabled=False,speech_output_enabled=False));assert p.disposition is VoiceRuntimeDisposition.TEXT_ONLY
