# Sofía 2.0 | Original 700 CA tasks: Core / Platform / Module ownership crosswalk

**Source:** GitHub `main` fc8ca985ed02dcc00c2d12bc00188831e57cbe6e on 2026-11-02. **Scope:** all 700 original CA IDs, excluding the separate 40 ML and 40 GA addenda.

**The complete per-ID assignment lives in [V18_700_TASK_OWNER_CROSSWALK_2026-11-02.csv](V18_700_TASK_OWNER_CROSSWALK_2026-11-02.csv).** Each record has one primary architectural owner and explicit secondary dependencies. It also includes original task type, brief text, prior code-status, source anchor, disposition and owner/source alignment.

## Ownership assignment summary

| Layer | Assigned CA tasks | Responsibility |
|---|---:|---|
| Core | 222 | Identity, cognition, MEMORY, personality, emotions, LIFE/GOALS, relationships, interests and modeled initiative |
| Platform | 350 | Security, canonical state, RUN/ACT, release verification, model infrastructure, Fleet, resource and lifecycle control |
| Release modules | 33 | Desktop, Discord, 2D avatar, Voice and mobile presentation/transport |
| Optional modules | 95 | Workshop, DEV, creative tools, model adaptation, vision, robotics, trains, science and connectors |
| **Total** | **700** | **Exactly one primary architectural owner per original CA task** |

## Crosswalk by original roadmap phase

| Phase | Total | Core | Platform | Release module | Optional module |
|---|---:|---:|---:|---:|---:|
| 00 | 65 | 6 | 55 | 4 | 0 |
| 01 | 66 | 7 | 52 | 1 | 6 |
| 02 | 30 | 1 | 20 | 7 | 2 |
| 03 | 46 | 0 | 46 | 0 | 0 |
| 04 | 22 | 0 | 20 | 2 | 0 |
| 05 | 41 | 24 | 13 | 4 | 0 |
| 06 | 73 | 62 | 10 | 1 | 0 |
| 07 | 26 | 9 | 17 | 0 | 0 |
| 08 | 56 | 39 | 8 | 8 | 1 |
| 09 | 66 | 38 | 17 | 0 | 11 |
| 10 | 27 | 6 | 8 | 2 | 11 |
| 11 | 49 | 5 | 44 | 0 | 0 |
| 12 | 24 | 6 | 4 | 1 | 13 |
| 13 | 63 | 0 | 33 | 3 | 27 |
| 14 | 12 | 0 | 3 | 0 | 9 |
| 15 | 22 | 14 | 0 | 0 | 8 |
| 16 | 12 | 5 | 0 | 0 | 7 |

## What mapping *does* and *does not* prove

- This is a **complete architectural primary-owner assignment**, guided by the approved Core 1.0, PLAT-01–08, 55-entry module ownership matrix and original task wording. It is not an independent clause-by-clause verification of 700 production integrations.
- `source_anchor` is the source location *previously recorded* in audit #132, where available. It is **not automatically the correct architectural owner**, nor proof of full behavior. The repo has a `platform.application` composition root, and some code intentionally crosses layer boundaries.
- 128 previously recorded anchors occur in a different layer than the chosen architectural primary owner; see CSV `source_alignment=CROSS_LAYER_ANCHOR`. Each is a **review lead**, not an automatic defect or a request to move code. Do not infer that file location proves or disproves task ownership.
- **Coding states remain unchanged:** 118 source-evidenced coded, 189 partially traced, 390 not individually established, three owner-decision supersessions. Original audit: [#132](https://github.com/Crazysodaman/SofiaAdaLyra/issues/132). This is not a claim that 390 features are missing.
- The 118 previously source-coded CA IDs retain their **unchecked test/host verification** in [G8 #129](https://github.com/Crazysodaman/SofiaAdaLyra/issues/129). Do not waive pre-release CI/security requirements in GO LIVE [#120](https://github.com/Crazysodaman/SofiaAdaLyra/issues/120).
- Physical Core-free Platform installation, separately approved Core package and independent module lifecycle remain **G2 work**, not certified by the source namespace restructure.
- **Every Verify-class task has a technical owning layer** (Core, Platform, or a module). `Verify` is a work type, not a fifth runtime component. The Platform verification layer PLAT-08 may be a secondary dependency for its acceptance tests.

## Approved scope/disposition and replacements

- `SUPERSEDED`: CA-2906 (generic automatic VM creation), CA-2908 (NoCloud media), CA-2910 (New-VM/VHDX). Owner selected a pre-existing Hephaestus Hyper-V VM and verified unattended Debian ISO instead. Their original historical requirements are preserved; replacement threat and acceptance requirements remain active.
- `ADAPT_TO_HEPHAESTUS_V1`: CA-2907, CA-2912, CA-2917, CA-2920, CA-2921. Replace obsolete automatic-creation terminology with approved existing-VM handoff, signed media, SAFE-granted startup, evidence and recovery. Do not silently drop security/guest requirements.
- `DEFER_ADVANCED`: selected speculative C++ optimization, from-scratch/fine-tuning and neuroscience/consciousness investigations. These remain traceable but are not new GO LIVE blockers.
- `OPTIONAL_MODULE_QUEUE`: the owner remains recorded, but a standalone connector/hardware/research module has its own lifecycle and is not mandatory for first Core/Platform activation.
- `RETAIN`: keep applicable work under its current Core/Platform/release-module owner. `RETAIN` does **not** mean incomplete and does not reset recorded coding credit.

## Boundary examples

| CA ID | Primary owner | Other participants |
|---|---|---|
| CA-001 | CORE-16 | Platform evidence/state and RUN execution |
| CA-1208 | PLAT-03 | Core memory/relationship privacy |
| CA-3103 | PLAT-02 | Core canonical memory |
| CA-3112 | RM-VOICE / expression renderer | Core decides emotion/intent; Platform governs access |
| CA-501 | CORE-01 | Platform state and all presentation modules |
| CA-704 | CORE-16 | NEURO implementation and MEM eligibility; Platform state and scope |
| CA-1009 | MOD-TRAINS | Platform grant, Core hobby goals |
| CA-2906 | PLAT-07 (superseded) | Existing-VM Workshop handoff replaces auto-create |
| CA-6203 | MOD-VISION | Platform privacy/permission and local capture agent |
| CA-6704 | PLAT-03 | MOD-ML dataset access, Core memory consent |

## Owner decisions from the 2026-11-02 conversation, reconciled

**Identity and relationships:** One Sofía across all language models and all conversation types; no stand-alone adult persona or separate sexual preference engine. Her normal expression may be candid, humorous, skeptical, affectionate, outspoken and detailed on mature topics where appropriate. EMOTION, REL, MEM, Core preferences and voluntary boundaries interact contextually. She may initiate affection, flirtation and personal questions but may also decline, disagree or choose not to engage. Consensual fictional dominance/submission dynamics never confer real system authority.

**Memory and privacy:** Authorized intimate/private conversations may be remembered, retrieved and reflected on in appropriately scoped sessions without leaking to other audiences. Private reflection derivatives must obey provenance, correction, revocation and disclosure restrictions.

**Models and logical roles:** Initial *candidates*: (1) Qwen 3.5 9B for conversation and vision; (2) Gemma 3 4B for utility and independent evaluation; (3) Qwen 3 14B for coding and independent development; (4) existing Qwen 3.5 abliterated 4B for authorized private/adult conversation. That's **four physical models, seven reused roles**, not seven autonomous identities or seven always-resident models. Research, development, dialogue and critic are *workflows* using these roles, with independent source/receipt/test verification. No automatic grant, private-secret disclosure, or unsafe provider promotion because an LLM agrees with itself.

**Security and runtime:** Owner-held 256-bit authorization secret for protected permission actions; FIDO2 remains configured but disabled per the latest owner decision. Secret verification is host-owned and never passed into the model prompt. Canonical writer remains one; remote package and model switching must not clone Sofía. Implementations and G8 live evidence are distinct.

**Scope and coding-only counting:** Existing implementation counts as coding-complete when production requirements are satisfied; remaining testing is tracked in G8. Approved obsolete approaches can be retired with successor evidence. Do not turn unrelated optional research, Gaia/JMRI hardware, new kernel designs, automatic Hephaestus VM creation or model fine-tuning into GO LIVE blockers.

**Priority:** Current OpenCode work order is **G7-A first, audit-found fixes second, remaining G2 third**, then other release-development requirements, followed by separately approved G8 real-host shakedown. Previously planned self-knowledge, LIFE, self-maintenance, sandbox and autonomous interests are not new subsystems.

## Sources and review process

- [Original 700 task inventory](../Sofia_V18_700_Tasks_Brief_Table.md) and [verbatim master](../roadmaps/Sofia_Companion_Autonomy_Master_Roadmap_V18_Priority_Phases.md).
- [Core 1.0 plan](CORE_1_0_PLAN.md), [Platform/module catalog](PLATFORM_AND_MODULE_CATALOG_V1.md), [55-entry ownership matrix](MODULE_OWNERSHIP_MATRIX.md), [UNIFIED_780_PLAN](UNIFIED_780_PLAN.md), and [repo restructure owner inventory](../restructure/OWNERSHIP_INVENTORY.md).
- Audit [#132](https://github.com/Crazysodaman/SofiaAdaLyra/issues/132), G8 [#129](https://github.com/Crazysodaman/SofiaAdaLyra/issues/129), unified-personality backlog [#131](https://github.com/Crazysodaman/SofiaAdaLyra/issues/131), GO LIVE [#120](https://github.com/Crazysodaman/SofiaAdaLyra/issues/120).
- Before claiming *production ownership implemented*, inspect each task's producer, canonical state owner, composition, call site, receiving module/API, explicit grant, negative cases and exact source revision. Do not move code automatically based solely on the `source_alignment` field.
