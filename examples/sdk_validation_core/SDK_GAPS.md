# SDK Validation Core | SDK Gap Log

**Status:** developer evidence log for PROBE-01/02/03/04/05/06/21, plus
PARTIAL/BLOCKED notes for PROBE-09 and PROBE-18. This is not an acceptance
claim and does not show that the SDK is complete.

The runtime in this directory imports only the Python standard library and
modules under `sofia.sdk`. It never imports `sofia.core`, `sofia.application`,
Platform authority internals or Sofía assets. Where the SDK is missing an
operation, this file records the gap by exact source location instead of adding
a private import.

## Gap summary

| ID | Status | Gap | Exact source reference | Current scaffold workaround |
|---|---|---|---|---|
| GAP-01 | OPEN | `CoreDefinition`, `CoreAssetReference` and `CORE_DEFINITION_SCHEMA` are not re-exported by the top-level SDK facade. | `src/sofia/sdk/__init__.py:7-53`; `src/sofia/sdk/core_definition.py:14,26,35` | Imported the public submodule path `sofia.sdk.core_definition`. |
| GAP-02 | OPEN | `ArtifactReference` is not re-exported by the top-level SDK facade. | `src/sofia/sdk/artifact.py:22`; absent from `src/sofia/sdk/__init__.py:7-53` | Used only through `CoreDefinition` asset references. |
| GAP-03 | OPEN | A Core definition has no field that declares its private scope. Scope is only implied by an `AuthorityProjection.audience_kind`. | `src/sofia/sdk/core_definition.py:35-47,67-71`; `src/sofia/sdk/contracts.py:196` | Added `scope.json` with `audience_kind: private` and a digest of the SDK definition. |
| GAP-04 | OPEN | No public signed-artifact/Core-definition verification facade. SDK metadata carries `signer_key_id` and `signature_scheme` but does not verify bytes. | `src/sofia/sdk/platform_library.py:73-74,218-228`; `src/sofia/sdk/platform_release.py:45`; `src/sofia/sdk/core_definition.py:35-47` | None. PROBE-18 is BLOCKED; see below. |
| GAP-05 | OPEN | Signing and verification helpers exist only in Platform-private modules, not in the SDK. | `src/sofia/platform/dev/release_signing.py:16,36,48`; `src/sofia/platform/ops/component_install.py:52,64,103`; `src/sofia/platform/ops/core_definition.py:25-56`; `src/sofia/platform/modules/library_signed_manifest.py:65,112-116` | None. Platform imports are forbidden for an independent Core. |
| GAP-06 | ADDRESSED | The SDK now exposes a portable Core worker hello/version/start/chat/task/history/health/stop transport contract. | `src/sofia/sdk/runtime.py:436-453` (`CoreRuntimeAdapter`), `:82-88` (typed outcomes), `:248-436` (strict request/response models), `:481-489` (exact version negotiation), `:559-607` (bounded JSON-lines), `:637-758` (dispatcher), `:761-801` (serve loop) | The example uses `sofia.sdk.runtime` for wire validation, deadline, idempotency and lifecycle dispatch. |
| GAP-07 | OPEN | SDK state facades are Platform-mediated protocols only; there is no worker-private durable history implementation or portable local state contract. The runtime facade defines a `history` operation, not storage. | `src/sofia/sdk/state.py:33-57`; `src/sofia/sdk/runtime.py:72-79` (history operation only) | Wrote worker-private `history.json` with atomic replace under the explicit `--state-dir`. |
| GAP-08 | OPEN | No SDK model-status vocabulary for truthful `MODEL_NOT_LOADED` / `DETERMINISTIC_TEST_ENGINE` reporting. | `src/sofia/sdk/cognition_model.py` has request/response types but no status enum; `src/sofia/sdk/__init__.py:7-53` | Local constants in `examples/sdk_validation_core/runtime.py:44-45`. |
| GAP-09 | OPEN | No portable independently versioned Core runtime package manifest. `python_runtime.py` describes the Platform runtime, not a Core package. | `src/sofia/sdk/python_runtime.py:10,48-114`; `src/sofia/sdk/platform_release.py:12-119` | Authored `assets/runtime_release.json` and bound its digest into `definition.json`. |
| GAP-10 | OPEN | Runtime idempotency results are memory-only. A duplicate key is suppressed within one worker process, but the cache is not durable across restart. | `src/sofia/sdk/runtime.py:637-758` (`RuntimeDispatcher`); no persistence facade exists | Duplicate suppression is proven within a process; durable history remains separate. |
| GAP-11 | OPEN | There is no cross-process cancellation handle or cancel operation. The facade can report `RuntimeCancelled` and enforce deadlines, but cannot signal a running task from another process. | `src/sofia/sdk/runtime.py:117-121` (`RuntimeCancelled`), `:723-730` (deadline check) | Deadline expiry and adapter-reported cancellation only. |
| GAP-12 | OPEN | `sofia.sdk.runtime` is a public submodule but is not re-exported by the top-level `sofia.sdk` facade. | `src/sofia/sdk/runtime.py:1-838`; absent from `src/sofia/sdk/__init__.py:7-53` | Imported the public submodule path `sofia.sdk.runtime`. |
| GAP-13 | OPEN | Request payloads are generic bounded JSON objects; there are no typed per-operation provider, settings or principal payload contracts matching SDKCOMP-10. | `src/sofia/sdk/runtime.py:196-245` (operation payload validation), `:248-320` (request model) | Chat and a deterministic task only; no provider/settings claims. |

## Public SDK APIs actually used

- `AegisIdentity`, `IdentityKind` from `src/sofia/sdk/identity.py:20-91`, exported at `src/sofia/sdk/__init__.py:9-13`.
- `ProtocolVersionRange`, `SDK_PROTOCOL_VERSION` from `src/sofia/sdk/contracts.py:76-116`, exported at `src/sofia/sdk/__init__.py:14-22`.
- `CoreDefinition.from_payload` / `CoreDefinition.digest` from `src/sofia/sdk/core_definition.py:73-95` via the public submodule (GAP-01).
- `RuntimeResult`, `RuntimeDenied`, `negotiate_runtime_protocol`, `serve` and `MAX_RUNTIME_TEXT_CHARS` from `src/sofia/sdk/runtime.py:398-435`, `:101-103`, `:481-489`, `:761-801` via the public submodule (GAP-12).

No other `sofia.*` import appears in the runtime, entrypoint or package
`__init__`. The isolated subprocess check reports the complete loaded module
list and `sofia_core_loaded: false`.

## PROBE status

- **PROBE-04 | FOCUSED_TESTED, not installed/accepted.** The example runtime and
  entrypoint use only the portable `sofia.sdk.runtime` facade. `-P -s`
  subprocess import checks with the worktree `src` load no `sofia.core`,
  `sofia.application` or `sofia.platform`. Signed installed-package and
  Platform supervision remain PROBE-07/PROBE-18 work.
- **PROBE-06 | FOCUSED_TESTED.** Deterministic text conversation, independent
  durable history, after-restart continuity, bounded requests and duplicate
  suppression are covered by `test/test_sdk_validation_core.py` and
  `test/test_sdk_runtime_facade.py`. Status remains truthful
  `MODEL_NOT_LOADED` / `DETERMINISTIC_TEST_ENGINE`; no real inference claim.
- **PROBE-09 | OPEN, not attempted here.** Invoking an independently packaged
  signed `dev.aegis.reference` module through an authenticated SDK/Platform
  capability request still requires GAP-04/GAP-05 and installed lifecycle work.

## PROBE-18 status: PARTIAL / BLOCKED

**Blocked by GAP-04 and GAP-05.** A negative signed-artifact test (wrong signer
or tampered manifest is refused) cannot be implemented against existing SDK
helpers because no SDK signing or verification facade exists. The only working
verifiers are Platform-private:

- `src/sofia/platform/ops/core_definition.py:25-56` (`CoreDefinitionVerifier`)
- `src/sofia/platform/ops/component_install.py:64-131` (`Ed25519ComponentSignatureVerifier`)
- `src/sofia/platform/modules/library_signed_manifest.py:65-116` (`verify_publisher_signed_module_manifest`)
- `src/sofia/platform/dev/release_signing.py:16-60` (ephemeral signing helper; Platform-dev, not SDK)

**Missing SDK API required to unblock:** a public, fail-closed SDK facade such
as `sofia.sdk.artifact_verification.verify_signed_manifest(manifest_bytes,
signature, *, signer_key_id, trusted_keys)` returning a verified immutable
manifest or raising distinct `WrongSigner` / `TamperedManifest` /
`UnsupportedSignatureScheme` errors, with an equivalent
`verify_signed_core_definition(...)` over `CoreDefinition.canonical_bytes`.
Until that exists, this scaffold records the blocker rather than importing
Platform internals.

## PROBE-21 developer effort

- SDK-facing runtime facade: `src/sofia/sdk/runtime.py` (838 lines).
- SDK-facing example runtime: `examples/sdk_validation_core/runtime.py` (379 lines).
- Process entrypoint: `examples/sdk_validation_core/entrypoint.py` (17 lines).
- Package initializer: `examples/sdk_validation_core/__init__.py` (1 line).
- Core conformance tests: `test/test_sdk_validation_core.py` (326 lines).
- Facade conformance tests: `test/test_sdk_runtime_facade.py` (397 lines).
- Public SDK modules used: `sofia.sdk` facade plus `sofia.sdk.core_definition`
  and `sofia.sdk.runtime` submodules.
- Forbidden/private API escapes attempted: none. No bypass was added.
- Static evidence: no `sofia.core`, `sofia.application` or `sofia.platform`
  import in the example or facade source; subprocess checks confirm
  `sofia.core` is absent after provisioning and runtime imports.
- Assumptions: the worktree `src` is placed on `PYTHONPATH` for isolated
  subprocess tests; the worker is launched directly rather than supervised by a
  real Platform; `--check-imports` remains a scaffold aid, not an SDK transport.
