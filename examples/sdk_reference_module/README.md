# Aegis SDK Reference Module (test-only)

This is the **golden, inert module example** for developers of Sofía/Aegis modules. It models **the actual Python SDK v1 contracts and Platform lifecycle**, not a magical plugin loader or an installer.

**Catalog status:** Not part of the 55 production module entries and **NOT** an independently installable release. Its example module ID is `dev.aegis.reference`, version `0.1.0`, and its only capability is `reference.ping`. No real-world services, external devices, Docker, credentials or model execution are involved.

## What is in this example

| File | Role |
| --- | --- |
| [reference.py](reference.py) | Module-side code. Declares module ID/capability, returns a bounded `ping` result, and exports typed `ModuleSettingsContract`. |
| [test_sdk_reference_module.py](../../test/test_sdk_reference_module.py) | Developer-only Platform harness: ephemeral Ed25519 test signature; real manifest verification, lifecycle, capability registration, authorization denial, settings CAS and pause/resume/remove receipts. |
| [SDK component update contract](../../docs/sofia2/COMPONENT_UPDATES_AND_UNIFIED_SDK_V1.md) | Authoritative intended SDK split, compatibility and upgrade boundaries. |
| [SDK compatibility workflow](../../docs/development/SDK_REFERENCE_AND_COMPATIBILITY.md) | When to change protocol versions, Python/Rust parity, and when a Platform restart is actually necessary. |

## Run in a disposable developer checkout

At the repository root with your normal project Python environment:

```bash
PYTHONPATH=src python -m pytest -q test/test_sdk_reference_module.py
```

On PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q test/test_sdk_reference_module.py
```

The test harness creates an ephemeral **test-only signing key in memory** and signs a copied `reference.py` file in pytest's disposable `tmp_path`. It never installs or signs a production package, edits a real host state DB, uses an owner secret or starts a production service. The test's synthetic authorizer is **not** suitable for real deployments.

## Intended lifecycle (real Platform contracts, synthetic approvals)

```text
Copy reviewed reference.py -> manifest v3 + digest + throwaway test signature
  -> verify_module_package (no import from untrusted archive)
  -> ModuleLifecycleManager.discover/approve/stage
  -> evaluate_module_compatibility
  -> ModuleLifecycleManager.activate (in-process trusted test handler)
  -> CapabilitySystem.execute(CapabilityRequest("reference.ping"))
       approved:  SUCCESS / effect=none
       denied:    UNAUTHORIZED / handler not invoked
  -> ModuleSettingsService.update (exact digest, lifecycle revision, CAS)
       display.mode:      LIVE -> APPLIED, ping uses new display mode
       demo.transport:    COMPONENT_RESTART -> PENDING, no silent restart
  -> pause -> capability UNAVAILABLE -> resume -> capability usable
  -> pause -> disable -> remove -> capabilities unavailable, audit retained
```

For a real production module, replace the in-process test registration with an **independently reviewed, digest-pinned `ReviewedAdapterFactory` and isolated worker**, signed release, host-side owner authorization, stable versioned IPC, cancellation, health and resource monitoring. The reference module's `capability_registrations` demonstrates interface shape, not an endorsement of importing source from arbitrary packages.

## How the Core and GUI/TUI use modules

The **Core never imports `reference.py` dynamically**. Aegis admits a signed package, starts an approved worker, registers the module's capability, and exposes the current capability through an authorized broker. The Core can request `reference.ping` using the SDK request envelope only after Platform approval. GUI and TUI read lifecycle/settings/jobs from the same authenticated Platform view, rather than writing their own module state. Module capabilities disappear when withdrawn.

The provided source-level harness tests actual Platform lifecycle and capability-system behavior. **It does not yet include a live Rust GUI/TUI client or OS worker process**, so it must not be cited as Platform/Module 1.0 installed-host certification. The existing reviewed Research worker provides an additional isolated-process example at `src/sofia/platform/modules/process_worker.py`.

## How to adapt for a real module

1. Use a new **owner-reviewed signed module identity**. Do not reuse `dev.aegis.reference` for production or copy the test signature.
2. Define exact capability names, typed inputs/outputs, resource budget, required host/OS/device profile and maintenance/health contract. Observe/advice before privileged effects.
3. Declare settings with `ModuleSettingsContract`. The Platform owns persistence/revisions/secret references and decides when LIVE/NEXT_OPERATION/COMPONENT_RESTART applies; the module has no direct canonical DB writer.
4. Supply a reviewed, digest-pinned worker factory. Don't import arbitrary package code during discovery/verification.
5. Require trusted Platform owner approval for actual module execution and any effectful capability. Never treat an LLM suggestion or manifest capability as authority.
6. Add fault/STOP/revocation/recovery/ABI/migration and installed Windows/Linux tests before claiming production readiness.

**SDK update expectation:** The Python and Rust protocol are both `1.0` at the inspected baseline. Tests detect drift, but they **do not auto-release, auto-download, or auto-migrate every SDK consumer**. Use the controlled compatibility workflow linked above.
