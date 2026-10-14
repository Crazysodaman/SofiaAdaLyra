# V18 Phase 00 CA-1207: model configuration and response UTF-8 boundary

Date: 2026-10-14. Production provider config previously accepted
NaN/Infinity as temperatures and bool masquerading as seed/context/output
integers. These were invalid model controls and could be passed into
Ollama generation options. ProviderConfiguration now requires a finite,
nonnegative temperature and genuine integer settings.

Ollama response parsing previously allowed model content containing
isolated Unicode surrogates, which cannot be serialized as UTF-8 into
canonical persistence, network or response transport. It now raises
a typed LLMProviderError before the response reaches persistence.
Tests cover all malformed configurations and the surrogate boundary,
without logs leaking the invalid payload. No fallback, new DB or permission
grant was added.

This fixes a concrete CA-1207 slice, not full outage handling or
the required independent Gate 4 acceptance.
