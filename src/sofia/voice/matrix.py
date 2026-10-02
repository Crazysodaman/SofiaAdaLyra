"""VOICE contribution to the message matrix."""
import re
from sofia.cognition.matrix.model import DomainContribution,MatrixDomain,MatrixRelevance
_VOICE=re.compile(r"\b(?:voice|speech|speak|speaking|microphone|\bmic\b|audio|tts|stt|text[- ]to[- ]speech|speech[- ]to[- ]text|listen|listening|push[- ]to[- ]talk|say\s+aloud|read\s+aloud|talk\s+aloud)\b",re.IGNORECASE)
class VoiceMatrixEvaluator:
    domain=MatrixDomain.VOICE
    def evaluate(self,envelope,turn):
        if not _VOICE.search(envelope.content): return None
        return DomainContribution(self.domain,MatrixRelevance.REQUIRED,"VOICE owns voice-runtime state and spoken-delivery projection")
