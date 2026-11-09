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
