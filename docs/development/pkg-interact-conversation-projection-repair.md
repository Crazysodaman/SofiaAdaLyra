# INTERACT: A/B evidence and bounded conversation projection

Status: **unverified code candidate**. This note records Sparks's real Windows A/B report after `23fe17d` and the follow-up implementation. Neither unit tests nor a new supervised CLI run have been reported for this candidate. `main` and production `state/sofia.db` are not modified by these GitHub changes.

## Actual A/B report from user

- Configured Ollama `qwen3:14b`, thinking `False`, `num_ctx=20000`. A (minimal personality) used about 3,300 prompt characters per case; B (original full, static assembler) used **73,554–74,443** for ear, offered hug and hypothetical. Technical B announced **72,318** characters, but the supplied transcript ended before its reply. Do not fabricate the missing output or a complete technical A/B result.
- Minimal A invented standing fondness for ear touches; B ear response generalized into poetic commentary. A and B offered hug responses fell back on physical-body disclaimers rather than participating in the proposed represented interaction. Both hypothetical versions denied Sofía's canonical represented form; the model already failed some grounding with A, so prompt size is *not* established as the sole cause. Minimal A technical response asked for the service name and Event Viewer evidence; no B technical output was supplied.
- A/B uses synthetic prompts without the actual saved history, emotional/reflection journal, runtime continuity, or tool results. A/B differences are diagnostic, not proof of live quality.

## Implemented candidate

`src/sofia/cognition/conversation_assembler.py` subclasses the default provider-neutral assembler. `compose()` selects it for the configured Ollama provider; other providers retain the original full assembler. For a tool-free turn with a long loaded Constitution, the new assembler omits **only the verbatim constitutional copy sent to the model**, not the protected file, its runtime integrity check, canonical `core_state`, structured self-state, grounding hierarchy, personality, memory projection, or any user/request messages. A short source-derived conversational projection supplies Constitution version/hash and foundational truth, autonomy, revocation, capability/authority and representational embodiment distinctions. A final expression-priority note reminds the model to respond to the actual user turn without a template, invented preference/history or generic body disclaimer; this is model guidance, not deterministic enforcement.

The **entire** Constitution remains in the model request when its content is short, the user explicitly asks about constitutional matters, or the operation has exposed tools. The full Constitution remains loaded and integrity-checked by `SofiaRuntime.start()` in every case. No constitutional file, SHA, authorization contract or DB was rewritten; no tool authority or background worker was added. This tradeoff should receive CORE/SAFE review because a compact model projection is *not* a complete enforcement mechanism for the constitutional text.

The A/B probe's B arm now uses this **bounded static assembler** so it approximates the new Ollama conversation path. Previous B responses came from the old **full static** assembler and must not be conflated with new B measurements. B still is not an exact live prompt. `test/test_conversational_context_projection.py` asserts canonical state and original user/system messages survive; ordinary long-doc conversations are shorter; explicit constitutional and tool-bearing requests retain the entire original; short-doc/default behavior remains unchanged. The existing probe tests now require the new bounded projection.

## Gates, in order

1. On Windows with Sofía closed, fast-forward pull the feature branch; **preserve** the locally edited `test/test_ollama_generation_contract.py`, modified `state/sofia.db` and timestamped backup. No reset, clean, stash or migration.
2. Run `python -m pytest -q -x test/test_conversational_context_projection.py test/test_interaction_ab_probe.py test/test_interaction_context_hygiene.py test/test_interaction_live_discussion.py test/test_interaction_expanded_service.py`. Fix any first traceback before calling the candidate verified. Then rerun the coordinated interaction/application suite pinned to this new SHA. Earlier **26 focused / 274 coordinated passes belong to `23fe17d`**, before this code.
3. Run `python -m sofia.interaction.ab_probe` on the new SHA to compare short A with bounded B, record every response and prompt-character count; a static comparison alone cannot prove real live quality or internal priorities.
4. Re-run a fresh supervised multi-turn `python -m sofia` session on the same SHA and assess personality, source-grounded prior claims, offer-vs-described contact, hypothetical represented anatomy, stop/resume, repetition, and first diagnostic step for a Windows service. Save original transcript evidence; no artificial user-state reset.
5. Full `pytest -q`, CORE/SAFE review of shortened provider projection and long-history/context budget, PR diff/privacy/migration review on copies, and separately authorized merge **only after** live acceptance. Discord D0–D4 remains a future, not deployed, integration.

## Open risks

ConversationService currently forwards the entire active session history. A compact Constitution projection does not solve unbounded chat history; any later context-window policy must preserve the latest user turn and trusted control/context messages and never delete saved evidence. The model may still generate inaccurate replies under either prompt; output validation/model comparisons remain open. No logging of raw private prompt contents, outbound delivery, persona guarantee, or full constitutional enforcement by summary is claimed.
