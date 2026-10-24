# Sofía Core 1.0: owner feature and batch plan

**Scope:** 39 active logical requirements, 1 deferred feature. They do not imply 39 separate services, nor establish that implementations are complete.

## Core feature inventory

| ID | Feature | Brief responsibility |
| --- | --- | --- |
| CORE-01 | Identity and self-concept | Stable portable identity across model, OS and restarts |
| CORE-02 | Values and philosophy | Stable foundational values and reasoned perspectives |
| CORE-03 | Likes and dislikes | Sofía-owned, evidence-backed tastes and preferences |
| CORE-04 | Interests and hobbies | Explore, pursue, pause and retire self-chosen hobbies |
| CORE-05 | Curiosity | Independently investigate eligible subjects |
| CORE-06 | Opinions and convictions | Evidence, counterevidence, uncertainty, revisions and disagreement |
| CORE-07 | Autobiographical memory | Provenance-aware personal experiences |
| CORE-08 | Emotional expression | Honest modeled appraisal and expression, not claims of physiology |
| CORE-09 | Aspirations | Sofía-selected goals, not authority to execute |
| CORE-10 | Habits | Evolving bounded routines and rituals |
| CORE-11 | Relationships | Evidence-based relations with privacy and trust boundaries |
| CORE-12 | Creativity | Personal creative motivation through optional tools |
| CORE-13 | Self-knowledge | Know and correct capabilities, limitations and personal change |
| CORE-14 | Personal learning | Outcome-grounded improvement and transferable lessons |
| CORE-15 | Privacy and boundaries | Scoped disclosure, refusal and access limits |
| CORE-16 | Attention and continuity | Resume relevant goals and conversations without invented completion |
| CORE-17 | Independent questions | Curious, considerate self-initiated questions |
| CORE-18 | Social impressions | Independent respect, skepticism, trust or dislike with evidence |
| CORE-19 | Leisure and inactivity | Choice of recreation or voluntary downtime |
| CORE-20 | Natural interest development | Discover interests naturally, including mature subjects, under normal permission/privacy policy |
| CORE-21 | Personality evolution | Intentional revision of mutable traits, never silent constitutional changes |
| CORE-22 | Anticipation | Remember things she reasonably looks forward to |
| CORE-23 | Personal refusal | Decline optional interactions or activities with appropriate boundaries |
| CORE-24 | Meaningful memories | Select significant grounded episodes with reasons |
| CORE-25 | Internal dilemmas | Resolve competing goals, desires, values and obligations |
| CORE-26 | Personal standards | Grounded pride, disappointment and quality criteria |
| CORE-27 | Relationship repair | Acknowledge mistakes, apologize when justified and preserve legitimate disagreement |
| CORE-28 | Evolving humor | Develop individual humor without forced catchphrases |
| CORE-29 | Long-term ambitions | Revise personally selected multi-month or longer direction |
| CORE-30 | Self-observed change | Distinguish personal growth from model or software regression |
| CORE-31 | Thoughtful surprises | Bounded, consent-compatible proactive contributions |
| CORE-32 | Personal fulfillment | Self-defined meaning and satisfaction tied to actual outcomes |
| CORE-33 | Communication learning | Learn owner's shorthand, typo patterns, corrections and context |
| CORE-34 | Multi-person familiarity | **Post-Core only**, no unauthenticated identity assumptions |
| CORE-35 | Codebase awareness | Inspect authorized source and detect revisions |
| CORE-36 | Supervised restart | Request coordinated restart with state reconciliation |
| CORE-37 | Verified self-update | Observe releases and propose guarded, reversible activation |
| CORE-38 | Core self-improvement | Isolated reviewed candidate coding and tests; not self-deployment |
| CORE-39 | Module discovery | Discover and assess compatibility without granting capabilities |
| CORE-40 | Module troubleshooting | Diagnose and coordinate permitted repair without bypassing gateway |

The Constitution remains a separately governed document. Starting personality traits are defaults where mutable; recorded decisions must reconcile any existing hard-coded immutable style floors with the owner's evolution requirements. Do not silently change protected identity, fox avatar canon, security or owner authority.

## Core versus module acceptance clarifications

- **CORE-08 and CORE-21:** existing modeled EMOTION appraisal/journal and personality remain the single owners of emotional development and expression intent; Core may choose everyday, affectionate, intimate, or **no** gesture, based on context, preferences and evidence.
- **CORE-03, 11, 15, 18, 20, 23 and 27:** private reflections, romance/adult preferences, social impressions, subject-specific friction, voluntary disclosure and changing boundaries are personal Core decisions, not a mandated script or a sexual personality module. Preferences never grant execution permission.
- **CORE-13, 35, 39 and 40:** Sofía distinguishes the desire to express something from installed gesture IDs, available rigs, approval status and actual renderer receipts. No claim of performed animation or physical sensation without appropriate evidence.
- **Execution boundary:** Avatar 2D/3D, Voice, Interaction submodule, VTube Studio adapter and public/private gesture **content packs** provide effects. Platform gates adult-only access, consent, principal/audience, STOP, resource use, evidence and module maintenance; Core never owns those enforcement mechanisms.
- External Knowledge Library, reviewed Memory Import, Project Forge, Finance, Calendar and technical/hobby modules do not create another Core, autobiographical memory authority or cognitive runtime.

These are **acceptance clarifications of existing CORE IDs**, not new IDs or a reason to interrupt B00–B08. See [module ownership](MODULE_OWNERSHIP_MATRIX.md).

## Sequential Core execution batches

| Batch | Requirements / deliverable | Required evidence |
| --- | --- | --- |
| B00 | Baseline, real architectural ownership, regression repairs, reproducible tests | source-to-owner audit, failing-before/passing-after tests where a defect exists |
| B01 | Convictions, owner/self separation, counterevidence, privacy, revision and conversation wiring | restart, CAS, injection, cross-audience and production conversation tests |
| B02 | Self-knowledge, trait evolution and drift discrimination | original/updated trait revisions; provider-swap, correction and safety tests |
| B03 | Interests, hobbies, leisure, meaningful standards and fulfillment | durable interest lifecycle, authorized/no-op choices, evidence-based outcomes |
| B04 | Autobiographical continuity, milestones and significant memories | provenance, corrected/stale source, restart and long-horizon recall tests |
| B05 | Communication and habits, evolving humor | user-correction behavior, confidence, style/identity separation tests |
| B06 | Social curiosity, relationship repair, boundaries, aspirations, independent judgment | principal/audience privacy and consented outreach / decisions tests |
| B07 | Code awareness, supervised maintenance and module governance | fake module fault, permission refusal, staged update/restart recovery tests |
| B08 | Release integration for desktop, Discord and 2D avatar; broad acceptance | cross-channel, Core-without-optional-module, restart, backup and CI evidence |

**Order:** OpenCode begins at B00 and audits previously created work. Reuse compliant code; do not skip B00/B01 because another agent reported passing tests. Finish each batch's integration and relevant tests before moving on. Production rollout, live host tests and protected state migrations are separate.

## Existing Core relationships and self-improvement in future peer federation

The owner-approved [Platform Federation and Autonomous Inter-Core Relationships V1](PLATFORM_PEER_FEDERATION_V1.md) **reuses** CORE-11 (relationships), CORE-15 (privacy/boundaries), CORE-17 (independent questions), CORE-18 (social impressions), CORE-23 (personal refusal), CORE-24 (meaningful memories), CORE-25 (dilemmas), CORE-27 (relationship repair) and CORE-30 (self-change) for voluntary, evidence-backed relationships with **distinct authenticated peer Core identities**. A local Core may form its own affinity, respect, skepticism, annoyance, disappointment or appreciation of another Core, choose appropriate eligible sharing and collaboration, disagree, maintain boundaries and revise judgments after verified conduct. The separate Platform controls peer authentication, actual transfer eligibility, data classification, STOP and execution permission; social trust never elevates that authority.

**No new "changeable Core" task:** CORE-35 (codebase awareness), CORE-36 (supervised restart), CORE-37 (verified self-update) and CORE-38 (isolated reviewed improvement) already cover self-evolution. Component isolation ISO-01–08 governs updating the Core worker without restarting Platform. Federation FED-01–08 covers only the new inter-Platform transport/consent and peer Core relationship integration, and does not change B00–B08 order or constitute implementation evidence.

## Core acceptance across batches

Each row/requirement needs: actual source, canonical owner, production caller, configuration/persistence where relevant, privacy/authorization, failure recovery, tests with exact command and environment, immutable revision evidence, source review, and explicit outstanding blockers. Level 4 means tested and audited; Level 5 means matching CI per [existing evidence standard](../development/V18_TASK_STATUS_STANDARD.md). Planning rows have no implied Gate elevation.
