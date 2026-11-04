# Module-Host Infrastructure Readiness (2026-11-03)

OpenCode Batch 2 shared-infrastructure report for the Codex module
integration handoff. All statements below are OBSERVED from this
repository at local `main` beyond checkpoint `50f70680` (unpushed work
at the time of writing), unless marked otherwise.

## Purpose

Prepare the existing Platform module infrastructure to receive
independently developed modules one at a time, and record which shared
contracts remain blocking and which modules can enter
release-candidate verification.

## Observed platform infrastructure (summary)

The module host is substantially complete; every behavior below is
pinned by existing tests without modification:

1. **Signed package contract** — `SignedModuleManifest` (schema v3),
   `VerifiedModulePackage`, `verify_module_package`
   (`src/sofia/platform/modules/package.py`). Ed25519 verification with
   a caller-provided trusted key; package identity is a canonical
   digest over the unsigned document. 15 package pins plus 19 release
   provenance pins (`test_module_package_v1.py`,
   `test_optional_release_packages.py`).
2. **Readiness** — `evaluate_module_readiness` requires exact revision
   and matching-SHA CI + host acceptance for PRODUCTION_READY; health
   is never readiness; activation is never authorized by readiness
   (`src/sofia/platform/modules/readiness.py`,
   `test_module_readiness_v1.py`).
3. **Compatibility** — advisory report verified at activation time
   against exact module/package/profile identity and authoritative
   flag; duplicated independently by the operations coordinator before
   any authority use (`src/sofia/platform/modules/compatibility.py`,
   `src/sofia/platform/modules/lifecycle.py`, operations re-check at
   `src/sofia/platform/modules/operations.py`).
4. **Adapters** — `ReviewedAdapterFactory` contracts pin exact package
   digests, component ids, interface versions, profiles, resources and
   host bindings; resolution errors on zero or ambiguous ownership
   (`src/sofia/platform/modules/adapters.py`).
5. **Lifecycle** — 14-state durable state machine with CAS transitions,
   start/reconciliation demotions (`PAUSED`/`QUARANTINED` on runtime
   restart), immutable stage verification, compensation on failed
   commit (`src/sofia/platform/modules/lifecycle.py`,
   `test_module_lifecycle_v1.py`).
6. **Operations** — idempotency keys, exact-order outcome statuses
   (`FAILED_BEFORE_EXTERNAL_EFFECT` before any dispatch, onset
   `EXTERNAL_EFFECT_ATTEMPTED` around `adapter.start`), uncertain
   outcomes never replayed, verified probes within a bounded window
   (`src/sofia/platform/modules/operations.py`,
   `test_platform_module_operations.py`).
7. **Settings** — per-package contract-fenced settings with CAS
   revisions, idempotent authorization replay, LIVE/PENDING/UNKNOWN
   apply triage and truthful unknowns (`src/sofia/platform/modules/settings.py`,
   `test_platform_module_settings.py`).
8. **Host authority** — `LocalModuleAuthority` consumes one-use remote
   owner approvals hosted in a local state store, mirrors owner STOP,
   and returns to operator-blocked state only through the owner
   (`src/sofia/platform/application/host_authority.py`,
   `test_platform_module_host_local_state.py`).
9. **Observer / self-model** — read-only canonical observer with
   honest emptiness; outcome mapping only over terminal attempts; fixed
   cursors with no silent truncation (`src/sofia/platform/modules/observer.py`,
   `src/sofia/core/modreg/platform.py`, `test_platform_module_observer.py`,
   `test_module_awareness.py`).
10. **Fleet/tooling** — pinned-mTLS remote-fleet composition;
    observing host goal-dispatch effects
    (`SofiaApplication.reconcile_host_goal_dispatch` →
    `observe_goal_dispatch`) requires configured Fleet trust;
    without it reconciliation fails closed
    (`src/sofia/platform/distributed/capability.py::create_configured_remote_fleet_service`,
    `src/sofia/platform/application/bootstrap.py`).

## Services this batch changed

- Added a concurrency pin proving the capability system and adapter
  factory registry survive concurrent register/resolve usage
  (`test_platform_module_infra_concurrency.py`) backed by an
  `RLock` in `CapabilitySystem` (`src/sofia/platform/capability/system.py`)
  and `AdapterFactoryRegistry` (`src/sofia/platform/modules/adapters.py`).
  No authorization semantics changed; resolution and ownership error
  messages are unchanged.
- Added application-level restart-continuity pins
  (`test/test_application_restart_continuity.py`) securing reviewed
  memory, owner preferences and goal state across a restart, and
  fail-closed behavior of host reconciliation without configured remote
  trust.

## Shared contracts still blocking RC verification

OBSERVED. These decisions/resources live outside this repository's code
paths and need owner action:

1. **Trusted key distribution.** `verify_module_package` requires a
   `trusted_public_key`; publisher/reviewer keys are provisioned
   outside the repository (by design). Until the owner records which
   keys certify release-candidate modules, no signed package can be
   accepted through production gates.
2. **Exact-SHA CI per module package family on Windows and Debian**
   (G7 item 67). Module activation evidence must include
   `matching_ci` readiness evidence from the exact source revision on
   installed artifacts; this requires pushing reviewed state and
   running the CI families.
3. **Host acceptance path (G8)**. Readiness evidence for
   PRODUCTION_READY requires independent host acceptance; the runbook
   (`g8-shakedown-runbook-draft.md`) needs a live run and recorded
   receipts.
4. **Settings/lifecycle operator-stop read parity** (minor
   architecture decision). Settings activation consumes STOP inside
   the same SQLite transaction; lifecycle consumes it before the
   transaction. Replay remains impossible in both; parity is a design
   decision reserved for the owner.
5. **Codex module source integration flow.** Codex's 55-entry module
   development and audit pass (reported HEAD `9384535b`) is on an
   isolated unpushed branch and is NOT integrated; Platform contracts
   above are ready to review staged patches module-by-module when
   reviewed commits/patches are available.

## Modules that can enter release-candidate verification

OBSERVED platform surface allows any module package meeting the signed
manifest contract to proceed through:
discover/approve/stage/activate with guarded receipts, provided:

- signed reviewed package identity exists (Provenance materialization
  kit supports it: `src/sofia/modules/optional_release_packages.py`);
- a `ReviewedAdapterFactory` for the exact digest/component/profile
  is registered at composition;
- matching-SHA CI availability evidence is recorded in
  `ReadinessEvidenceStore` (blocked on item 2 above);
- host acceptance receipts follow G8 (item 3).

Module-count snapshot (names only, no internals read): 58 package
directories under `src/sofia/modules`: avatar, avatar3d, avatar_studio,
body, browser, cad, calendar, communications, creative_studio,
data_analytics, desktop_automation, development, digital_twin, discord,
documents, electronics, energy, engineering, file_watch, finance, games,
generalization, homelab, household, inference, integrate, integrations,
interaction, it_backup_dr, it_containers, it_database, it_devops,
it_helpdesk, it_network, it_observability, it_security, it_storage,
it_systems, knowledge_library, media, mentor_review, ml_evaluation,
mobile, neuro, printing3d, productivity, project_forge, remote_access,
research, robotics_gaia, sensors, smart_home, trains, ui, virtual_world,
vision, voice, workshop.

None of these are granted release-candidate status by this report;
RC status is claimed only after items 1-3 above.

## Commands

```
pytest -q test/test_platform_module_infra_concurrency.py \
          test/test_capability_system.py \
          test/test_platform_module_operations.py \
          test/test_module_lifecycle_v1.py \
          test/test_platform_module_settings.py \
          test/test_platform_module_command_service.py \
          test/test_platform_module_observer.py
# 66 passed
```
