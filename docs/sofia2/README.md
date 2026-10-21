# Sofía 2.0: architecture and development home

**Status:** owner-directed architecture and planning baseline, October 21, 2026. This document does not certify production implementation or tests.

Sofía 2.0 is the new product generation. Sofía V18 and earlier code are the proof-of-concept foundation, not a disposable repository. Sofía Core 1.0 is the portable persistent personal foundation. A governed runtime platform supplies authority, persistence, recovery and module lifecycle. Modules supply capabilities and presentation channels.

## Read in this order

1. [Architecture](ARCHITECTURE.md): responsibilities, runtime boundaries, core-versus-module decisions and failure isolation.
2. [Core 1.0 plan](CORE_1_0_PLAN.md): CORE-01–40 feature inventory, CORE-B00–B08 development sequence and acceptance.
3. [Non-Core plan](NON_CORE_MODULE_PLAN.md): specific platform, bundled release and optional modules; interfaces, safety, sequencing and acceptance.
4. [780-task integration](UNIFIED_780_PLAN.md): preserve the original CA/ML/GA requirements while mapping them to Sofía 2.0 owners.
5. [Development workflow](DEVELOPMENT_WORKFLOW.md): local OpenCode execution, snapshots, safe merges, evidence and owner-controlled release.

## Product and ownership

| Layer | Responsibility | Intended initial delivery |
| --- | --- | --- |
| Sofía Core 1.0 | identity, cognition, memory, personality, modeled emotions, relationships, interests, agency and evaluation | Core B00–B08 |
| Runtime platform | canonical writer, application lifecycle, SAFE authority, RUN job execution, module manager, versioned updates, recovery and observability | required foundation |
| Bundled companion modules | desktop chat, Discord bridge, 2D fox avatar and approved expression surfaces | Sofía 2.0 companion release |
| Optional modules | speech, research, art, development execution, homelab, robotics, trains, games, mobile and experiments | staged independent releases |

**Design distinction:** the Core may express a need for a capability, but it does not acquire permission to execute that capability. The verified capability gateway, SAFE, RUN and external release supervisor retain their existing authority.

## Governing sources

- [Original 780-task inventory](../Sofia_V18_700_Tasks_Brief_Table.md), containing 700 CA + 40 ML + 40 GA original IDs.
- [Five-level evidence standard](../development/V18_TASK_STATUS_STANDARD.md), governing source/test/CI claims.
- [Existing companion autonomy contract](../development/companion-autonomy-contract.md), specifying the sole canonical writer, Cognition V2, audience separation and execution receipts.
- [Existing OpenCode integration](../development/opencode.md), specifying development-adapter authority boundaries.
- [Constitution](../../src/sofia/constitution/constitution.md), which is not amended by these plans.

## Development control

OpenCode is the primary local implementation agent. The owner periodically reviews and pushes coherent checkpoints to GitHub `main`. Local uncommitted OpenCode/Codex changes are not presumed to be in GitHub. Architectural documentation can be updated independently, but agent work must reconcile upstream changes safely. No agent gets blanket permission to deploy, restart production, alter the Constitution, change canonical database ownership, or publish code.

**Not a migration instruction:** existing deployments, writer ownership, state schema and release controls remain unchanged until independently tested and explicitly authorized.

## Decisions and unresolved questions

- Agreed: all 780 prior task IDs become part of Sofía 2.0 development, mapped to a primary owner; no parallel competing roadmap.
- Agreed: develop all Core batches B00 through B08 from requirements, independently verifying reused proof-of-concept code.
- Agreed: Core-34 (account-free multi-person familiarity) is deferred until after Core 1.0.
- Default: release includes a working desktop, Discord and 2D fox avatar experience. Optional voice availability depends on real quality/receipt evidence.
- To decide before implementation: initial optional module priority, exact production platform scope for releases, module distribution/signing process, and whether first-release voice is mandatory.

## Definition of success

Core and platform are integrated, privacy- and authority-correct, recoverable and independently testable; bundled channels use shared canonical services without duplicating identity. Optional modules can be missing or fail without corrupting personal history. All 780 original task IDs have a traceable destination and retained acceptance requirements. Completion counts are based only on executed evidence.
