# Sofía 2.0: engineering simulation module batch 5 (2026-10-25)

**Repository:** `Crazysodaman/SofiaAdaLyra` / `main`. **Development checkpoint:** independent module source and tests; this document is not a Platform certification or proof of live installation. The module designs are entries in `docs/sofia2/MODULE_OWNERSHIP_MATRIX.md`. Prior inspection of shared API: `src/sofia/sdk/contracts.py` SDK 1.0 and `src/sofia/platform/capability/model.py` / `platform/modules/adapters.py`.

## Modules (v0.1.0, ALPHA only)

| Module | Capability ID and operation profile | Source | Input and output contract | Limitations |
|---|---|---|---|---|
| MOD-ENGINEERING | `engineering.simulate_resistive_dc.v1`, SIMULATE | `src/sofia/modules/engineering/analysis.py` | v1 exact-fields source/timestamp/topology/supply/resistor values/current threshold -> v1 branch current/voltage/power, equivalent resistance and findings | Ideal DC resistive network only; no wiring safety, ampacity, short-circuit, protective-device coordination or electrical code judgment |
| MOD-ELECTRONICS | `electronics.analyze_adc_divider.v1`, SIMULATE | `src/sofia/modules/electronics/analysis.py` | v1 source/timestamp/Vin/resistors/ADC reference/resolution/input limit -> divider node voltage, Thevenin resistance, ideal ADC code and limit flags | No actual ADC tolerance, supply transient, ESD, loading, conversion nonlinearities or GPIO control |
| MOD-3D-PRINT | `printing3d.estimate_material.v1`, ADVISORY | `src/sofia/modules/printing3d/analysis.py` | v1 source/timestamp/slicer-reported filament length/diameter/density/time/nozzle/layer and optional flow ceiling -> volume/mass/average flow and findings | Unverified slicer estimates; average flow does NOT establish peak flow, mechanical strength, print completion or actual filament consumed |
| MOD-ROBOTICS-GAIA | `gaia.simulate_leg_ik.v1`, SIMULATE | `src/sofia/modules/robotics_gaia/kinematics.py` | v1 source/timestamp/3-DOF leg segment lengths/xyz and per-joint limits -> reachable state and ideal joint angle candidates | No servo-pulse conversion, SSC-32 protocol, real collision checks, body stability, torque/speed/thermal analysis or motor actuation |

All modules consume existing `SDK_PROTOCOL_VERSION` from `sofia.sdk.contracts` and `Capability`/`CapabilityRequest` from the existing Platform API. Their `capability_registrations()` returns inert registration tuples. Direct invocation does not authenticate its caller. The Platform is the only permitted owner of authorization, STOP, generation fencing, process isolation, resource leasing, update/rollback and canonical state. No new SDK, database writer, supervisor, central settings service, direct network access, serial port or OS process operation was created.

## Operation profiles, configuration and resources

- All use **stateless** deterministic analysis; source data must be explicitly supplied by an approved Platform route. The module does not read sensors, files, cameras, serial devices or host processes. No module-owned durable state, secrets or state migrations.
- **API version:** SDK protocol 1.0. Modules do not select or install a Core; MODULE_HOST, CORE_LINK+MODULE_HOST and CORE_HOST compatibility is conceptual until signed packaging and Platform probes pass.
- **Runtime requirements (provisional estimates, not measured acceptance):** Windows/Linux, Python >=3.12, CPU allocation 50 millicores, RAM 32 MiB, zero GPU and zero mandatory peripherals *per analysis worker*. Actual peak resource measurements and Fleet placement tests are pending.
- **Configuration schema v1:** per-host `max_age_seconds` integer 1..86400, default 86400, validated by pure entrypoints; updates from Settings must be authenticated and atomically applied by shared Platform. No configuration persistence, live reload or atomic rollback was tested.
- **Data and privacy:** non-identifying bounded references; no arbitrary user-supplied command strings; reject extra keys; all outputs label source as `hypothetical_supplied` (or `slicer_supplied_unverified`) with `effect=none`. No cross-audience re-disclosure permitted. Platform must authenticate source and principal and apply retention rules.
- **Timeout/idempotency:** bounded synchronous computation (Engineering <=32 resistors, Electronics one divider, Printing one slicer summary, Gaia one leg). Pure replay is idempotent for identical inputs and `now`. Platform controls deadline and cancellation. Module does not emit external effect receipts.

## Proposed per-module maintenance profiles (pending immutable signing by Platform)

Intended `sofia.module.maintenance.v1` profile version 1, support status `supported`, and `module_version=0.1.0` for each module. Signed artifact digest, publisher trust and verified update compatibility **cannot be supplied by a module** and are intentionally pending. The table is a constrained maintenance-proposal record, not an accepted `SignedModuleManifest` or fake signed profile.

| Module | Inert health probe | Known failure modes / recovery | Owner attention conditions |
|---|---|---|---|
| Engineering | `engineering.fixture_kirchhoff.v1` | Invalid topology/data or stale plan -> no simulation; malformed input is rejected. Platform supervisor may restart an isolated crashed worker and quarantine on repeated failures | Disagreement with independent circuit solver, anomalous numeric results or confusion with real-world electrical installation |
| Electronics | `electronics.fixture_divider.v1` | Out-of-range ADC/design parameter -> reject; stale inputs -> unknown; limit violations -> advisory only. Platform owns recovery | Proposed voltage at/over ADC user-supplied limit; component selection needs hardware datasheet review |
| 3D Printing | `printing3d.fixture_material.v1` | Bad slicer/unit report -> reject; stale -> unknown; high average flow -> advisory only | Actual machine throughput differs from supplied profile; material/thermal constraints unverified |
| Robotics Gaia | `gaia.fixture_ik_forward_check.v1` | Out-of-workspace -> unreachable; joint limit violation -> no valid actuation plan; stale -> no solution; Platform quarantines repeated crashes | Before hardware trials: pin geometry, servo calibration, collision checks, power/safety interlocks and owner approval |

For every module: health probe must be effect-free, retry budget for the pure handler 0, crash-loop quarantine threshold proposed 3 (Platform-controlled and not active here), update only through a verified immutable package, restore/revert only to a Platform-certified compatible digest, rollback is never self-triggered, diagnostics contain only bounded codes and no raw secrets. No real worker lifecycle or host resilience evidence has been generated.

## Test evidence and security review

- Test suite: `test/test_engineering_modules_batch5.py`.
- In isolated workspace with test-only SDK/Capability stand-ins: `PYTHONPATH=src python -m pytest -q test/test_engineering_modules_batch5.py` -> **61 passed**.
- Combined isolated regression for Batches 2–5: `PYTHONPATH=src python -m pytest -q test/test_four_module_batch.py test/test_it_resilience_modules.py test/test_module_batch4.py test/test_engineering_modules_batch5.py` -> **211 passed**.
- `python -m compileall -q src/sofia/modules` succeeded in isolated workspace; static inspection of the four new modules found no subprocess/socket/SQLite/OS/serial imports.
- Tests cover Kirchhoff power/voltage/current invariants, divider clipping and overvoltage warnings, print unit conversion and process warnings, Gaia forward/inverse consistency and unreachable/limit behavior, nonnumeric/infinite/boolean input rejection, stale/future source times, exact-input contracts and inert registered handlers.
- Actual GitHub repository pytest, pinned production SDK, signed package construction, independent security audit, authenticated source injection, supervised host simulation, CI, interoperability certification, release manager activation and physical acceptance remain **unverified**. Readiness label is **ALPHA**, not Gate 4, BETA, RC or Production Ready.

## Exact integration request to Codex (shared owner)

After official SDK/Platform stability, construct an approved `ReviewedAdapterFactory` for each signed module with exact module/package digest, selected operation profile, component/host binding and version negotiation. The reviewed dispatcher must authenticate principal and provenance; verify grants, deadlines, destination generation, cancellation, STOP, and resource/placement state **before** calling these module handlers. Persist and compare authenticated evidence/receipts with the actual request payload; never promote analysis output into an authorization token. Platform owns package signature, maintenance digest linkage, canonical state and lifecycle, while these four module packages remain narrow and stateless.

**Crosswalk:** Four explicit catalog IDs above. CA/GA/ML authoritative tasks were not advanced by this documentation; a release review must map exact existing task identifiers and execute full gates before claiming completion.
