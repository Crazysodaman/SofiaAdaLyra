# Independent IT observation batch: MOD-IT-NETWORK + MOD-IT-HELPDESK

**Source base checked:** `5b6248250aab4b89c34d50f812e57d8f23c0e597` (`main`, 2026-10-25). This is a source base, not a claim of live host availability.

**Readiness:** ALPHA for both modules. Independent pure interpretation logic exists; signed immutable package, trusted factory reconstruction, real Platform admission, isolated process acceptance, independent audit/review, fleet compatibility, CI and host tests remain unverified. Do not mark Gate 3/4 or BETA based on this checkpoint.

**Ownership:** Existing `sofia.sdk.contracts.SDK_PROTOCOL_VERSION` and the Platform `Capability/CapabilityRequest` contract are consumed. No duplicate state, settings, SDK, scheduler, SAFE implementation or transport was introduced. Existing `src/sofia/modules/integrations` adapters are preserved. These analyzers do not collect network/host observations, sign evidence, verify caller identity or execute repairs.

## Module contract: MOD-IT-NETWORK 0.1.0

- **Capability:** `it.network.interpret_snapshot.v1` (OBSERVE, no external effect); single current, bounded snapshot of interface state, address/gateway, DNS rcode and TCP outcome.
- **Result:** `sofia.it.network.report.v1`; source ref, timestamp, freshness, findings, non-verified evidence classification, `effect=none`.
- **Negative behavior:** reject invalid IPs, unrelated fields, invalid enum values and mismatched address families; classify stale/future samples as unknown. NXDOMAIN never implies resolver outage by itself.
- **Host:** portable Python >=3.12, Windows/Linux on a reviewed MODULE_HOST or CORE_HOST; no GUI, GPU or Core required.
- **Resources (provisional minimum):** 50 millicores / 32 MiB RAM / 0 GPU MiB; zero direct network connections. These are declarations, not measured peak limits or signed Fleet reservations.
- **Configuration:** v1 `max_age_seconds` integer 1..86400, default 300, Platform host-owned; live reload only after atomic host validation, not implemented here. No secrets or durable module-owned state.
- **Maintenance:** schema target `sofia.module.maintenance.v1` (signed profile pending), health: inert import/registration and sample data validation, no outbound probes; failure: malformed -> deny, stale -> unknown, handler crash -> Platform supervisor quarantine; recovery: restore last known compatible signed package after Platform-controlled update, owner attention for recurring malformed sources; no automatic repairs. Rollback requires Platform verification.

## Module contract: MOD-IT-HELPDESK 0.1.0

- **Capability:** `it.helpdesk.triage_evidence.v1` (ADVISORY, no external effect); bounded ticket symptoms, diagnostic codes and optional versioned network projection.
- **Result:** `sofia.it.helpdesk.assessment.v1`, deterministic category, evidence level and observational next check; not a repair authorization.
- **Safety:** strict input enums, explicit source equality for network joins, stale/future rejection, no untrusted free-text echo, no shell/process/file/network effects, no claim that supplied evidence was independently authenticated.
- **Host:** portable Python >=3.12, Windows/Linux. No GUI, GPU, Core or canonical DB required.
- **Resources (provisional minimum):** 50 millicores / 32 MiB RAM / 0 GPU MiB, zero direct network connections. No module-owned persistence.
- **Configuration:** v1 `max_age_seconds` integer 1..86400, default 300; host-owned atomic validation pending in shared Platform. No secrets.
- **Maintenance:** schema target `sofia.module.maintenance.v1` (signed profile pending), health: registration and bounded fixture triage, dependency: optional MOD-IT-NETWORK result schema v1, failure: report mismatches deny and unavailable observations remain unknown; Platform controls restarts/quarantine/update/rollback, escalate repeated failures to owner. No automatic repairs.

## Focused test evidence

- `PYTHONPATH=src python -m pytest -q test/test_it_observation_modules.py`: **22 passed** in a local *isolated source workspace* with lightweight test-only replacements for the inspected SDK version constant and Platform Capability classes. This is **not** full-repo SDK integration or GitHub CI evidence. SDK stand-ins are not committed.
- `python -m compileall -q src/sofia/modules/it_network src/sofia/modules/it_helpdesk`: success in that workspace.
- Test matrix includes stale/future clocks, malformed/prohibited data, NXDOMAIN nuance, gateway mismatch, no-effect results, optional network-to-helpdesk interoperability, wrong network source and stale cross-module report.

## Exact Platform integration dependency for Codex

A reviewed factory must be able to register `capability_registrations()` through existing `ReviewedAdapterFactory` / `CapabilitySystem.register_batch` **only after** trusted package digest and profile selection, verified caller principal/audience/SAFE admission, SDK 1.0 envelope/generation/deadline checks, STOP enforcement, resource reservation and immutable maintenance profile attestation. The actual package signature, factory trust registration, supervisor isolation, source evidence authentication, request envelope bridging and release manager registration are NOT implemented in these module-owned files. No competing gateway or privileged auto-registration is permitted.

**CA/GA/ML crosswalk:** Not promoted. The source inspection covered the authorized 55-entry catalog and SDK/adapter foundations, but the authoritative 780-item task ledger reconciliation and independent acceptance remain pending.
