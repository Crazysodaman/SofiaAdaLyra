# Project Aegis | SDK Compatibility Update Specification

**Status:** Design and implementation handoff, not an applied source update. **Date:** 2026-11-16. **Source:** `main` `b330b079d01639c2f2f49a60202c3a93f1874bac`.

## Direct finding
Python `SDK_PROTOCOL_VERSION = ProtocolVersion(1, 0)` and Rust `SUPPORTED_PROTOCOL = "1.0"` currently match in the audited source. The version string does not prove complete module/Core/GUI compatibility. Portable module façade and full consumer graph remain unfinished; current SDK reference Core/Platform are deliberately in-process test doubles.

## Components to review

| Python SDK | Migration/compatibility focus |
|---|---|
| `__init__.py`, `contracts.py`, `contract_wire.py` | Public exports, wire bounds/versioning, strict JSON/shape, stable outcomes |
| `identity.py`, `core_definition.py`, `artifact.py` | Immutable independently signed Core identities/definitions, exact asset references |
| `core_link.py`, `platform_management.py`, `platform_management_client.py`, `platform_management_mutation.py`, `platform_management_response.py`, `platform_settings_view.py` | Exact Core selection, auth, event/settings revision, management and status parity |
| `platform_library.py`, `platform_release.py`, `fleet_admission.py`, `python_runtime.py` | Signed delivery, installed runtime, Fleet trust and ABI rules |
| `module_settings.py`, `tool_binding.py`, `state.py` | Module-facing portable contracts and capability-vs-authority isolation |
| `cognition.py`, `cognition_engine.py`, `cognition_json.py`, `cognition_model.py`, `voice_expression.py`, `principals.py` | Provider and modality-neutral contracts; preserve per-Core privacy |

| Rust SDK-facing crate | Migration/compatibility focus |
|---|---|
| `sofia-contracts` | Python/Rust canonical JSON and schema parity; protocol v1.0 |
| `sofia-core-link` | Real peer/session/auth and async/sync client compatibility |
| `sofia-platform-lifecycle` | Worker generation/version, isolated update and OS release receipts |
| `sofia-ui-broker` | Versioned management and GUI/TUI parity, including exact error semantics |

## Update sequence

1. Inventory every public export, importer, manifest and installed package. Freeze a machine-readable compatibility manifest with exact SHA.
2. Review current Python/Rust schemas and golden negative fixtures, including identity, authority projection, module requests/responses, management, Core Link, Fleet, Artifact Library and settings.
3. Implement the minimal portable Core facade and module facade without importing `sofia.core` or privileged Platform internals.
4. Add compatibility negotiation for additive minor changes **only when both peers support it**. Keep protocol 1.0 if no wire change is necessary.
5. Add versioned signed artifact manifest and consumption matrix for all 55 catalog entries. `NOT_IMPLEMENTED` and `UNVERIFIED` are allowed truthful statuses.
6. Make SDK contracts/codegen/tests change together. Maintain old/new contract fixture fixtures and reject unsafe downgrade or mismatched ABI.
7. Build the independent `SDK Validation Core` as the *real* consumer. Every private-import escape is an SDK defect report.
8. Run Windows/Debian installed Python/Rust tests and clean exact SHA release gating. Then propose signed rollout with component-scoped restart and rollback.

## Must-not-break security properties

- A `CoreDefinition` is not an executable grant; the SDK carries requests, not owner authority.
- Version or model switching never changes Core identity, memory writers or private assets.
- STOP, revocation, wrong Core identity, generation and release digest deny execution.
- The model/inference runner remains optional and does not load on Core-free boot.
- Auto-discovery does not auto-install; accepted signed package still requires installation/activation approval.
- Missing runtime host/process tests mean no production compatibility claim.

Refer to the `SDKCOMP-01` through `SDKCOMP-30` implementation program and `SDK-A01` through `SDK-A18` acceptance table in the unified master for exact task ownership.
