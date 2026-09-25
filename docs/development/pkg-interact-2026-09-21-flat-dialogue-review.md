# PKG-INTERACT: flat-dialogue live review (2026-09-21)

## Observed at `733f63a` (user-supplied Windows CLI transcript)

- Startup continuity is concise. The two body-touch turns produce the same generic refusal, rather than distinct context-aware replies. This is an observed output problem; no consent, enjoyment, or willingness should be inferred from the user's gesture text.
- `*pats your left ear*` yields only `*one ear flicks*`. That exact phrase is an optional cue in the v1 interaction engine, not evidence of a sensed touch or actual avatar animation. A short reply is not intrinsically wrong, but a repeated cue without substantive engagement does not satisfy the desired character depth.
- `I ask to hug you` is classified as an **offer**, not performed contact. The model nevertheless frames the offered virtual hug as disallowed physical contact and gives a generic assistant redirection.
- The Windows-service answer becomes a ten-section checklist, recommends unrelated broad repairs and temporarily disabling security tools, and uses `sc` without `.exe` in commands while saying PowerShell is supported. This is not an accepted first-step diagnostic.
- The 43 focused and 274 coordinated Windows tests passed at `733f63a` before this live run; the live **quality gate fails**. Those passes do not verify any subsequent commit.

## Source diagnosis and bounded repair

`src/sofia/cognition/repetition_guard.py` compares a draft only when its normalized text contains >=120 characters. The very short `*one ear flicks*` and brief refusals are not evidence the guard triggered; only tool-free near-verbatim long replies receive one retry. The provider has no content-free per-turn report of whether a retry occurred, so do not attribute this flattening to the retry without instrumentation or a controlled comparison.

The existing `NaturalInteractionEngine` accepts limited single-gesture forms. The two observed butt-touch phrases were not classified: `butt` lacked a reviewed alias, the praise-prefaced form did not match the whole-action parser, and `grope/gropes` were not explicit vocabulary. Therefore the specific interaction prompt and durable gesture policy were not attached to those turns. This is a demonstrated **routing gap**, not proof that all refusals stem from missing classification.

At `6e301dd`, the grammar gained a narrow `butt` -> `buttocks` alias, a strict single-gesture `Good girl, ...` preface, and an explicit `grope/gropes/groping` lexical mapping to the existing `intimate-touch` semantic ID. No catchall verb, region-wide permission, consent inference, physical contact, executable action, or alternate reaction script is added. At `c472fc5`, regression tests cover the actual phrases, discussion/negation/composites, offered hug, ambiguous ear, and temporary-DB ledger stop/replay.

## Still open: character and response quality

- The v1 ear decision lists `*one ear flicks*` as an optional text cue. Confirm how to keep expressive cues available without model parroting; do not make mandatory gestures or force a length minimum on all social turns.
- The style and interaction prompts contain numerous negative instructions. Review their combined provider-bound ordering and full payload with user-approved redacted diagnostics before broadly rewriting personality or constitutional summaries.
- Determine whether the repeat guard triggered on any long response using a content-free counter or an isolated A/B with the same model and prompts. Do not claim the guard fixed or caused flattening from this one transcript.
- Treat offers, descriptions, feelings, and consent as distinct. A fictional represented body is not a real sensor, but an offer of a represented hug can receive a contextual character response without a physical-body disclaimer or a default acceptance.
- First Windows diagnostic should request service name and exact error/event and propose a discriminating read-only check. `sc.exe` must be used when suggesting a command that may be entered in PowerShell. Do not jump to reinstall, antivirus disable, malware or broad OS repair without evidence.
- Compare model behavior under controlled, privacy-preserving conditions only after parsing/provider construction is verified. No arbitrary tone-enforcing response postprocessor, stock script, automatic intimacy approval, or DB reset.

## Next verification

On `feature/pkg-interact-shared-engine`, close CLI, preserve `state/sofia.db`, its backup and the user's local Ollama test edit; fast-forward pull. First run `test/test_interaction_live_phrase_coverage.py` with `test/test_interaction_expanded_service.py`, `test/test_interaction_context_hygiene.py`, `test/test_ollama_repetition_guard.py` and `test/test_ollama_provider.py`. If green, run the 274-test coordinated subset and a brief supervised live CLI comparison including a prior refusal, an ear pat, two distinct gestures and an offered hug. Evaluate relevance and optional expression, not only duplicate similarity. Complete full suite, CORE/SAFE and user-authorized merge reviews separately.
