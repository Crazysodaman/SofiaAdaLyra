# Sofía Ada Lyra | master readiness index

**Updated 2026-09-22. Draft PR #4; documentation-only and not merged/deployed.**

The proposed authoritative roadmap for this branch is now [ROADMAP.md](ROADMAP.md). It reconciles the old 13-package plan, the RUN proposal, and the SOCIAL/AVATAR additions into **one ordered 16-package roster**.

**Primary release path:** CORE → INTERACT → MEM → SOCIAL minimum principal/audience boundary → Discord D0–D4 using NET + UI + SAFE → RUN verified 24/7 operation → separately authorized general web/search.

**SAFE + VERIFY are continuous gates**, not late packages. REL/ACT/AVATAR/DEV/BODY/EVOLVE/CLEAN may advance in parallel when they do not bypass the primary release gates.

## Status definitions

- **Merged foundation:** code is on main, but live/integrated acceptance may still be open.
- **Draft candidate:** code exists on a feature branch/PR and is not merged.
- **Offline tested:** a focused slice ran in a stated isolated environment; this is not current Windows/full-suite/live acceptance.
- **Integrated:** tested against the actual intended repository revision and dependencies.
- **Live accepted:** witnessed real component/system behavior at a pinned revision.
- **Released/deployed:** separately approved merge/activation/deployment.

Never combine test counts from unrelated SHAs or branches into a fictional mega-pass.

## Ordered readiness index

| Order | Package/workstream | Current implementation location | Immediate next gate |
| ---: | --- | --- | --- |
| 1 | CORE | PR #1 merged | Fresh integrated suite + supervised startup/identity/personality/latency review after INTERACT stabilizes |
| 2 | INTERACT | Draft PR #2 | Current-head focused/coordinated tests, real-model decision/expression quality, then full-suite/review |
| 3 | MEM | Draft PR #9 | Durable original/provenance/privacy integration and restart retrieval |
| 4 | SOCIAL minimum | PR #4 design | Trusted Sparks principal/audience boundary only; general multi-user remains deferred |
| 5 | NET | Draft PR #11 + merged distributed foundations | Real Discord-scoped transport enforcement; Artemis remains separate; no general web |
| 6 | UI | Draft PR #6 plus future Discord adapter | Bind same Sofía runtime to authenticated DM/client and verify delivery/renderer receipts |
| 7 | RUN | Draft PR #3 | Real service/supervisor, restart/backoff, resource limits, multi-day supervised acceptance |
| 8 | ACT | Draft PR #15 + merged reflection/outbox foundations | One scheduler/outbox path, consent/quiet/stop, real delivery acknowledgement |
| 9 | REL | Draft PRs #12 and #13 | Reconcile to one absence/reunion pipeline using authenticated MEM evidence |
| 10 | AVATAR | Draft PR #7 | Continue offline asset/fit/rig work; real renderer/hit-test/ack later |
| 11 | DEV | Draft PR #17 | Trusted OpenCode executor + scoped test/rollback |
| 12 | BODY | Draft PR #16 | Real Gaia calibration, hardware watchdog and independent physical stop |
| 13 | EVOLVE | Draft PR #19 | Independently verified protected amendment workflow; never self-approve |
| 14 | CLEAN | Draft PR #14 | Real repo inventory and preservation plan before any deletion/migration |
| Gate | SAFE | Draft PR #18 + merged authority/integrity foundations | Trusted auth/privacy/secrets/recovery enforcement throughout |
| Gate | VERIFY | Draft PR #8 | Authenticated revision-pinned evidence and real/live negative tests throughout |
| Channel | Discord D0–D4 | Draft PR #5 + NET/UI/INTERACT/MEM/SAFE | Sparks-only authenticated private DM; no public/multi-user mode initially |
| Later | General web/search | Not implemented by design | Begins only after real Discord and verified RUN 24/7 acceptance |

## Current known reconciliation points

- PR #1 **merged on 2026-09-20**. Older documents saying it is open are stale.
- PR #2 remains the active INTERACT candidate and must not be declared green using older-SHA Windows results.
- PRs #12/#13 overlap. Choose one REL implementation path before integration.
- VERIFY PR #8 is active. PR #10 is superseded/closed.
- Discord is a cross-package channel workstream, **not package 17**.
- Search remains intentionally absent from the Discord NET milestone.
- Runtime SQLite/log artifacts currently tracked in the repository are a SAFE/CLEAN migration problem. Preserve first; do not delete state merely to make Git look tidy.

## Documentation hierarchy

1. [ROADMAP.md](ROADMAP.md): ordered package roster, release sequence, cross-package ownership.
2. This file: compact readiness/navigation index.
3. Package-specific readiness/review docs on each package branch: revision-specific implementation evidence.
4. Historical batch and earlier roadmap documents: archival context only.

A design document, passing isolated unit test, or persuasive model answer is not proof of a live capability.
