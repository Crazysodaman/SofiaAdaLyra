# PKG-REL | Relationship continuity and nuanced expression

**Branch:** `feature/pkg-rel-foundation` from `main` SHA `2141879`. **Status:** a pure, unintegrated reviewed-preference proposal plus tests. The existing EmotionalJournal and personality are foundations; no model claim proves a subjective feeling, physical sensation, lasting preference or consent.

## Outcome
Preserve the documented Sparks/Sofía relationship and evolve *mutable* familiarity, humor and preferences from original, evidence-linked interactions and explicit corrections. Personality may be playful, serious or quietly responsive; she must not repeat one curiosity question after every gesture, assume a user action caused her affection, or fabricate prior intimacy. Canonical identity and constitutional boundaries are not mutable relationship settings.

## Slices
1. **R0 inspect:** review real source IDs, current emotion labels, consent/stop implementation, live transcripts and memory provenance. Separate model-generated declarations from user statements and independently reviewed revisions.
2. **R1 event semantics:** record actor, source, target, timestamp, modality, appraisal candidates, expressible alternatives and unresolved uncertainty; user pats and compliments never automatically assign Sofía positive emotion.
3. **R2 preference history:** explicit scoped preference revisions with likes, dislikes and uncertain states, corrections, expiry and reversible history. The new `src/sofia/package_foundations/rel.py` is only a validation object; a supplied reviewer ID is not authenticated and cannot grant permission.
4. **R3 expression planner:** context-dependent mixed emotions, variable intensity, restraint and silence; optional fox/voice/avatar expressions only when channels exist and actual acknowledgments are returned. No mood-meter unlock or forced intimate escalation.
5. **R4 multi-session continuity:** preserve evidence-linked changes across restart without promoting assistant hallucinations or private data to universal truth. Memory retrieval should be scoped to intended relationship and privacy settings.
6. **R5 corrective dialogue:** honor explicit user corrections, Sofía's expressed preferences and cross-client stop; avoid repetitive probing, formulaic disclaimers and unsubstantiated history.

## Testing, dependencies and release
Run `python -m pytest -q -x test/test_pkg_rel_foundation.py`, then add original-source forgery, opposite preferences, reviewed reversals, denial, privacy redaction, multi-turn repeated greeting and multi-session corrections. Supervised 20–30-turn live reviews should include neutral, affectionate, uncomfortable, serious, virtual lab and quiet exchanges with real model outputs rather than asserted scripts. Keep measurements of repetition and unsupported assertions. **Dependencies:** CORE for trustworthy self-state; INTERACT for single-gesture events and stop; MEM for reviewed durable learning; UI for real expressions; SAFE for privacy and revocation; VERIFY for longitudinal evidence. No new state migration or production user data change is approved; full-suite, live and separate merge gates remain open.
