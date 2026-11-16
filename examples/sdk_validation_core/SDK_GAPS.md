# SDK Validation Core | SDK Gap Log

**Status:** developer evidence log for PROBE-01/02/03/04/05/06/21, plus a
PARTIAL/BLOCKED note for PROBE-18. This is not an acceptance claim and does not
show that the SDK is complete.

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
| GAP-06 | OPEN | No portable Core worker hello/version/start/chat/history/health/stop transport contract. The SDK exposes typed envelopes, not a worker JSON-lines protocol. | `src/sofia/sdk/contracts.py:241-417`; no worker transport module under `src/sofia/sdk/` | Implemented a local bounded JSON-lines protocol using stdlib `json` only. |
| GAP-07 | OPEN | SDK state facades are Platform-mediated protocols only; there is no worker-private durable history implementation or portable local state contract. | `src/sofia/sdk/state.py:33-57` | Wrote worker-private `history.json` with atomic replace under the explicit `--state-dir`. |
| GAP-08 | OPEN | No SDK model-status vocabulary for truthful `MODEL_NOT_LOADED` / `DETERMINISTIC_TEST_ENGINE` reporting. | `src/sofia/sdk/cognition_model.py` has request/response types but no status enum; `src/sofia/sdk/__init__.py:7-53` | Local constants in `examples/sdk_validation_core/runtime.py:35-36`. |
| GAP-09 | OPEN | No portable independently versioned Core runtime package manifest. `python_runtime.py` describes the Platform runtime, not a Core package. | `src/sofia/sdk/python_runtime.py:10,48-114`; `src/sofia/sdk/platform_release.py:12-119` | Authored `assets/runtime_release.json` and bound its digest into `definition.json`. |

## Public SDK APIs actually used

- `AegisIdentity`, `IdentityKind` from `src/sofia/sdk/identity.py:20-91`, exported at `src/sofia/sdk/__init__.py:9-13`.
- `ProtocolVersion`, `ProtocolVersionRange`, `SDK_PROTOCOL_VERSION`, `negotiate_protocol` from `src/sofia/sdk/contracts.py:52-116`, exported at `src/sofia/sdk/__init__.py:14-22`.
- `CoreDefinition.from_payload` / `CoreDefinition.digest` from `src/sofia/sdk/core_definition.py:73-95` via the public submodule (GAP-01).

No other `sofia.*` import appears in the runtime, entrypoint or package
`__init__`. The isolated subprocess check reports the complete loaded module
list and `sofia_core_loaded: false`.

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

- SDK-facing runtime: `examples/sdk_validation_core/runtime.py` (491 lines).
- Process entrypoint: `examples/sdk_validation_core/entrypoint.py` (17 lines).
- Package initializer: `examples/sdk_validation_core/__init__.py` (1 line).
- Conformance tests: `test/test_sdk_validation_core.py` (257 lines).
- Public SDK modules used: `sofia.sdk` facade plus `sofia.sdk.core_definition`
  submodule.
- Forbidden/private API escapes attempted: none. No bypass was added.
- Static evidence: no `sofia.core`, `sofia.application` or `sofia.platform`
  import in the example source; subprocess `-I` check confirms `sofia.core` is
  absent after provisioning and runtime imports.
- Assumptions: the installed editable `sofia` package is importable under
  `python -I`; the worker is launched directly rather than supervised by a real
  Platform; `--check-imports` and the local JSON-lines protocol are scaffold
  aids, not an SDK transport.
