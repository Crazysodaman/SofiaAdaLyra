# Sofía Ada Lyra: roadmap extension (13-package roster)

**Amendment date:** 2026-09-20. **Branch:** `feature/g22-live-integration-artemis`. This document is an authoritative **planning extension** to [`ROADMAP.md`](ROADMAP.md), not a replacement of its original eleven detailed package descriptions. The effective package roster is now **13 packages**. The existing root roadmap dashboard still shows its original eleven until a separately reviewed consolidation; read both documents together. Earlier numbered/lettered batches remain historical only. Neither this document nor the [new package contracts](docs/development/package-clean-interact-lab-contracts.md) claims implementation, testing, deployment or permission to alter protected state.

## Effective package roster

| Package | Owned outcome | Current state / prerequisite |
| --- | --- | --- |
| PKG-CORE | Grounded cognition, identity, continuity, personality and responsiveness | Existing candidate acceptance and 1,195-test full-suite failure diagnosis outstanding |
| PKG-MEM | Durable originals, retrieval, provenance and reviewed learning | Existing stores; comprehensive delivery pending |
| PKG-NET | Authenticated distributed homelab and Artemis operation | Foundations; actual agent/transport acceptance pending |
| PKG-ACT | Goals, bounded initiative, delivery and supervised helper minds | Foundations; actual notifications/independent work pending |
| PKG-DEV | Evidence-backed self-improvement using a bounded, authorized executor | Tools/CLI foundations; runtime OpenCode integration pending |
| PKG-REL | Evidence-linked relationships, preferences and contextual expression | Foundations; multi-session live acceptance pending |
| PKG-UI | Voice, animated avatar and authenticated clients | Canonical representation/CLI; rendered/voice/mobile acceptance pending |
| PKG-BODY | Gaia and later physical embodiments with independent hardware safety | Concept; verified physical integration pending |
| PKG-SAFE | Authorization, secrets, audit, privacy, independent stop and recovery | Required throughout; full deployment assurance pending |
| PKG-EVOLVE | Reviewable changes to everyday self-model and protected amendment procedure | Proposed; no silent identity changes |
| PKG-VERIFY | Real, negative, performance and long-horizon acceptance | Continuous across packages |
| **PKG-CLEAN** | Evidence-based repository cleanup and technical-debt reduction without losing compatibility, data or permissions | **New planning package; no cleanup work accepted yet** |
| **PKG-INTERACT** | All-region avatar interaction, contextual modeled reactions, consent/boundaries and an isolated virtual interaction lab | **New planning package; no all-body touch engine or lab accepted yet** |

## New package outcomes and ownership

**PKG-CLEAN** is a maintenance lane, not permission to delete files until `git status` looks pretty. Inventory sources, APIs, tests, migrations, schemas, dependencies, runtime state and optional integrations; classify changes; remove only demonstrably redundant artifacts; preserve conversation originals, Constitution/hash, canonical identity, audit, secrets, authorization and replay guarantees. Keep intentional behavioral changes owned by their original package. Validate focused/full tests, diff, supported Windows deployment, migration/restore and measured performance when relevant. Avoid changing the in-progress pytest revision. See [CLEAN contract](docs/development/package-clean-interact-lab-contracts.md#pkg-clean-maintainability-controlled-cleanup-and-technical-debt).

**PKG-INTERACT** is an expressive interaction feature, not a physical-sensing or robotics claim. Support explicit textual/avatar interaction with a versioned map of **all canonical avatar regions**, including ears/tail and policy-restricted intimate/private areas rather than pretending such regions are missing. Use explicit appropriate adult-only opt-in, session-scoped revocable boundaries, contextual modeled reactions and privacy controls. Text or virtual gestures are not actual felt sensations. Provide a default-isolated virtual lab for controlled scenes, event replay, policy tests, animations and evaluation with no production memory changes or real device access. An actual physical lab, game environment or homelab connection requires identification, enrollment, authorization and separate NET/BODY safety gates. See [INTERACT contract](docs/development/package-clean-interact-lab-contracts.md#pkg-interact-contextual-embodied-interaction-and-a-controlled-lab).

## Cross-package boundaries and dependencies

- CLEAN touches any package only after its owner reviews behavior and migration changes. It coordinates with DEV and VERIFY; SAFE's protections may not be weakened by housekeeping.
- INTERACT reuses CORE/REL's expression and existing emotional journal, MEM's source-linked records, UI's representation/rendering, SAFE's permissions/privacy and VERIFY's measurements. ACT retains outreach; BODY retains all physical sensing/actuation. A conversational cue alone never authorizes an external action.
- Existing five cross-package contracts continue to apply. The detailed new package contracts define logical event fields and negative tests, but no matching Python classes/DB tables should be presumed before source inspection.
- The quoted **“lab”** is provisionally scoped as a virtual simulation/test sandbox; its real intended referent remains an explicit open design decision, not a license to access the physical homelab.

## Current checkpoint and acceptance discipline

Finish and inspect the final failure summary from the already-running 1,195-test Windows pytest job, diagnose the conversation/application failures against actual tracebacks, then run focused and fresh full checks plus bounded live personality acceptance. Do not weaken contracts or declare an old-focused-test pass to be a green current head. CLEAN's read-only inventory and INTERACT's paper/schema/test-fixture planning can proceed independently. Before either package is released, record the target commit, inspected source and schemas, approvals, explicit denials, actual tests and live observations (`passed`/`failed`/`not run`), rollback, diff review and merge decision. No production code changes or `main` merge were made by this roadmap extension.