# Rust modernization source evidence index

**Audited commit:** `bb1fd13b6abfabfe6d30c356d06ae8469533deac`

This index records the source set used for the accompanying planning report. It
is an inspection map, not acceptance evidence for an unexecuted Rust system.

## Repository instructions and packaging

- `AGENTS.MD`
- `pyproject.toml`
- `packaging/components.toml`
- `src/sofia/platform/verify/component_artifacts.py`
- `.github/workflows/compatibility.yml`
- `.github/workflows/package-tests.yml`
- `.github/workflows/manual-verify.yml`
- `.github/workflows/release-candidate.yml`
- `.github/workflows/debian-release-candidate.yml`
- `.github/workflows/g4-core-link-pr.yml`
- `.github/workflows/g5-recovery-pr.yml`
- `.github/workflows/go-live-component-install-pr.yml`
- `.github/workflows/go-live-core-worker-pr.yml`

## Architecture and acceptance records

- `docs/sofia2/ARCHITECTURE.md`
- `docs/sofia2/COMPONENT_UPDATES_AND_UNIFIED_SDK_V1.md`
- `docs/sofia2/UNIVERSAL_PLATFORM_CORE_LINK_AND_MULTI_CORE_BINDING_V1.md`
- `docs/sofia2/HARDWARE_NEUTRAL_FLEET_AND_INFERENCE_CONTRACT_V1.md`
- `docs/development/venus-artemis-runtime-topology-2026-10-11.md`
- `docs/development/v18-operating-layer-architecture-decision.md`
- `docs/development/companion-autonomy-contract.md`
- `docs/development/companion-v0.1.md`
- `docs/development/pkg-ui-current-main.md`
- `docs/development/pkg-ui-sofia-workbench-concept.md`
- `docs/development/pkg-ui-windows-workbench.md`
- `docs/development/tray-settings-and-wardrobe-editor.md`
- GitHub issue #120 public body, observed 2026-11-04 UTC
- GitHub issue #129 public body, observed 2026-11-04 UTC
- inactive Constitution 2.0 proposal branch, especially the proposal,
  implementation impact, and final review handoff

## Platform roles, SDK, Core Link, and Fleet

- `src/sofia/platform/config/roles.py`
- `src/sofia/sdk/contracts.py`
- `src/sofia/sdk/core_link.py`
- `src/sofia/sdk/principals.py`
- `src/sofia/sdk/state.py`
- `src/sofia/platform/core_link/access.py`
- `src/sofia/platform/core_link/binding.py`
- `src/sofia/platform/core_link/conversation.py`
- `src/sofia/platform/core_link/transport.py`
- `src/sofia/platform/distributed/https_transport.py`
- `src/sofia/platform/distributed/tls.py`
- `src/sofia/platform/distributed/identity_durable.py`
- `src/sofia/platform/distributed/endpoint_bound_gateway.py`
- `src/sofia/platform/distributed/endpoint_policy_durable.py`

## Workers, supervision, state, SAFE, and RUN

- `src/sofia/platform/core_worker/process.py`
- `src/sofia/platform/modules/process_worker.py`
- `src/sofia/platform/modules/host_authority.py`
- `src/sofia/platform/run/components.py`
- `src/sofia/platform/run/supervisor.py`
- `src/sofia/platform/run/runtime_service.py`
- `src/sofia/platform/run/watchdog_service.py`
- `src/sofia/platform/run/host.py`
- `src/sofia/platform/run/heartbeat.py`
- `src/sofia/platform/run/lease.py`
- `src/sofia/platform/run/generation.py`
- `src/sofia/platform/run/effects.py`
- `src/sofia/platform/run/host_effect_attestation.py`
- `src/sofia/platform/safe/permissions.py`
- `src/sofia/platform/safe/execution_approval.py`
- `src/sofia/platform/safe/operator_stop.py`
- `src/sofia/platform/safe/secret_store.py`
- `src/sofia/platform/state/sqlite_access.py`
- `src/sofia/platform/state/sdk_facade.py`
- `src/sofia/platform/state/canonical_sqlite.py`
- `src/sofia/platform/state/plane.py`

## Existing UI and launch surfaces

- `src/sofia/platform/launcher.py`
- `src/sofia/platform/ui_launchers.py`
- `src/sofia/modules/ui/core_link_desktop.py`
- `src/sofia/modules/ui/core_link_tray.py`
- `src/sofia/modules/ui/core_link_control_center.py`
- `src/sofia/modules/ui/desktop.py`
- `src/sofia/modules/ui/settings_window.py`
- `src/sofia/modules/ui/settings_sections.py`
- `src/sofia/modules/ui/tray_agent.py`
- `src/sofia/modules/ui/tray_launcher.py`
- `src/sofia/modules/ui/windows_tray.py`
- `src/sofia/modules/ui/windows_startup.py`
- `src/sofia/modules/ui/notifications.py`
- `src/sofia/modules/ui/avatar2d_renderer.py`
- `src/sofia/modules/ui/avatar3d_renderer.py`

## Screen capture and owner authorization follow-up

- `src/sofia/modules/vision/capture.py`
- `src/sofia/modules/vision/windows_capture.py`
- `src/sofia/modules/vision/consent.py`
- `src/sofia/modules/vision/desktop_control_cli.py`
- `src/sofia/modules/vision/linux_capture.py`
- `src/sofia/modules/ui/settings_sections.py`
- `src/sofia/platform/safe/owner_browser.py`
- `src/sofia/platform/safe/owner_secret.py`
- `src/sofia/platform/safe/owner_webauthn.py`
- `src/sofia/platform/safe/permissions_cli.py`
- `src/sofia/platform/safe/execution_approval.py`

## Focused existing tests inspected

- `test/test_sdk_component_contracts.py`
- `test/test_sdk_state_facade.py`
- `test/test_core_link_binding.py`
- `test/test_core_link_conversation.py`
- `test/test_core_link_desktop.py`
- `test/test_platform_module_host_local_state.py`
- `test/test_platform_module_process_worker.py`
- `test/test_module_lifecycle_v1.py`
- `test/test_run_component_supervisor.py`
- `test/test_run_supervisor.py`
- `test/test_run_windows_service_spec.py`
- `test/test_platform_ui_launchers.py`
- `test/test_ui_process_lock.py`
- `test/test_ui_tray_lifecycle.py`
- `test/test_ui_windows_startup.py`
- `test/test_screen_capability_authority.py`
- `test/test_vision_action_workflow.py`
- `test/test_vision_cross_platform.py`
- `test/test_permission_runtime_wiring.py`
- `test/test_safe_owner_webauthn.py`
- `test/test_canonical_sqlite_protection.py`
- `test/test_memory_canonical_state_fencing.py`
- `test/test_state_replication.py`
- `test/test_remote_mtls_transport_acceptance.py`
- distributed identity, authorization, endpoint policy, TLS, agent service, and
  Fleet tests listed under `test/test_distributed_*.py`

## Quantitative static observations

- Rust manifests/source/UI definitions found: **0**.
- Python files under `src/sofia/platform` importing `sofia.core.*`: **75**.
- Python files under `src/sofia/modules/ui` importing `sofia.core.*`: **14**.
- Open PRs on the public PR page: **8**, all drafts.
- Current Python package markers: **22**.

These counts are bound to the audited commit and must be refreshed after the
open development PRs change `main`.

## Exact-SHA CI evidence refreshed 2026-11-04 UTC

- Package matrix run `41827400956`: 15 passed jobs; failed `pkg_social`,
  `pkg_core`, `pkg_ui`, `pkg_know`, `pkg_dev`, `pkg_safe`, `pkg_integrate`.
- Windows RC run `41827400858`: full revision-bound verification failed;
  downstream keyless provenance skipped.
- Debian RC run `41827400887`: full installed-wheel verification failed;
  downstream keyless provenance skipped.
- Manual Verification run `41827400879`: revision-pinned verification failed.
- Local focused reproduction of the permission CLI and protected approval
  tests: **2 failed**, with CLI return/exception and generalized-owner-auth/
  FIDO2 message-contract mismatches respectively.

Public workflow annotations establish the RC/Manual failing steps, but their
diagnostic logs were not independently available. Attribution of those three
jobs to the shared package mismatch remains **INFERRED**, not observed.
