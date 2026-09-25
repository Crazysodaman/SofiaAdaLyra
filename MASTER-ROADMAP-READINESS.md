> **Project status update — 2026-09-24:** PKG-DISCORD v1 is live accepted for the supervised Sparks-only private-DM transport path and merged to `main` via PR #64 (`ba2111b`). A new INTERACT/CORE live-quality repair gate is open for generic/canned conversational fallback discovered through that channel; accepted INTERACT safety semantics remain intact. SOCIAL minimum principal projection also remains open because transport authentication is not yet carried into cognition as `Sparks`.

# Sofía Ada Lyra | master readiness index

**Updated:** 2026-09-24 (America/Chicago). **Status:** documentation and implementation-state index, not evidence of deployed capability. PR #1 and the roadmap reconciliation PR #4 are merged. The package roster remains **19 packages**; no package #20 is created for the watchdog or replicated databases.

## Authoritative planning and acceptance documents

1. [ROADMAP.md](ROADMAP.md): canonical 19-package roster, invariant release order, package ownership and fleet/removal constraints.
2. [Full roadmap and individual package contracts](docs/development/FULL-PACKAGE-ROADMAP-2026-09-22.md): expanded 19-package scope, dependencies, current status, proposed deliverables, acceptance criteria, milestones and next engineering order.
3. [Six reliability gates and state replication](docs/development/pkg-reliability-control-plane-contract.md): recovery, operation ledger, operator stop/approval, resource fairness, failure lab, capability truth, replication/fencing/backup.
4. [Reliability implementation stages](docs/development/pkg-reliability-implementation-plan.md): recoverable SQLite baseline before any candidate database migration; staged proofs.
5. [RUN independent watchdog and standby recovery](docs/development/pkg-run-watchdog-failover-contract.md): local supervisor, independent monitor, fenced leader promotion, standby startup, rejoin and failure acceptance.
6. Package-specific branch docs, PRs and revision-pinned tests: implementation evidence, not an excuse to combine unrelated test runs.

**Primary release path:** CORE → INTERACT → MEM → SOCIAL minimum Sparks-only principal/audience → Discord D0-D4 through NET + UI + SAFE → OPS trusted host telemetry/enrollment → RUN verified supervised 24/7 and applicable recovery/failover → later separately authorized general web/search.

**SAFE + VERIFY are continuous gates.** KNOW/INTEGRATE/REL/ACT/AVATAR/DEV/BODY/EVOLVE/CLEAN can proceed in parallel without bypassing release, privacy or authority gates. Reading local authorized documentation does not grant web browsing. Discord connectivity is not a general web grant.

## Status definitions

- **Merged foundation:** code is on `main`, but real-host or integrated acceptance may remain.
- **Draft candidate:** code is on a feature branch/PR, not merged to `main`.
- **Design-only:** a documented outcome/contract, with no certified corresponding deployed behavior.
- **Offline tested:** a particular isolated revision passed; not proof of current Windows/full-suite/live behavior.
- **Integrated:** tested against the actual intended repository revision and dependencies.
- **Live accepted:** witnessed real component/system behavior at a pinned revision with appropriate receipts.
- **Released/deployed:** separately approved activation/deployment, distinct from merged docs or source.

Never combine test counts from unrelated revisions into a fictional mega-pass. Reconfirm actual PR heads, CI and live evidence before changing these states.

## Per-package readiness and immediate next gate

| Order | Package | Current evidence-based location/status | Next gate |
| ---: | --- | --- | --- |
| 1 | CORE | Foundations merged via PR #1 | Joint INTERACT/CORE live-quality repair for generic assistant fallback, then fresh integrated identity/personality/restart/latency evidence. |
| 2 | INTERACT | **Accepted foundation merged via PR #2 plus accepted hardening via PR #29** | New narrow live-quality repair gate with CORE for natural/non-canned dialogue; accepted interaction safety/ledger semantics remain closed. |
| 3 | MEM | SQLite foundations on `main`; original retrieval preflight draft PR #9 | Durable originals, provenance, privacy, consistent cross-store backup and independent restore. |
| 4 | SOCIAL | Minimum principal/audience boundary designed; live Discord proved transport auth but missing cognition projection | Project the authenticated owner as Sparks in shared cognition and add negative cross-user/audience leakage tests. |
| 5 | NET | Distributed foundations on `main`; narrow Discord private-DM transport live accepted | Broader DNS/TLS/redirect/remote-host enforcement; no general web. |
| 6 | UI | Workbench prototype draft PR #6; Sparks-only Discord DM adapter live accepted for v1 transport | Keep Discord narrow while desktop/web/mobile/voice/renderer and proactive outbound remain separately gated. |
| 7 | RUN | Periodic-opportunity candidate draft PR #3; no certified OS supervisor/24-7/HA | OS supervision and independent watchdog; safe standby startup, exclusive lease/fencing, ledger reconciliation, multi-day soak and measured host-failover proof. |
| 8 | OPS | Read-only inspection foundations on `main`; fleet agent/orchestration contract only | Trusted cross-platform enrollment/telemetry, measured capacity, maintenance and compatible workload relocation, failover/rollback, Sparks-only final machine-removal approval. |
| 9 | ACT | Unsent outbox/reflection foundations on `main`, outreach preflight draft PR #15 | One durable scheduler/outbox ledger, consent/quiet/stop and actual delivery receipt. |
| 10 | REL | Overlapping absence/reunion candidates draft PRs #12/#13 | Reconcile one evidence-grounded, scoped and non-clingy relationship pipeline. |
| 11 | AVATAR | Offline asset/tooling candidate draft PR #7 | Rig/renderer/hit-test/animation receipt and accessible text fallback. |
| 12 | DEV | Proposal preflight draft PR #17 | Trusted OpenCode execution, scoped changes, tests and rollback; doc-grounded candidate tool creation. |
| 13 | BODY | Simulation-only candidate draft PR #16 | Real Gaia SSC-32/calibration and independently verified hardware emergency stop. |
| 14 | EVOLVE | Protected amendment proposal preflight draft PR #19 | Reviewed independently authorized config/identity/Constitution changes; never self-approve. |
| 15 | CLEAN | Inventory/protected-path preflight draft PR #14 | Recovery-first state preservation, safe cleanup migration and rollback. |
| 16 | KNOW | Reading/provenance and document-authoring contracts on `main` | Real local/PDF/repo ingestion, source/version citations and privacy; scoped, reviewed documentation generation/upkeep. |
| 17 | INTEGRATE | General adapter foundations on `main`, package self-tooling design only | Typed live service adapter, truthful registry, KNOW→DEV→SAFE/VERIFY→scoped activation→rollback proof. |
| Gate | SAFE | Authority/integrity foundations; disclosure preflight draft PR #18 | Real identity, secrets, revocation, independent stop, backups/restore, fencing and protected exact-device approvals. |
| Gate | VERIFY | Active candidate draft PR #8; PR #10 superseded | Current-revision live negative/security and failure tests, integrated suite, restore, latency, RPO/RTO and soak evidence. |

## Named workstreams, not extra packages

- **Discord D0-D4:** initial scope is authenticated Sparks-only private DM; no public guild/multi-user access implied. See [full roadmap](docs/development/FULL-PACKAGE-ROADMAP-2026-09-22.md).
- **Two data locations:** proposed single writer plus synchronous data-bearing standby on independently verified failure domains, a separate quorum/fencing witness and third isolated/versioned backup. SQLite first gets state inventory, safe consistent backups and independent restore; PostgreSQL is only one future candidate after benchmark, migration, and separate activation approval. Synchronous replication does not protect against replicated deletion/corruption.
- **Watchdog and standby:** local supervisor restarts local process; independent fleet monitor detects host failure; compatible standby supervisor starts a replacement only after exclusive leader fencing and durable-state validation. If exclusivity, quorum or data is uncertain, fail closed rather than boot two leaders. A witness is not a data copy. Two VMs on Artemis are not independent physical failure domains.
- **Operator authority:** Sparks can independently stop automation, pin hosts/workloads and prohibit reboots. Sofía may quarantine/drain/prepare a machine, but **only Sparks explicitly approves final removal of that exact device and proposal revision**.
- **General web/search:** only after genuine Discord, OPS deployment-host and RUN 24/7 acceptance, with distinct authorization and provenance.

## Reconciliation notes

- PR #1 merged on 2026-09-20; older documents still describing it as open are historical.
- PR #2 merged on 2026-09-23 after Windows closure evidence: 97 focused, disposable real-Qwen four-turn pass, qualified repository 1665 passed / 2 skipped / 1 unrelated local test deselected, and final 60/60 closure audit.
- REL PRs #12/#13 overlap; reconcile them before merging both paths.
- VERIFY PR #8 is active; #10 is superseded/closed.
- Discord and watchdog/replication are cross-package workstreams, **not twentieth/twenty-first packages**.
- Runtime SQLite files and logs tracked by Git must be preserved and deliberately migrated under SAFE/CLEAN; never delete state just to tidy Git.

**A roadmap, unit test, mock transport, model statement or documentation-only merge is not proof of 24/7 operation, standby promotion, acknowledged-write RPO 0, or deployed high availability.**