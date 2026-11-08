# SDK reference and compatibility policy (owner-requested, 2026-11-08)

**Status:** Initial SDK reference harness implemented in a draft PR; version governance described here. This is **not** proof of live automated SDK updates or a production reference module.
**Related:** [reference module example](../../examples/sdk_reference_module/README.md), [SDK v1 design](../sofia2/COMPONENT_UPDATES_AND_UNIFIED_SDK_V1.md), [Python SDK](../../src/sofia/sdk), [Rust shared contracts](../../rust/crates/sofia-contracts/src/lib.rs).

## 1. One SDK family, several consumers

| Component | Observed version boundary | Update policy |
| --- | --- | --- |
| Python `sofia.sdk` shared contracts | `SDK_PROTOCOL_VERSION = ProtocolVersion(1, 0)` | Platform/Core/modules use explicit typed portable contracts; update from reviewed package releases, not background source replacement. |
| Rust `sofia-contracts` | `SUPPORTED_PROTOCOL = "1.0"` | Require schema/protocol parity or an explicitly negotiated supported version range; separate crate version `0.1.0` is a **package version**, not wire protocol. |
| SDK module-facing facade | Python typed contract + Platform capability/worker interfaces | The current module example necessarily imports `sofia.platform.capability.model` and delegates lifecycle/authority to Platform. A separately packaged portable module facade remains incomplete. |
| Platform/native management, Core Link, UI | Several versioned contracts and independent Rust/Python implementations | The contract, implementation and tests for **each affected consumer** must update together for a breaking change, or retain a reviewed compatibility shim. |
| Developer SDK tooling | This golden sample + tests, Python/Rust parity guard | Future source scaffolding, schema codegen, cross-language golden fixtures, ABI matrix, exact SHA certification and signed installer still needed. |

## 2. What 'automatically update every SDK when possible' means

**Desired:** whenever an approved compatible SDK contract is changed, CI identifies every declared Python/Rust consumer, compiles/validates conformance fixtures, reports the compatible release set, and prepares signed coordinated artifacts. The Platform can recommend/stage compatible per-component updates without stopping unrelated modules.

**Not yet present:** an automated, authoritative all-consumer dependency graph, secure unattended module SDK updater, automatic version bump propagation, full code generation, or installed-host evidence. A file edit to Python does **not** automatically update Rust, and the reverse is equally true.

**Safe default:** no silent SDK upgrades on installed modules or Cores. A module's signed manifest selects `api_minimum`, `api_maximum_exclusive`, the exact artifact digest, isolation/profile, maintenance rules and migration. A compatible SDK *package* release can be prepared/verified; installation is still an independently governed change with STOP/revocation and rollback checks. If the new ABI requires Platform ownership, shared schema migration or in-process modules, an approved Platform restart may be required, and the UI must say so.

### Compatibility decision matrix

| SDK change | Expected action | Restart policy |
| --- | --- | --- |
| Docs, examples, or new test fixture | Run static and targeted cross-language checks | None |
| Additive field with safe backward behavior, minor protocol range supported by both peers | Update both language bindings/fixtures/consumers, negotiate shared minor version | Compatible worker can update separately after review; no mandatory Platform restart if truly isolated |
| Validation tightening or changed error semantics | Treat as potentially breaking; review affected callers and negative fixtures | May require coordinated upgrade rather than assumptions |
| Breaking schema / major protocol bump | No silent coercion, fail closed, ship new endpoints or explicit migration with compatibility window | Staged coordinated release, Platform restart only when genuinely required |
| Privileged capability/permission classification, secret or signing contract | Independent SAFE/security review, signed digest, explicit owner approval | Scope dictated by actual affected trusted boundary |
| Hardware/OS driver, native extension or shared in-process ABI | Require dependency impact review, host staging, verified rollback | Affected worker or Platform/OS maintenance where necessary, not 'always hot' |

## 3. Golden reference module as the conformance template

Tests in `test/test_sdk_reference_module.py` exercise:
- version/protocol parity: Python `SDK_PROTOCOL_VERSION` vs Rust `SUPPORTED_PROTOCOL`, negotiation rejects incompatible majors;
- no-execution signed manifest integrity of copied `reference.py` with a **throwaway test key**;
- real `ModuleLifecycleManager` discover/approve/stage/activate/pause/resume/disable/remove and actual event receipts;
- `CapabilitySystem` admitted read-only request, denied request and disappearance when paused;
- `ModuleSettingsService` schema v3 typed values, authenticated synthetic test authorizer, optimistic revision fencing, idempotency and distinct LIVE versus COMPONENT_RESTART outcomes;
- no production owner key, no live host, no real authority or verified worker health.

**Source-test limitation:** using a reviewed in-process handler tests the lifecycle/SDK facade but does **not** prove real worker isolation, dynamic signed adapter enrollment, TUI/GUI subscriptions, cross-host placement, signed release workflow or restartless UI parity. Keep G/Platform acceptance open until a disposable installed-host test reproduces those behaviors.

## 4. Required SDK release pipeline (remaining work)

1. **Inventory:** machine-readable SDK schema and exact consumers (Python/Rust/UI/Core/modules), without trusting unreviewed discovered modules.
2. **Build:** additive or breaking change proposal with exact version/range, migration/revocation implications, stable error taxonomy, retry/idempotency semantics, and artifact SHA.
3. **Conformance:** update Python and Rust fixture corpus, run negative tests, schema roundtrip, error parity, signed package/adapter admission and user-visible UI state. Keep the reference module green.
4. **Package:** signed SDK/Platform/core/module compatibility release from approved builder, with independent audit of codegen/factory, SBOM and fresh host evidence.
5. **Rollout:** compatibility graph selects smallest safe worker restart or data-only reload; module/Cores cannot force install, choose new SDK authority or skip current STOP.
6. **Verify:** real Windows/Debian installed-host worker/capability and multi-UI tests; rollback and no duplicate external effects if transport crashes.
7. **Document:** record exact SHA/test command/worker generation, outcome and known gaps; only then mark SDK consumer supported.

**Do not make an 'SDK auto-update' timer part of Sofía's reasoning loop.** Use Platform-owned signed release jobs with independent approval. A user-facing `SDK Updates` page can recommend compatible updates and say when a restart is necessary; availability is not permission.
