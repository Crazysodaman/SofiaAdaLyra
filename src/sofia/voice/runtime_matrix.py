"""Capability/runtime matrix for the local voice stack."""
from .model import VoiceInputMode,VoiceRuntimeDisposition,VoiceRuntimePlan,VoiceRuntimeSignals

class VoiceRuntimeMatrix:
    def evaluate(self, signals: VoiceRuntimeSignals) -> VoiceRuntimePlan:
        if not isinstance(signals,VoiceRuntimeSignals): raise TypeError("signals must be VoiceRuntimeSignals")
        reasons=[]; requested=signals.input_mode
        wants=signals.listening_enabled and requested is not VoiceInputMode.TEXT_ONLY
        listen=bool(wants and signals.microphone_available and signals.stt_available and signals.stt_healthy)
        if requested is VoiceInputMode.TEXT_ONLY: reasons.append("text-only input mode is explicitly selected")
        elif not signals.listening_enabled: reasons.append("voice listening is explicitly disabled")
        elif not signals.microphone_available: reasons.append("no microphone availability evidence")
        elif not signals.stt_available: reasons.append("no speech-to-text engine availability evidence")
        elif not signals.stt_healthy: reasons.append("speech-to-text engine is not healthy")
        else: reasons.append("microphone and speech-to-text stack are ready")
        speak=bool(signals.speech_output_enabled and signals.speaker_available and signals.tts_available and signals.tts_healthy)
        if not signals.speech_output_enabled: reasons.append("voice output is explicitly disabled")
        elif not signals.speaker_available: reasons.append("no speaker/output-device availability evidence")
        elif not signals.tts_available: reasons.append("no text-to-speech engine availability evidence")
        elif not signals.tts_healthy: reasons.append("text-to-speech engine is not healthy")
        else: reasons.append("speaker and text-to-speech stack are ready")
        disposition=VoiceRuntimeDisposition.READY if listen and speak else VoiceRuntimeDisposition.DEGRADED if listen or speak else VoiceRuntimeDisposition.TEXT_ONLY
        return VoiceRuntimePlan(disposition,requested,requested if listen else VoiceInputMode.TEXT_ONLY,listen,speak,requested is not VoiceInputMode.TEXT_ONLY and not listen,not speak,tuple(reasons))
