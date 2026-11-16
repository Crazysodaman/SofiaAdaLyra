# Project Aegis | Platform-first startup, Batch 1 checkpoint

**Date:** 2026-11-16  
**GitHub current main verified when inspected:** `ac7f178cd8d7e790151e308c192175ac1ecad62e` (recheck on use).  
**Evidence type:** Owner-pasted OpenCode report plus independent read-only inspection of GitHub source at the stated head. **Not** an executed local test or installed-host acceptance report.

## Batch 1 delivered source paths

- `src/sofia/platform/cli.py` and `pyproject.toml`: public `aegis` client executable, status/startup/service/core/module/chat/diagnostics/gui/tui commands. Core/service/module mutations and chat still intentionally refuse without real authenticated management/Core Link wiring. GUI/TUI only resolve existing executables.
- `src/sofia/platform/run/core_autostart.py`: canonical-SQLite desired state, one-use approval verifier callback, reconciliation interface and result recording. No production real-Core process backend by default.
- `src/sofia/platform/run/platform_service.py`: accepts an optional injected `CoreStartupReconciler`, reconciles and provides startup status. No automatic generic Core process integration independently proven.
- `src/sofia/platform/run/management_read.py`, `management_peer_authority.py`, `src/sofia/sdk/platform_management.py`, `platform_management_response.py`: startup.status read contract; core-running status no longer rejected solely because a Core exists.
- New/updated focused tests include `test_aegis_cli.py`, `test_core_autostart.py`, `test_platform_service_session.py`, management/SDK response tests.

## Test evidence as reported by OpenCode, not personally rerun here

Integrated focused tests 175 passed/7 skipped, Platform-only gate 414 passed/15 skipped, CLI 31 passed, workers' management/startup 130 passed/22 skipped, autostart 42 passed/7 skipped. No full unfiltered suite was reported. Exact-main GitHub CI was in progress or queued when checked; do not call it passed by implication.

## Source-observed issues to reproduce next

| ID | Observation in code | Consequence / needed test |
| --- | --- | --- |
| SA-RISK-01 | `core_autostart.py` default freshness 900 seconds compares persisted `updated_at` to current time | Previously approved autostart may fail after a normal overnight reboot; distinguish durable policy from fresh authorization |
| SA-RISK-02 | `CoreStartupReconciler.reconcile()` counts cached STARTED for matching generation without fresh worker observation | Crash/stale process may be falsely counted RUNNING |
| SA-RISK-03 | Reconciler returns ZERO_CORE_HEALTHY if zero policies enabled, even when disabled policy rows exist; Platform reports `core_count = len(policies)` and response validation rejects zero-core state when count > 0 | Inconsistent startup.status for one installed but disabled Core |
| SA-RISK-04 | Reconciler allows optional `is_authorized` default to True and constructs a string `approval_ref`; callback is injected, not a current signed owner grant | Production wiring must enforce current owner trust, signed package, SAFE/STOP and generation |
| SA-RISK-05 | Session constructor runs reconciliation synchronously after management IPC setup | Need tests for bounded native READY deadline and management responsiveness when a Core start blocks |

These observations are *not* proof of a currently reproducible CI failure. Build negative tests and fix narrowly; never weaken SAFE/STOP or owner-proof rules.

## Prioritized verification gap

The native Rust `aegis-platform-service` and Python `sofia.platform.run.platform_service` are designed for Core-free authority; a production signed independent Core worker autostart is not yet proven. The `aegis` CLI isn't currently using a supported live authenticated OS transport, although a pinned Linux `platform.status` SDK client exists. SDK Validation Core is not yet built. Legacy Sofía-first entrypoints remain until parity and rollback are verified. Preserve Platform 1.0 and Core 1.0 GO/NO_GO criteria and real-host evidence gates.

## Missing documents, resolved by external handoff

At the moment the first worker ran, the new owner planning files were not checked into the repository. Include the separately supplied owner ZIP's `docs/roadmaps` files in the actual checkout to allow task-ID mapping; do not claim that a planning document by itself changes code or authorizes service installation.
