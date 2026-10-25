# Sofía 2.0 independent modules, batch 3: resilience analytics

**Audited remote baseline:** GitHub `main` at `8a27a0b237f524b272ca42978875185a99b1fcb7` on 2026-10-25. This is a read-only source baseline, not a claim of installed packages.

## Four capabilities

| Module | Version | Capability | Mode | State |
| --- | --- | --- | --- | --- |
| MOD-IT-STORAGE | 0.1.0 | `it.storage.analyze_volumes.v1` | OBSERVE | stateless |
| MOD-IT-DATABASE | 0.1.0 | `it.database.analyze_status.v1` | ADVISORY | stateless |
| MOD-IT-BACKUP-DR | 0.1.0 | `it.backup_dr.assess_recovery.v1` | ADVISORY | stateless |
| MOD-IT-SECURITY | 0.1.0 | `it.security.triage_findings.v1` | ADVISORY | stateless |

All four are bounded data interpreters and have actual callable capability registration tuples. They import the original `sofia.sdk.contracts.SDK_PROTOCOL_VERSION` and `sofia.platform.capability.model.Capability`/`CapabilityRequest` names. No Core, DB, device, Docker socket, SQL, filesystem or network access is performed by these modules. Source claims are always labeled `supplied_unverified`; no capability may issue verified evidence or auth grants.

**Existing code inspected/preserved:** `src/sofia/modules/integrations/storage.py`, `src/sofia/modules/integrations/sqlite.py`, `src/sofia/platform/ops/backup.py`, `src/sofia/platform/modules/package.py`, `src/sofia/platform/safe/permissions.py`, `src/sofia/sdk/contracts.py`. These adapters and Platform-owned backup/recovery engines are *not replaced or modified*. The prospective provider wiring will reuse authorized read-only projections, and never wrap a mutating maintenance method in an OBSERVE profile.

## Operation, resources and platform

- Windows/Linux Python >=3.12, CORE_HOST and MODULE_HOST, no GUI, Core cognition or GPU. A remote Core Link is sufficient if the real Platform dispatch contract exists.
- **Provisional requirement**, not observed/measured: each needs nominal 50 millicores, 32 MiB RAM and 0 GPU MiB. No direct network/device use. Actual worker memory/CPU require independent measurement and signed manifest admission.
- Per capability max_age_seconds: typed integer 1..86400, default 300, but runtime settings registration, atomic apply acknowledgments, rollback and shared Settings ownership remain Platform tasks.
- Input and output schemas are versioned; unknown input keys, invalid identity fields, non-finite metrics, negative counter values, duplicates and inconsistent backup timelines are rejected. Stale/future observations are classified unknown. Truncated or absent data must never become zero-load assertions.
- Security privacy: no raw logs, commands, SQL, credentials, URLs or arbitrary external text accepted. Only approved scoped identifiers and explicit enumerations are output. A high-severity alert is not automatically a verified compromise. A backup passed flag is not automatically proof of restore recoverability.

## Module-specific maintenance profiles (v1 proposal, not signed)

| Module | Inert probe | Fault/degraded state | Owner action |
| --- | --- | --- | --- |
| IT Storage | Validate bounded usage snapshot & registration | Stale/missing/invalid -> unknown/deny | Inspect storage provider, free space or device hardware manually |
| IT Database | Validate reported connection/replica/latency snapshot | Unknown/stale/invalid -> unknown/deny | Review DB provider telemetry, privileges and query logs |
| IT Backup/DR | Validate backup/recovery timelines and drill claims | Missing verified drill, RPO/RTO breach, stale input -> unknown/degraded | Request supervised test restore and independent verification |
| IT Security | Validate sanitized finding enums and freshness | Stale/corrupt/untrusted finding -> unknown/deny | Review independent source evidence before privileged response |

**Maintenance schema target:** `sofia.module.maintenance.v1` version 1, status proposed/supported after signing, health check on bounded sample (no provider connection), fail closed on malformed evidence, retry budget owned by Platform, quarantine on repeated crashes by Platform supervisor, no module-controlled auto-repair, update only after digest/signature/compatibility verification, rollback only through Platform; immutable maintenance artifact digest not generated. No persistence/retention or secrets stored inside these modules. Diagnostics must redact any rejected input values. Operator attention required for recurring bad telemetry or confirmed security issue. State/disabling needs no migration.

## Local verification

- `PYTHONPATH=src python -m pytest -q test/test_it_resilience_modules.py`: **51 passed** (Python 3.13.5, isolated workspace). Runner used minimal **test-only** SDK/Capability stand-ins. They are not delivered into the repository as replacements for real SDK or Platform classes.
- `python -m compileall -q src/sofia/modules/it_storage src/sofia/modules/it_database src/sofia/modules/it_backup_dr src/sofia/modules/it_security`: passed in isolated workspace.
- Cases include four handler registrations/descriptor spoofing, stale/future timestamps, boundary/NaN metrics, permission-free no-effect classification, RPO/RTO evaluation, false restore success prevention, security raw-field injection denial and cross-module observation separation.
- **Unverified:** full-repo test suite, real SDK import, signed package/factory activation, Platform SAFE/STOP/RUN authorization, actual worker isolation, real-source trust, Fleet resource reservation, CI, review, on-host operation and rollback. **Readiness: ALPHA** for all four, no 780-task evidence promotion.

## Exact Codex-owned handoff

Codex Platform team must expose trusted adapter factory reconstruction and packet-to-capability dispatch for the four registrations, after package digest and maintenance profile signature checks, request envelope/generation/deadline/caller/SAFE/STOP checks, typed settings admission, resource lease and source provenance validation. No second supervisor, SDK, writer or Settings manager has been added here. This is an integration dependency, not an authorization to install automatically.
