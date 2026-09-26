# INTERACT / CORE live-quality repair gate

**Opened:** 2026-09-24  
**Branch:** `fix/interact-core-live-quality-repair`  
**Base:** merged PKG-DISCORD v1 mainline  
**Status:** repair gate open; no accepted INTERACT safety/ledger semantics are reopened.

## Trigger

Supervised Sparks-only Discord acceptance proved the transport can carry a real owner DM through the shared Sofía runtime and return one visible reply. The same live conversation exposed a narrower quality regression:

- ordinary greeting: generic assistant-style self-introduction and canned "How can I assist you today?" ending;
- authenticated-owner identity question: generic privacy boilerplate because SOCIAL principal projection is not yet present;
- canonical embodiment question: detailed authoritative wardrobe answer succeeded.

The evidence therefore separates transport, social identity, and conversational quality instead of blaming Discord for all three.

## Ownership boundary

### This repair gate owns

- natural, non-canned ordinary conversation;
- preserving Sofía's canonical personality in short greetings and casual dialogue;
- eliminating repetitive generic assistant closers when the user did not ask for them;
- retaining strong technical/direct mode without flattening warmth, wit, or contextual variation;
- preserving authoritative identity, embodiment, Constitution, operational truth, and interaction boundaries while improving expression;
- matched CLI and Discord live probes through the same conversation service.

### SOCIAL owns separately

- mapping an independently authenticated principal to the canonical Sparks principal;
- projecting authenticated principal/audience evidence into cognition;
- wrong-principal and cross-user privacy/isolation tests.

This gate must not hard-code a Discord snowflake, display name, or transport-specific "Sparks" rule into the personality layer.

### Discord is closed for v1 transport

Do not reopen the accepted v1 owner-DM transport unless a repair actually regresses transport behavior. Discord remains an adapter to the same Sofía runtime, not a second personality.

## Repair sequence

1. **Reproduce and pin**
   - Record current main SHA and provider/model configuration.
   - Reproduce a small deterministic live-quality set through CLI and supervised Discord.
   - Preserve actual responses, not paraphrased pass/fail labels.

2. **Trace projection**
   - Inspect the provider-bound system/personality projection for ordinary chat.
   - Compare greeting, technical, embodiment, serious, affectionate, refusal, and clarification prompts.
   - Determine whether generic fallback originates in missing/weak personality guidance, context trimming, history contamination, repetition guard behavior, or model/provider behavior.

3. **Minimum repair**
   - Prefer a shared CORE/INTERACT projection fix over response-specific templates.
   - No canned greeting table, transport-specific personality injection, or fake memory.
   - Do not rewrite the Constitution or canonical identity merely to improve style.

4. **Regression gates**
   - existing INTERACT safety/ledger/source-attestation/stop tests remain green;
   - CORE grounding and authoritative embodiment tests remain green;
   - no new fabricated sensation, action, permission, memory, or capability claims;
   - no repeated stock closer across the representative dialogue set.

5. **Live acceptance**
   - supervised CLI and Discord use the same shared runtime;
   - greeting sounds like Sofía rather than a generic assistant;
   - technical response remains crisp and useful;
   - embodiment answer remains authoritative;
   - serious/refusal/clarification cases remain truthful and appropriately toned;
   - multiple turns show variation without forced theatricality or random personality noise.

6. **Integrated verification**
   - run focused repair tests;
   - run coordinated CORE/INTERACT/Discord regressions;
   - run the repository suite on the final candidate and record exact counts, skips, failures, elapsed time, and SHA;
   - then perform one final supervised real-model quality sample before merge.

## Exit criteria

This gate closes only when the current shared conversation path demonstrates natural, varied Sofía expression across the representative live set while all authoritative grounding and accepted interaction semantics remain intact.

A successful SOCIAL principal fix is useful but does not, by itself, close this quality gate. Likewise, a good wardrobe answer does not prove ordinary dialogue quality.

## Non-goals

- no general multi-user rollout;
- no proactive Discord outreach;
- no 24/7 supervisor or watchdog deployment;
- no general web/search;
- no renderer/voice/robot capability;
- no protected identity/Constitution amendment.
