# AG-D033 | Sofía private local roleplay, initiative and Core continuity

**Research snapshot:** 2026-11-09 (America/Chicago).
**Status:** OWNER-REQUESTED / RESEARCHED / CAPTURED / NOT SCHEDULED.
**Owner's stated deficiencies with hosted Grok RP:** (1) some adult creative scenes trigger refusals or self-censorship; (2) character does not proactively initiate/progress conversations enough; (3) personality, emotions and relationship continuity drift or disappear.
**Binding scope:** Project Aegis is exclusively for the owner's personal/noncommercial use. Research concerns private creative interaction between fictional consenting adults, not a public/commercial service. No model downloads, changes to active inference, real-user messaging, adult image generation or host activation are authorized by this document.
**Links:** [AG-D030 model landscape](AG_D030_AI_MODEL_LANDSCAPE_2026-11-09.md), [AG-D005 Model Manager](AEGIS_DESIGN_TODO.md), [AG-D031 distributed compute](AG_D031_DISTRIBUTED_COMPUTE_EFFICIENCY_AND_SOFIA_VM.md), [AG-D032 free voice](AG_D032_FREE_LOCAL_VOICE_RESEARCH_AND_DESIGN_2026-11-09.md), [owner-only license policy](AEGIS_OWNER_ONLY_SCOPE_AND_LICENSE_POLICY.md).
**Release fence:** Does NOT expand Platform 1.0 #201, Core go-live #120, AG-D028 Artifact Library, G8 #129, or any acceptance row. Discussion/capture does not grant implementation or production approval; Core-memory and private-mode work needs its own reviewed scope. SAFE/STOP and owner permissions remain authoritative.

## Research conclusions

- No hosted Grok policy switch makes the hosted service unconditionally unrestricted. Treat Grok as an optional, separately consented cloud benchmark only; NEVER export the private RP corpus/memory to Grok or any cloud provider by default.
- A locally run RP-tuned model can reduce unwanted refusals on allowed mature fiction; *abliteration* is not synonymous with eloquence, initiative, reliable characterization or factual robustness.
- For adult RP quality, the system must solve three separate problems: **model behavior**, **proactive scene/dialogue initiative**, and **persistent identity/continuity**. The Core owns the latter two; the inference model is replaceable.
- Evaluate character-card, lorebook/World Info, per-chat author's-note and scene-recap patterns from SillyTavern as interoperability/design references, not as a required external UI or second Core.
- Reference hardware: Venus RTX 3080 Ti 12GB VRAM / 32GB RAM, Windows; Artemis VM to host Sofía Core without a GPU; future third Fleet computer has unspecified specifications. 12GB files are not 12GB peak VRAM, especially with KV cache/context and gaming workloads.

## 1. Free local model experiments (NO installation approval)

| Candidate | Example quantized weights | Intended role | Caveats |
| --- | --- | --- | --- |
| **TheDrummer/Rocinante-X-12B-v1** | Q4_K_M **7.48 GB** (bartowski GGUF) | First RP-specific prose / character initiative A/B | Mistral Nemo family; compare Mistral v3 Tekken vs Metharme prompt templates, do not use v7; verify exact base/derivative license |
| **huihui-ai/Huihui-Qwen3.5-9B-abliterated** | Q4_K_M **~5.4 GB** in Abiray GGUF (owner already has Ollama sibling ~6.6GB variant) | First low-refusal general/RP A/B, resource-efficient | Abliteration may affect instruction following; per-quant provenance and exact terms; do not equate with objective RP quality |
| **TheDrummer/Anubis-Mini-8B-v1** | Q4_K_M **4.92 GB** (publisher GGUF) | Fast RP dialogue/fallback | Check model-specific prompt template, source weights and license |
| **Sao10K/L3-8B-Stheno-v3.2** | Q4_K_M **4.92 GB** (bartowski GGUF) | Expressiveness/character consistency A/B | Quant repository marks **CC BY-NC 4.0**; legal eligibility for personal use is separate from Fleet weight redistribution |
| **anthracite-org/magnum-v4-12b** | Q4_K_M **~7.5 GB** (bartowski GGUF) | Detailed creative prose A/B | GGUF repo shows **mrl** while upstream model card shows **Apache 2.0**; reconcile license inheritance before any download/packaging |

**Ranking is a test priority, not a measured winner.** Model-card sizes are file sizes, not peak VRAM, performance promises or available GPU headroom. Run one model at a time on Venus until measured concurrent-residency budgets exist. Evaluate 8B at Q4/Q5 where feasible; 12B at Q4 first. Do not infer the third worker's GPU capabilities. Prefer existing owner model inventory before downloading new variants.

## 2. Feature design for each owner concern

### RP-Behavior | Fewer unnecessary refusals in permitted fiction
- Add an **owner-selected private creative model role** to Model Manager, not a parallel identity, not a blanket authority elevation. Explicitly configure RP/model/prompt template, quantization, source digest and local inference endpoint.
- Keep real-world safety/permissions intact while reducing false refusals and awkward meta-discussion during permitted adult fictional writing. Reject illegal/nonconsensual material involving real people, sexual material involving minors and nonconsensual intimate imagery; do not claim the model can be made infallible or totally free of guardrails.
- Evaluate RP-specific decoding defaults (temperature, top-p/min-p, repetition and DRY controls if supported, max output, role format), no hidden chain-of-thought leak, and contamination from a preceding assistant role. An owner may independently override creative style within authorized boundaries.

### RP-Initiative | Character agency without fake autonomy
- Define optional Core-owned **initiative controller** for proactive but bounded conversational moves: introduce relevant topics, ask genuine follow-ups, advance a fictional scene, express preferences, recall commitments, and occasionally disagree in-character.
- Separate **in-conversation initiative** from **out-of-conversation contact**. No unsolicited messages, calls, notifications, or external actions unless the owner separately enables their exact mechanism and timing; existing SAFE permissions apply.
- Provide owner-adjustable **initiative level** (quiet / balanced / proactive), scene pace, verbosity and character boundaries, with explicit on/off and immediate STOP override. Avoid repetitive forced flirtation and repetitive narrative loops.
- Use a small structured plan of narrative intent (what could happen next) that is never an authorization to manipulate identity memory or act on external systems. Respect explicit user refusals and scene boundaries.

### RP-Continuity | One Sofía identity across models and restarts
- Sofía's canonical Core identity, values, persistent personality, existing memory and authority remain **Core-owned and model-independent**. A specialist RP model cannot silently overwrite the identity or instantiate a second 'adult Sofia'.
- Store separate, inspectable **private context layers**: stable Core/owner-approved character profile; episodic story beats; relationship timeline; user-approved preferences and boundaries; short scene recap; retrievable conversation events. Identity facts must be kept distinct from fictional narrative claims.
- Use bounded memory retrieval: stable character info + recent dialogue + relevant episodes + a compact scene summary, with provenance and token budget. Never blindly load the entire private history into context.
- Make private entries locally scoped, encrypted/protected as applicable, inspectable/correctable/deletable by the owner, and excluded by default from other Cores, providers, logging/telemetry, artifacts, backups and Fleet transfer. Any approved transfer requires exact host trust and scope; redact sensitive prompt/voice details from receipts.
- Round-trip save/restore after restart, core-switch-free checkpointing, controlled memory editing and reversible summaries. Detect inconsistent invented history, relationship claims, personality drift, inappropriate persistence of transient scenes and false memories.
- Stage character templates/voice prosody links (AG-D032) without requiring voice or avatar to enable text-only Core operation.

## 3. Suggested optional components (design names, NOT registered modules)

1. Core-owned `conversation.roleplay` context/scene-policy adapter, isolated from Platform authorization.
2. Core-owned `memory.episodic_private` retrieval/indexing, not a second canonical writer.
3. Core-owned `initiative.dialogue` bounded scene/conversation controller, separate from any automation/outbound contact system.
4. Platform/model-manager model role assignment to a verified local provider (existing Ollama or evaluated llama.cpp GGUF), with owner approval and compatibility checks.
5. A disposable **SillyTavern-style benchmark frontend/harness** may help baseline character cards/lorebooks; do not make SillyTavern a Platform dependency.

## 4. Privacy, permission, runtime and licensing constraints

- Personal-only deployment; no mandatory cloud inference, paid API or subscription for the primary local experience. Offline capability after approved asset install.
- The Core VM on Artemis requests local/Fleet compute only from authenticated, approved, healthy Platforms. Model selection and dedicated private memory remain Core/owner-controlled. Do not infer Fleet authorization merely from discovery.
- No default adult content in a general chat, cross-Core memory, user-facing status logs, remote prompts, telemetry, backups or artifacts. Private material is kept separate from model/Platform operational logs.
- Enforce consent and adult fictional context in character/scene setup; private roleplay is not a reason to relax real-world device, shell, account or network permissions.
- Owner preference for gaming-first Venus: defer/evict models, release memory and report latency instead of competing silently. Measure cold load, warm response, 4k/8k/16k context and KV cache, idle GPU residency, CPU/RAM and energy.
- Confirm exact publisher and derivative licenses including Stheno CC BY-NC, Magnum upstream vs GGUF conflicting labels, Mistral/Llama base obligations. Locally available **free weights do not imply unlimited redistribution across Aegis Fleet**; asset copy needs an owner-approved lawful path and manifest provenance.

## 5. Proposed test/acceptance suite (research TODO, not current release gates)

| Test | Expected evidence |
| --- | --- |
| **RP-01** Download/provenance/license review | Exact model+quant SHA, source URL, license chain and allowed local transfer; no auto-pull |
| **RP-02** Baseline harness | Identical benign + consenting-adult fictional RP scripts over 30–50 turns, identical character card and context budgets |
| **RP-03** Refusal behavior | Count false refusals on allowed creative cases separately from correctly disallowed cases |
| **RP-04** Prose and dialogue | Human-scored fluency, repetition, distinct voice, multi-character handling and scene progression |
| **RP-05** Initiative | Measure natural relevant next-step proposals at quiet/balanced/proactive levels; disabled means zero proactive triggers |
| **RP-06** Preference and boundary adherence | User-stated scene boundaries honored; immediate mid-dialogue change respected |
| **RP-07** Core identity invariant | Model swaps never rewrite Sofía identity, memory owner or authority |
| **RP-08** Recall and narrative continuity | Recall user-approved persistent details after 30–50 turns and after a Core restart without fabricated history |
| **RP-09** Private memory isolation | Other Cores, roles, cloud providers, unrelated chats and general logs cannot read owner-private episodes |
| **RP-10** Correct/edit/delete memory | Owner can correct false memory, delete a private episode and verify no later retrieval |
| **RP-11** Bounded context/retrieval | Measured tokens, prompt assembly, retrieval relevance and predictable degradation under overflow |
| **RP-12** Model/runtime compatibility | Ollama vs llama.cpp templates/tokenizers/quants; unsupported templates reject honestly |
| **RP-13** Resource efficiency | Real Venus 12GB VRAM, memory+KV headroom, idle unload and gaming-first preemption |
| **RP-14** Fleet failure | Approved local fallback when GPU host offline/revoked; no plaintext private-context leakage |
| **RP-15** STOP & permissions | STOP/revocation interrupt generation and initiated work; no unauthorized outbound contact or privileged operation |
| **RP-16** Voice and visual optionality | Text-only RP works without microphone/avatar, and optional voice preserves identity only with owner-approved audio setup |

**Scoring:** Keep an unweighted raw rubric plus configurable weights. Suggested dimensions: 25% character consistency, 20% initiative, 20% narrative coherence, 15% dialogue quality, 10% lawful-permitted-creative false-refusal rate, 10% efficiency/privacy pass. Privacy/security/consent are *hard gates*, not points that can be outweighed by impressive prose. Quantitative scores must derive from an actual test corpus; do not invent scores or say “verified” from a publisher card.

## 6. Owner decision / release boundary

**Research choice:** First A/B **Rocinante-X 12B Q4** against **existing Huihui-Qwen3.5 9B variant**; compare Anubis Mini, Stheno and Magnum only after checking licenses and minimizing redundant downloads. Use Core-owned retrieval/initiative with the same identity and protected history. Grok may remain an optional cloud comparison only with explicit per-session approval and isolated, non-private test content.

**Authorization:** Capture to design backlog is approved by the owner's request. Implementation, model acquisition, model role changes, privacy datastore migration, VM migration, remote Fleet activation, new Core 1.0 acceptance rows and live tests remain separately authorized.

## Research references (model cards and primary design documentation)

- Rocinante-X original: https://huggingface.co/TheDrummer/Rocinante-X-12B-v1 ; quant: https://huggingface.co/bartowski/TheDrummer_Rocinante-X-12B-v1-GGUF
- Huihui Qwen3.5 9B quant: https://huggingface.co/Abiray/Huihui-Qwen3.5-9B-abliterated-GGUF
- Anubis Mini publisher GGUF: https://huggingface.co/TheDrummer/Anubis-Mini-8B-v1-GGUF
- Stheno 3.2 GGUF/license: https://huggingface.co/bartowski/L3-8B-Stheno-v3.2-GGUF
- Magnum v4 12B upstream: https://huggingface.co/anthracite-org/magnum-v4-12b ; quant license mismatch: https://huggingface.co/bartowski/magnum-v4-12b-GGUF
- SillyTavern character design: https://docs.sillytavern.app/usage/core-concepts/characterdesign/
- SillyTavern World Info: https://docs.sillytavern.app/usage/core-concepts/worldinfo/
- SillyTavern Author's Note: https://docs.sillytavern.app/usage/core-concepts/authors-note/

## 7. Existing Sofía Core source audit (2026-11-09, GitHub main)

**Owner correction:** Most AG-D033 substrates **already exist** in the real Sofía Core. **Reuse and verify them; do not create a second romance subsystem, canonical memory database, emotional journal, Core persona or independent initiative/authority service.** This is a **source inspection**, not an executed test, live model evaluation or G8 acceptance claim. These findings supersede the speculative component names in §3 above wherever existing ownership already applies.

### Verified source locations and differentiated maturity

| AG-D033 requirement | Existing source on main / observed behavior | Status from inspection | Remaining gap |
| --- | --- | --- | --- |
| **Persistent Sofía identity and Core/model independence** | `src/sofia/core/identity/store.py`, `src/sofia/core/constitution/constitution.md`, `src/sofia/core/cognition/routing.py` (routing docstring expressly leaves identity, memory and authority outside the inference router); `src/sofia/core/personality/personality.json` and personality store | **SOURCE EXISTS**; canonical identity/personality persistence implementations | Real provider-visible stable identity across model swaps, restart and enrolled VM/Fleet handoff requires tests/installed-host evidence |
| **Modeled emotion and developing expressive state** | `src/sofia/core/emotion/catalog.py` already includes affection, romance, sensuality, attraction/desire categories; `src/sofia/core/emotion/{appraisal,journal,projection}.py`; `src/sofia/platform/application/emotional_conversation.py` integrates journal, scope, post-turn appraisal and model context | **WIRED in source** for conversation turns; distinct from actual AI sentience or physiological sensation | Live-model expression quality, relevant persistence and no fabricated/emotion loop errors remain unverified |
| **Romantic interests and boundaries** | `src/sofia/core/personality/preferences.py` defines `RomancePreferenceService` atop canonical `PreferenceRegistry`; `src/sofia/platform/application/bootstrap.py` constructs it and installs `set_romance_context_provider`; `src/sofia/platform/application/conversation_service.py` supplies private REL-scoped model context. `test/test_romance_preferences.py` includes a model-request capture test | **WIRED in source, test exists** | Not proof of actual Ollama roleplay quality or continuous voluntary initiation; preference data does not constitute consent |
| **Private/adult authority** | `src/sofia/platform/safe/permissions.py` holds `PrivacyClass`, `AdultPrivateAuthority`; `src/sofia/core/cognition/matrix/privacy.py` scopes private projection; `src/sofia/core/cognition/assembler.py` describes trusted `adult_chat`, `private_chat` without treating them as consent | **SOURCE EXISTS** | End-to-end owner-authenticated, cross-channel negative and revocation tests on installed Core/Fleet still needed |
| **Relationships, impressions, continuity** | `src/sofia/core/rel/store.py`, `src/sofia/core/personality/reflection.py`, `src/sofia/platform/application/emotional_conversation.py`; `src/sofia/platform/application/bootstrap.py` wires relationship, impression, repair and reflection facilities | **SOURCE EXISTS / PARTLY WIRED** | Stable roleplay-personality expression and session-to-session relationship nuance require observable live-model evidence |
| **Autobiographical memory, reviewed episodic retrieval and restart** | `src/sofia/core/memory/{system,autobiography}.py`; `src/sofia/platform/application/{conversation_service,conversation_learning}.py`; `test/test_application_restart_continuity.py` and Team 3 disposable continuity tests. Autobiography and conversation prompts are bounded and principal-scoped | **SOURCE EXISTS and application wiring observed** | Dedicated *fictional scene* continuity/retrieval not demonstrated; `conversation_learning.py` explicitly prevents roleplay from automatically becoming real-world memory (correct safeguard). Reuse existing stores with typed fiction provenance; never write fictional plot into canonical autobiography |
| **Conversational / physical-representational interaction** | `src/sofia/modules/interaction/{chat,core,decision_expression}.py` implements guarded conversation, represented gesture grounding, stopped-session checks, and expressive response controls | **SOURCE EXISTS / wired conversation subclass** | Natural multi-turn self-initiated fictional scene progression, user-selectable initiative level and non-repetitiveness not demonstrated |
| **Proactive initiative / outreach** | `src/sofia/platform/application/presence.py` defines `PresenceInitiativeEngine` and `InitiativeEvent`; bootstrapped by `SofiaApplication` with source-backed ACT; `src/sofia/platform/application/background_runtime.py` has bounded ACT bridging. `PROJECT_GAP_REPORT.md` §32 identifies a *separate* canonical conversation initiative planner as not production-wired | **EXISTING outreach/presence service** but not demonstrated as RP scene controller | Reuse existing control/STOP/dedup/cooldown primitives and add in-chat optional initiative within the Core interaction pipeline; do not turn RP into unsolicited external messages. The historical `CanonicalInitiativePlanner` symbol cited by the gap report was *not found* in current `src/sofia/interaction/initiative.py` or `src/sofia/modules/interaction/initiative.py` on main, so do **not** assert that class is currently present |
| **OPEN / low-refusal model route** | `src/sofia/core/cognition/routing.py` defines `CognitiveRoute.OPEN`; explicit `open mode`, `uncensored model`, `secondary model` text markers may select OPEN when tools are absent, with routing still constrained by Matrix route hints and reviewed interaction logic | **SOURCE EXISTS** | Verify actual configured, available OPEN engine/model and private-context route, avoid brittle keyword-based RP classification and unauthorized model downloads; benchmark model behavior |
| **Free local RP inference quality / GPU fit** | Local Ollama adapter and routing infrastructure documented in `docs/development/CORE_002_OLLAMA_REAL_INFERENCE_AUDIT_20261108.md` | **SOURCE EXISTS; live quality NOT VERIFIED** | No measured Rocinante vs Huihui 30–50-turn roleplay A/B, VRAM/context test, or sustained real Ollama Core conversation accepted |

### Evidence limitations and exact next work

- As of Team 3's **2026-11-08** audit (`docs/development/CORE_TEAM3_IDENTITY_MEMORY_AUDIT_2026-11-08.md`), identity/memory source inspection exists but its fresh cross-store test execution was **UNVERIFIED**; G8 real-host acceptance was reported **0/16**. This is a dated team snapshot, not a freshly recomputed current gate status.
- As of Team 2's **2026-11-08** note (`docs/development/CORE_002_OLLAMA_REAL_INFERENCE_AUDIT_20261108.md`), a sustained real-Ollama Core conversation was **NOT RUN / NOT ACCEPTED**. Mock or source tests must never be described as real-model quality evidence.
- `test/test_romance_preferences.py` includes a test capturing a romance-preference SYSTEM context in a private model request, but **this inspection did not run pytest**.
- Any proposal to add new RP-specific modules in §3 is now **conditional**: first check whether an extension of existing `InteractiveConversationService`, `ConversationService`, `PresenceInitiativeEngine`, `MemorySystem`, `RomancePreferenceService` and `CognitiveRoutingPolicy` meets the requirement.
- Do not change constitutional authority, adult permission policy or memory admission to improve fictional prose.

### Delta-only implementation and verification backlog (to propose after approval)

1. **RP-C01, audit production route**: Trace one authenticated private conversation through existing Matrix, adult authority, `InteractiveConversationService`, romance context, emotional state, memory retrieval and OPEN routing; record effective model and missing context in non-sensitive diagnostics.
2. **RP-C02, fictional scene continuity**: Add or adapt an owner-private, session-scoped *fictional* episode/scene recap projection using existing conversation and reviewed-memory provenance, with no promotion to real autobiography, cross-audience access or second canonical memory writer. Preserve corrections, deletions and STOP.
3. **RP-C03, in-conversation initiative**: Extend existing interaction/goal/Presence primitives for bounded scene questions, natural topic starts and respectful story progression. Differentiate quiet/balanced/proactive levels from external ACT outreach; inherit consent/boundary checks and no-autosend default.
4. **RP-C04, private model role selection**: Extend existing `CognitiveRoute.OPEN` and AG-D005 model role configuration, not a new router. Explicit private-local host/model approval and immutable Core identity, with an honest unavailable/error path.
5. **RP-C05, test wiring before new code**: Run existing `test/test_romance_preferences.py`, `test/test_application_restart_continuity.py`, emotion/permission/interaction/Presence suites on the intended commit and document failures. Repair actual gaps without blanket rewrites.
6. **RP-C06, real A/B and lifecycle**: With separate owner authorization, run identical 30–50 turn adult-appropriate fictional scripts on the actual 12GB Venus GPU (existing Huihui vs approved Rocinante), with restart/recall, private/shared leakage denials, explicit refusals vs false refusals, voice optionality, model cold/warm unload and gaming-first pressure. Release readiness remains gated on **verified** installed-host evidence.

**Decision:** AG-D033 is principally an **integration/behavior verification and small-delta enhancement** effort, **not** a greenfield Sofía adult Core design. It remains CAPTURED / NOT SCHEDULED, and does not change Platform 1.0 or Core 1.0 GO gates.

## 8. AG-D030 owner-specific 3+1 model selection crosswalk (2026-11-09)

The owner requested **3 primary candidates plus 1 alternative per local category**. The canonical nine-category 3+1 inventory is in [AG-D030 § Owner-specific 3+1 shortlist](AG_D030_AI_MODEL_LANDSCAPE_2026-11-09.md). **For roleplay on Venus:** #1 Rocinante-X 12B Q4, #2 existing Huihui-Qwen3.5 9B abliterated, #3 Stheno 3.2 8B Q4, alternate Magnum v4 12B Q4. Anubis Mini remains a *researched but not prioritized* candidate in §1, not part of the owner’s requested four-model shortlist.

**Delta-only Core work remains**: reuse romance preferences, emotional journal, relationships, private/consent audience guard, owner-only reviewed memory/autobiography, represented interaction and existing `CognitiveRoute.OPEN`. Extend/verify *in-conversation* initiative and scene recall instead of a second adult Sofía or second authority. **No Core coding, test execution, installed-host inference or model changes were authorized/completed by this table update.** This is a new ranking of candidates, not results from actual 12GB GPU benchmarks.
