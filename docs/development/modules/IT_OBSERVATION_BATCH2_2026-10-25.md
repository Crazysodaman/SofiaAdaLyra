# Sofía 2.0 independent modules, batch 2

Base inspected: GitHub main at 8a27a0b237f524b272ca42978875185a99b1fcb7 (2026-10-25).

Four module-only, Python >=3.12, OS-neutral observational/advisory analyzers:

| ID | Capability | Operation profile | State | Resources (provisional, NOT measured) |
|---|---|---|---|---|
| MOD-SENSORS 0.1.0 | sensors.interpret_readings.v1 | OBSERVE | none | 50 millicores/32 MiB RAM/no GPU |
| MOD-IT-OBSERVABILITY 0.1.0 | it.observability.correlate.v1 | ADVISORY | none | 50 millicores/32 MiB RAM/no GPU |
| MOD-IT-SYSTEMS 0.1.0 | it.systems.analyze_snapshot.v1 | ADVISORY | none | 50 millicores/32 MiB RAM/no GPU |
| MOD-IT-CONTAINERS 0.1.0 | it.containers.interpret_inventory.v1 | OBSERVE | none | 50 millicores/32 MiB RAM/no GPU |

Capabilities consume standard reviewed SDK_PROTOCOL_VERSION and Platform Capability/CapabilityRequest types. No alternate SDK, Core, state, auth service, process supervisor or device connector. Input only from a caller-authorized evidence producer. Outputs explicitly labeled supplied_unverified. No self-issued permissions or claims of receipt verification.

Existing integrations to reuse later: mobile sensor observation provider; environment provider; Portainer, local maintenance and Hyper-V adapters; Platform monitoring/fleet telemetry. No existing integration file changed.

Maintenance profile target for each: sofia.module.maintenance.v1 (immutable signed profile NOT completed). Inert inspection and bounded sample evaluation; no native network/device probing. Invalid/duplicated observations rejected; expired timestamps treated as unknown. For crash, restart and quarantine rely on Platform supervisor. No automatic repair, service restart, cleanup, live permission upgrades or host migration. Fault escalation to owner through Platform on repeated source mismatches. Rollback requires exact package/digest verification by Platform. No secrets to persist.

Module-specific configuration schema target: host-owned `max_age_seconds` integer in 1..86400, default 300; no global Settings modifications. A Platform settings facade and atomic apply acknowledgements remain integration dependencies.

Test: `PYTHONPATH=src pytest -q test/test_four_module_batch.py`, 29 passed in isolated workspace, with test-only stand-ins for two existing shared SDK/Platform classes. Stand-ins are excluded from the delivery bundle. `python -m compileall` completed for module sources.

## Unverified / pending
- Real installed SDK import, exact factory reconstruction and package identity/signature, on-host process isolation, authenticated source adapters, signed maintenance and manifests, version negotiations through envelopes, permission/STOP enforcement and effect receipts, CI, code review, full-repository regression and live-host acceptance.
- Tests verify deterministic module analyzers only. No target modules have verified Platform production lifecycle registration.
- Universal readiness: ALPHA for all four; original CA/GA/ML task counts not promoted.
- This bundle is an independent source checkpoint and is not a GitHub push or release receipt.

## Exact Codex integration ask
Bind each `capability_registrations()` tuple from trusted reviewed factories to Platform capability runtime after verified package digest, per-principal and per-audience SAFE scopes, execution generation/deadline checks, resource lease, settings validation and signed maintenance profile. Platform must provide data-provider provenance and handle abort/STOP, isolation and update rollback. Modules must never construct their own gateway.
