# Sofía 2.0 Platform takeover ledger

This is the recoverable evidence ledger for the reconciled Platform work. It
is not a release certificate or permission to deploy.

## Baseline

- Takeover checkout: `/workspace/SofiaAdaLyra-Takeover`
- Branch: `main`
- Source revision: `f3075b81ad00df878b7dc01f877a5113a8c67d67`
- Date/environment: 2026-10-24 UTC, Linux x86_64
- Historical Platform checkout: preserved dirty at `033a1bb7`, not reset or
  overwritten
- Historical Core checkout: preserved dirty at `af860fd8`, not reset or
  overwritten
- Production state and hosts: not opened, changed, restarted, enrolled, or
  migrated
- Publication: no commit or push; owner authorization remains required

## Reconciled implementation slices

| Scope | Canonical relocated owner | Implemented in takeover | Local evidence | Remaining acceptance |
| --- | --- | --- | --- | --- |
| PLAT-01 / SF-10 | `sofia.platform.run.components` | Dependency-aware component lifecycle, lease-bound writes, pause/quarantine and startup reconciliation | Included in 84-test Platform suite | Application/OS-host registration, Windows service evidence, fault campaign |
| PLAT-02 | `sofia.platform.state` | Atomic multi-record CAS, hash lineage, reviewed namespace/state facade and inert migration/restore plans | Included in 84-test Platform suite | Authorized restore exercise, distributed fencing, Windows/CI |
| PLAT-03 | `sofia.platform.safe` | SAFE facade and secrets-reference broker; no secret values exposed | Included in 84-test Platform suite | Full current-grant projection into Core, rotation/live authority acceptance |
| PLAT-04 | `sofia.platform.run.effects` | Durable effect envelope, exact idempotency, STOP and attestation recheck, explicit unknown/unverified/verified outcomes | Included in 84-test Platform suite | Production TaskExecutionManager registration and remote outcome acceptance |
| PLAT-05 / SF-08/12/13/16 | `sofia.platform.modules` | Signed non-executing package parser, immutable identity, dependency ranges, profiles, lifecycle, compatibility/readiness and canonical observer | Platform suite plus 61-test Core integration suite | Production lifecycle command facade, actual signed publisher package, sandbox and rollback exercise |
| PLAT-06 | `sofia.platform.cognition_compute` | Measured compute admission/reservation model and truthful route reports | Included in 84-test Platform suite | Real provider load/unload receipts and GPU/VRAM host evidence |
| PLAT-07 / SF-03/05/07/14 | `sofia.platform.ops` | Resource/device arbitration, bounded deterministic forecasting, migration replay refusal and startup recovery | **25 passed** OPS migration suite; resource/forecast tests in Platform suite | Distributed consensus, physical-device safety, real Fleet telemetry |
| PLAT-08 | `sofia.platform.modules.readiness` | Independent readiness projection over package, compatibility, lifecycle and evidence | Included in 84-test Platform suite | Exact-revision CI, independent review, release/rollback campaign |

The focused reconciled Platform command covering module package,
compatibility, lifecycle/readiness, compute, resources/forecast, component
supervision, effect broker, SAFE and atomic state services completed with
**84 passed** during the initial port. After Core integration and migration
repairs, the combined 15-module Platform/observer/OPS suite completed with
**98 passed** in 3.54 seconds. The focused OPS workload-migration
reconciliation command had separately completed with **25 passed**. These are
local test results, not CI or live-host proof.

Cross-layer regression evidence after restructure repairs:
`pytest -q -m 'pkg_core and not integration'` — **4,745 passed, 4 skipped,
2,229 deselected, 8 subtests passed** in 310.47 seconds on local Linux. The
run includes local mobile HTTP, pinned mTLS, and attended WebAuthn flows after
bounded loopback permission was granted. No external service or live host was
used.

Packaging acceptance: a clean local wheel build succeeded, installed into a
disposable target, and exposed all five required Core packaged assets plus
Avatar wardrobe and UI resources. Installed Platform/Application and Avatar
imports succeeded. The installed `python -m sofia` command reached its stable
launcher contract using an invalid-argument no-state check. Desktop, Discord,
Windows service, and real-provider host acceptance remain open.

## Canonical boundaries preserved

- All durable Platform metadata remains in the existing `sofia.db`; no
  secondary authority, identity, job, or module database was introduced.
- `CapabilitySystem`, SAFE/STOP and RUN remain the authorization/execution
  boundaries. A signed manifest, forecast, goal, or Core proposal grants no
  authority.
- Startup does not assume a previously active adapter survived restart.
- Unknown or interrupted external outcomes are not replayed as successful.
- The canonical writer host was not selected or migrated.

## Next eligible work

Wire the verified module lifecycle through an application-owned Platform
facade using existing SAFE and RUN receipts, then project signed manifest
capabilities/components into the Core observer. After that, complete the
remaining component supervision/recovery integration and the Platform Control
Center views. Keep effectful transitions inert until an authenticated approval
and existing execution boundary admit them.
