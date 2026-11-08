# Aegis SDK: Core + Platform + Module development test bench

This is the **three-piece, disposable reference setup** for testing how a Core uses an Aegis Platform module through SDK contracts. It complements the separately [signature-verified reference module tests](../sdk_reference_module/README.md).

| Part | Source | Uses | Never does |
| --- | --- | --- | --- |
| Dummy Core | [`sdk_reference_core/core.py`](../sdk_reference_core/core.py) | Builds `ComponentRequestEnvelope`, a bounded payload and independently checks response correlation/claimed outcome | Claims real Sofía identity, talks to LLM, stores Core memory or creates permissions |
| Dummy Platform | [`sdk_reference_platform/platform.py`](../sdk_reference_platform/platform.py) | Simulates connection binding, STOP, per-Core grants, capability routing and hotplug with the actual `CapabilitySystem` | Authenticate real users, sign software, write canonical state or start actual OS services |
| Reference Module | [`sdk_reference_module/reference.py`](../sdk_reference_module/reference.py) | Returns bounded `reference.ping` information through a Platform-controlled capability | Controls Docker, host, Files, models, devices or secrets |
| Shared wire demo | [`sdk_reference_system/wire.py`](wire.py) | Strict bounded JSON SHA-256 fingerprints for the example only | Produce an authentication/authorization signature |

**Boundary:** These are **in-process test doubles**, not a fully isolated Core and Platform, not an OS-authenticated IPC server, and not an installed module. The test-only `open_test_session()` and `test_only_grant()` are **never** production APIs. The identity/protocol fields are *portable data*, not evidence of a trusted actor. A signed module installer, production SAFE/STOP, enrollment and persistent canonical state remain separate.

## Try it yourself (no containers, Core or Platform services touched)

From the Aegis repo checkout:

**PowerShell (Windows):**

```powershell
python -m pip install -e . pytest
$env:PYTHONPATH = "src"
python -m examples.sdk_reference_system.try_it
python -m pytest -q test/test_sdk_reference_core_platform.py test/test_sdk_reference_module.py
```

**Linux / Debian:**

```bash
python -m pip install -e . pytest
PYTHONPATH=src python -m examples.sdk_reference_system.try_it
PYTHONPATH=src python -m pytest -q test/test_sdk_reference_core_platform.py test/test_sdk_reference_module.py
```

Expected **demo** outcomes (illustrative until CI confirms these tests):

```json
{
  "demo": "aegis.sdk.core-platform-module.v1",
  "first_core": "succeeded_reported_unverified",
  "second_core_before_grant": "denied",
  "second_core_after_grant": "succeeded_reported_unverified",
  "module_unplugged": "unavailable",
  "available_capabilities_after_unplug": [],
  "independent_verified_effect": false,
  "production_authentication": false,
  "real_worker": false,
  "persistent_state": false
}
```

### What you learn by editing

1. **Core-side:** In [`core.py`](../sdk_reference_core/core.py), inspect `build_ping()`. Change the nonce in [`try_it.py`](try_it.py) and observe the same value returned by the module. Try an unknown schema or expired deadline in the test file and see it rejected.
2. **Platform-side:** In [`platform.py`](../sdk_reference_platform/platform.py), compare `test_only_grant(session)` with `test_only_revoke(session)`. The Platform, not the Core, decides whether a capability call can execute. Test STOP, identity mismatch, generation changes and unplug without restarting the demo.
3. **Module-side:** In [`reference.py`](../sdk_reference_module/reference.py), inspect `capability_registrations()` and `settings_contract()`. Change a **non-privileged** output field in a scratch branch, update conformance expectations and verify that the SDK protocol is unchanged.
4. **Release-side:** In [`test_sdk_reference_module.py`](../../test/test_sdk_reference_module.py), see real manifest verification with a throwaway test key and exact lifecycle/setting revision checks. An in-memory Platform demo is never permission to install a live module.
5. **Multi-Core:** [`test_sdk_reference_core_platform.py`](../../test/test_sdk_reference_core_platform.py) shows two independent synthetic Core sessions, denial before grant, denial after revocation, request replay rejection and module unplug without Core teardown.

## Development model for any real Core/Platform

```text
        DUMMY CORE A         DUMMY CORE B
       SDK request v1       SDK request v1
              \                /
               \              /
                DUMMY PLATFORM
        test-only connection binding
          Platform-owned capability registry
         simulated per-Core access + STOP
                        |
              REFERENCE MODULE
                reference.ping
```

For production, use a real, **authenticated, signed, generation-fenced Aegis IPC/session** and reviewed `PlatformModule` workers. A model's assertion that it is a Core or has permission is never proof. The production Platform must derive the actual principal, audience and scope from its trusted connection, not from the `AuthorityProjection` sent in the request.

### SDK updates

The Python and Rust wire protocol currently advertises **1.0**. The SDK reference CI can catch format incompatibilities and regressions across the three examples, but does **not** upgrade installed components automatically. See [SDK compatibility rules](../../docs/development/SDK_REFERENCE_AND_COMPATIBILITY.md). New developer code does not get an SDK update by magic; signed, compatible release artifacts and owner-reviewed rollout remain necessary.

**Acceptance status:** Reference Core + Platform are educational fixtures. This bench does **not** certify standalone executable Core, production Platform, actual module IPC, real OWNER approval, live GUI/TUI, SDK auto-updates, or Platform 1.0 GO-LIVE.
