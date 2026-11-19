# Aegis Cores #6 and #7 Integration, QA and Documentation V1

**Status date:** 2026-11-17 (reconciled 2026-11-18)  
**Workstream:** integration, QA and documentation for Cores #6 and #7  
**Current reconciliation:** `docs/sofia2/CORE_CATALOG_V1.md` and
`docs/sofia2/CORE_7_UNWRITTEN_SPEC_V1.md`  
**Baseline:** `main` at `7ea80fb3` for the original workstream; the modules are
now integrated on current main.  
**Evidence class:** source inspection and disposable simulated fixtures only.
No live Platform, installed Core package, real inference backend, GPU
reservation, callsign authority, avatar renderer, voice asset or external host
was used. This document does not claim live or installed verification.

## Evidence vocabulary

- **OBSERVED:** files read or tests executed in this worktree.
- **INFERRED:** a narrow adapter can connect an external workstream to the
  Protocol, but the external implementation was not present at this baseline.
- **UNKNOWN:** no observation was made. No claim of existence or nonexistence
  is derived from denied or absent access.

The Core #6 (Vera-like) and Core #7 (blank/unwritten) implementation
workstreams were not present as committed code in this worktree at baseline
`7ea80fb3`. Their internal APIs remain **UNKNOWN**. Integration therefore uses
the narrow Protocols in `sofia.core.multicore.v6_v7_acceptance`; no Agent 2,
Agent 3 or Agent 4 file was edited or imported.

## Implemented files

| File | Purpose |
| --- | --- |
| `src/sofia/core/multicore/v6_v7_acceptance.py` | Disposable two-Core fixture, Protocol seams and end-to-end acceptance harness. |
| `test/test_core_multicore_v6_v7_integration.py` | Integration, isolation, denial, recovery, coexistence and real Platform/memory boundary tests. |
| `docs/sofia2/AEGIS_CORES_6_7_IMPLEMENTATION_V1.md` | This traceability, operation and blocker record. |

No real installation occurs. The reference package adapter reports
`installed=False` for both new fixtures; activation is a simulated selection
that preserves that truth. A separate `seed_installed` helper exists only to
model an already-installed Core during coexistence tests.

## Design-to-implementation traceability matrix

Status values: **Designed** = requirement represented in the acceptance
contract; **Coded** = implemented in this workstream; **Tested** = executed by
the named test; **Blocked** = requires an external owner or live host.

| Requirement | Designed | Coded | Tested | Blocked | Evidence |
| --- | --- | --- | --- | --- | --- |
| One Vera-like Core and one blank Core | Yes | Yes | Yes | No | `V6V7Fixtures`, `test_full_disposable_acceptance_path_passes_required_stages` |
| Unique UUIDs and distinct profiles/identities | Yes | Yes | Yes | No | `test_fixtures_have_unique_identity_distinct_profiles_and_separate_callsigns` |
| Callsign separated from UUID identity | Yes | Yes | Yes | No | same fixture test; authorization call test |
| No authority from armor, appearance or identity metadata | Yes | Yes | Yes | No | fixture test; `CoreProfileView` has no authority field; metadata is never used in `authorize()` |
| Registration without installation | Yes | Yes | Yes | No | `test_full_disposable_acceptance_path_passes_required_stages` |
| Authorized simulated activation | Yes | Yes | Yes | No | full path test; `test_authorization_denial_prevents_activation_inference_and_reservation` |
| Text conversation routing to the selected Core | Yes | Yes | Yes | No | full path test; `test_blank_core_remains_unselected_without_inference_or_reservation` |
| Injected text inference with Core-addressed provenance | Yes | Yes | Yes | No | full path test; inference history assertions |
| Cross-Core memory isolation | Yes | Yes | Yes | No | reference and real `MulticoreMemoryStore` tests |
| Unauthorized cross-Core sharing denial | Yes | Yes | Yes | No | `test_cross_core_memory_isolation_and_unauthorized_sharing_denial`; real-store test |
| Restart/recovery preserves identity | Yes | Yes | Yes | No | `test_recovery_preserves_identity_and_blank_core_stays_unselected` |
| STOP applies regardless of persona | Yes | Yes | Yes | No | `test_stop_denies_both_personas_and_injected_stop_blocks_the_run`; `verify_denials` |
| Authorization denial blocks consequential work | Yes | Yes | Yes | No | `test_authorization_denial_prevents_activation_inference_and_reservation` |
| Blank Core remains unselected | Yes | Yes | Yes | No | `test_blank_core_remains_unselected_without_inference_or_reservation` |
| Invitation decline remains non-activating | Yes | Yes | Yes | No | reference harness stage; real `ChatEngine` decline test |
| Core-free Platform operation | Yes | Yes | Yes | No | `test_platform_only_operation_with_real_chat_engine_and_zero_cores`; harness stage |
| No GPU/compute reservation for inactive Cores | Yes | Yes | Yes | No | `test_blank_core_remains_unselected_without_inference_or_reservation`; reservation ledger |
| Existing installed Cores coexist | Yes | Yes | Yes | No | `test_existing_installed_cores_coexist_with_v6_v7_registrations` |
| Avatar and voice deferred | Yes | Yes | Yes | External | fixture metadata only; no asset claim |
| Real signed Core package installation | No | No | No | Yes | requires Agent 2/3 package and installer owners |
| Live callsign authority reservation | No | No | No | Yes | requires Fleet naming authority and enrolled Platform |
| Live GPU/resource reservation | No | No | No | Yes | requires Platform/Fleet compute authority |

## Installation, activation, configuration and recovery

### Installation

No installation is performed by this workstream. The disposable fixture writes
a canonical Core definition and personal asset files under a caller-owned
temporary directory. The package adapter records registration only and keeps
`installed=False`. Production installation remains with the existing signed
package and lifecycle owners.

### Activation

Activation requires three separate observations:

1. The injected `AuthorizationGate` returns exactly `True` for the exact Core
   UUID, generation and definition fingerprint.
2. The injected `CorePackage.activate()` returns the exact UUID and generation.
3. The Platform text surface explicitly selects that Core.

STOP is checked before registration, activation, routing, inference, memory
work and invitation handling. A stopped gate fails closed with `V6V7Denied`.

### Configuration

The harness receives explicit ports:

- `ProfileResolver`: resolves a `CoreProfileView` by Core UUID.
- `CorePackage`: registration, simulated activation, status, recovery and
  snapshot/restore.
- `CoreMemory`: owner-scoped remember/recall/records/share plus
  snapshot/restore.
- `CoreInference`: registration, injected text conversation, history,
  restart recovery and snapshot/restore.
- `TextPlatform`: enrollment, explicit selection, room text, invitation
  decline and history.
- `SafetyGate`, `AuthorizationGate`, `ResourceAuthority`: STOP, exact
  authorization and compute-reservation evidence.

Fixture configuration is deliberately inert. A callsign, armor material,
presentation string, nickname or identity concept cannot be used as a Core UUID
or as an authorization decision.

### Recovery

Recovery uses package, inference and memory snapshots. Fresh reference adapters
restore the snapshots, inference recovery is invoked, and the recovered
package must return the same UUID, generation, full name, callsign and profile.
Blank Core selection state, memory ownership and the absence of a blank Core
reservation are rechecked after recovery.

## Avatar and voice

Avatar and voice are deferred. The fixture profiles set
`avatar_available=False` and `voice_available=False`. Armor material and
presentation are descriptive fixture metadata only; they do not assert that an
asset, renderer, model or voice exists. Text routing and injected text
inference do not require either asset.

## Security crosswalk

| Boundary | Enforced behavior | Evidence |
| --- | --- | --- |
| Capability versus authority | Profiles, callsigns, armor, appearance, chat text and inference output never call `authorize()`. | authorization call test; profile field inspection |
| Operator STOP | STOP denies both the Vera-like and blank personas before consequential stages. | STOP test; denial stage |
| Authorization denial | A denied activation stops before reservation, selection or inference. | authorization denial test |
| Memory ownership | Recall and record listing are owner-filtered; foreign record persistence is rejected. | reference and real-store tests |
| Memory sharing | Missing authorization, foreign-owner authorization and private security class are denied. Only explicit shareable records produce recipient-owned copies. | sharing tests |
| Callsign identity | Callsign is display text, not a UUID and not an authorization input. | fixture and authorization call tests |
| Armor/appearance metadata | Presentation metadata is inert and cannot substitute for UUID identity or permission. | fixture test; denial stage |
| Blank Core | Unselected Core receives no routed text, inference or reservation. | blank Core test |
| Invitation decline | Decline changes invitation state only; it does not activate or select the Core. | harness stage; real ChatEngine test |
| Core-free Platform | Owner text works with zero enrolled Cores. | real ChatEngine test; harness stage |
| Compute reservation | Reservation evidence exists only for the active Vera-like Core. | resource stage; recovery test |
| Existing Cores | Prelude definitions and installs remain untouched by new registrations. | coexistence test |
| Platform/Fleet admission | Not exercised or replaced. The fixture does not enroll hosts or grant production authority. | documentation boundary |

## Exact integration dependencies

The following adapters must be supplied or confirmed when the external
workstreams land. They are **INFERRED** compatibility seams, not verified
external APIs.

1. **Core #6 profile/package owner:** bind the real profile to a Core UUID and
   provide `CorePackage.register()`, `activate()`, `status()`, `recover()` and
   snapshot/restore. The adapter must preserve unique UUID/number/slug data and
   must not report installation for the disposable fixture.
2. **Core #7 blank owner:** provide the same package/profile seam without
   inventing personal assets. Blank must remain unselected until an explicit
   authorized activation and Platform selection occur.
3. **Memory owner integration:** wrap `sofia.core.multicore.memory` with the
   `CoreMemory` Protocol, or use the real store directly. `ShareAuthorization`
   and `SecurityClass` remain the sharing boundary.
4. **Inference owner integration:** wrap `sofia.core.multicore.inference` with
   the `CoreInference` Protocol. Injected results must keep exact Core UUID,
   generation and conversation identity.
5. **Platform chat owner:** the reference text surface models selection and
   invitation decline. The real `ChatEngine` was exercised independently for
   Core-free operation and invitation decline; a production adapter must map
   `select_core`, `post`, `invite` and `decline_invitation` explicitly.
6. **SAFE/STOP and Fleet/callsign authority owners:** provide a
   `SafetyGate` backed by the existing operator STOP store. Callsign
   normalization and reservation remain with the existing Fleet naming
   authority; this workstream does not reserve a name.
7. **Compute/resource authority:** provide `ResourceAuthority` backed by the
   existing Platform/Fleet resource boundary. The reference ledger does not
   reserve hardware.

## Known blockers

- External Core #6/#7 implementation classes and package definitions were not
  present at baseline `7ea80fb3`; their APIs are UNKNOWN.
- No real signed Core package was installed, launched or recovered on a host.
- No live inference provider, model installation or GPU residency was used.
- No live callsign reservation or Fleet enrollment was performed.
- No avatar renderer or voice asset was created or verified.
- Production adaptation of the narrow Protocols remains required.
- The fixture's reference memory, package, inference, platform and resource
  adapters are in-memory evidence only.

## Verification performed

Executed with:

```text
\\Artemis\Hestia\Users\Crazysodaman\Programing\SofiaAdaLyra\.venv\Scripts\python.exe
```

Focused new suite:

```text
test/test_core_multicore_v6_v7_integration.py
14 passed
```

Related multicore acceptance, integration and memory suite:

```text
test/test_core_multicore_v6_v7_integration.py
test/test_core_multicore_acceptance.py
test/test_core_multicore_integration.py
test/test_core_multicore_memory.py
32 passed
```

Platform chat read/write boundaries used by the real Platform checks:

```text
test/test_platform_chat_general.py
test/test_platform_chat_private.py
test/test_platform_chat_contracts.py
19 passed
```

Existing SAFE operator STOP regressions:

```text
test/test_safe_operator_stop_revision.py
test/test_safe_operator_stop_state_loss.py
15 passed
```

These are source-level and simulated-fixture results. They do not certify a
live Platform, an installed Core, a model process, a GPU reservation or an
enrolled Fleet host.
