# Aegis Platform 1.0 acceptance

Platform-only shakedown and full-project shakedown are separate verdicts.
Both are **NO**. G8 (#129) remains deferred. Authority: #120; original
700-task coding register #132 remains unchanged. No production activation.

## Reconciled source inventory

Inspected baseline: `81371ac8ca45f00657f3eed02a05d8b11a0be3fb`.
No open PRs at campaign startup. Existing worktrees were preserved.

| Area | Existing production source | Observed implementation / remaining dependency |
| --- | --- | --- |
| Identity | `platform/state/installation_identity.py`, `sdk/identity.py` | Persistent UUID/key and AEG-P serial; explicit bootstrap, corruption refusal. Reuse PR192. Installed service composition and reviewed recovery remain. |
| Owner security | `platform/safe/`, `sdk/principals.py` | Existing signed exact approval, STOP, replay/audit contracts; reuse PR193. Service IPC must call these owners. |
| Fleet | `platform/ops/callsigns.py`, `platform/distributed/` | Atomic designated local registry and durable admission/revocation. Remote naming transport is missing; no global offline success. |
| Signed Core boundary | `platform/ops/core_definition.py`, `sdk/core_definition.py` | Existing signed verifier and runtime/asset digests (PR195). Governed durable stage/activate/remove interface remains. |
| Generic workers | `platform/core_worker/`, `platform/cognition_provider.py` | Core-free worker/provider implementations (PR196/197); optional inference is separate from baseline. No real personal writer authority is granted. |
| Rust Core Link | `rust/crates/sofia-core-link/` | Current-selection-fenced status adapter (PR199); lifecycle-changing operations need separate owner authority. |
| Broker | `rust/crates/sofia-ui-broker/` | Durable Windows/Unix journal (PR198), policy foundation. Running authenticated IPC, session/DND observers and native tray remain. |
| Rust service | `rust/crates/sofia-platform-lifecycle/` | Observation/reference contracts only: no process spawning, SCM dispatcher or systemd service owner. Highest-priority implementation gap. |
| Legacy services | `platform/run/runtime_service.py`, `platform/run/release_process.py` | Python runtime service imports personal Core settings and launches legacy runtime. Cannot certify as Core-free Rust service. |
| Modules | `platform/modules/`, `platform/application/module_lifecycle.py` | Existing generic manifests and local-state lifecycle; complete signed isolated installed-host lifecycle still requires verification. |
| Update/recovery | `platform/ops/platform_install.py`, `platform/run/active_release.py`, `platform/state/` | Existing staging/recovery/verified restore components; Platform-only service composition and installed OS upgrade/reinstall acceptance remain. |
| Packaging | `packaging/components.toml`, `platform/verify/component_artifacts.py` | Separate SDK/Platform/Core wheels. Rust binaries and OS service installers are not yet a complete Platform release. |

Paths above are under `src/sofia/` unless prefixed `rust/` or `packaging/`.
A wheel import, unit test, or compiled crate is not installed-host service evidence.

## Platform-only release matrix

States: PASS, FAIL, BLOCKED, NOT TESTED. FAIL denotes a known missing mandatory
production path; NOT TESTED means no complete disposable installed-host acceptance
receipt, even where narrower unit/installed-wheel evidence exists.
Every row needs exact source SHA, test IDs, CI run, artifact digests and actual
Windows/Debian host observations before PASS. This baseline SHA is the source
reference for all rows below; no installed-host receipt is asserted.

| ID | Requirement | State | Windows | Debian 12 | Missing release evidence / next dependency |
| --- | --- | --- | --- | --- | --- |
| 01 | Fresh Platform-only install | NOT TESTED | NOT TESTED | NOT TESTED | Complete signed OS installer, not wheels alone |
| 02 | No Core installed | NOT TESTED | NOT TESTED | NOT TESTED | Minimal installed wheels covered by `test_platform_optional_dependencies`; final OS release receipt pending |
| 03 | No canonical Core DB | NOT TESTED | NOT TESTED | NOT TESTED | Same minimal test; service-wide file access acceptance pending |
| 04 | Permanent UUID | NOT TESTED | NOT TESTED | NOT TESTED | Existing identity tests; reinstall/reboot OS receipt pending |
| 05 | Core-free health/startup | FAIL | NOT TESTED | NOT TESTED | Running Rust service composition |
| 06 | Windows service start/stop | FAIL | NOT TESTED | NOT TESTED | SCM integration |
| 07 | Debian service start/stop | FAIL | NOT TESTED | NOT TESTED | systemd integration |
| 08 | Abrupt exit recovery | FAIL | NOT TESTED | NOT TESTED | Rust supervisor and durable generation |
| 09 | No duplicate supervisor | FAIL | NOT TESTED | NOT TESTED | OS locking / lifetime ownership |
| 10 | Authenticated CLI/IPC | FAIL | NOT TESTED | NOT TESTED | Canonical SAFE-backed management boundary |
| 11 | SAFE/STOP | NOT TESTED | NOT TESTED | NOT TESTED | Existing SAFE tests; running service integration |
| 12 | Owner revocation | NOT TESTED | NOT TESTED | NOT TESTED | Existing verified grants; service integration |
| 13 | Fleet enrollment | NOT TESTED | NOT TESTED | NOT TESTED | Existing disposable mTLS/admission tests; release host receipts |
| 14 | Fleet revocation | NOT TESTED | NOT TESTED | NOT TESTED | Admission/removal/stale-trust regressions; host receipts |
| 15 | Remote naming authority | FAIL | NOT TESTED | NOT TESTED | Authenticated remote registry adapter |
| 16 | Offline names | NOT TESTED | NOT TESTED | NOT TESTED | Existing cached/unconfirmed client tests; remote reconnect |
| 17 | Generic signed module install | NOT TESTED | NOT TESTED | NOT TESTED | Installed signed artifact lifecycle |
| 18 | Module rollback/lifecycle | NOT TESTED | NOT TESTED | NOT TESTED | Isolation, limits and crash/revocation acceptance |
| 19 | Signed update/recovery | NOT TESTED | NOT TESTED | NOT TESTED | OS service upgrade/interruption receipts |
| 20 | Identity through reinstall | NOT TESTED | NOT TESTED | NOT TESTED | Uninstall/reinstall OS receipts |
| 21 | Invalid Core rejection | NOT TESTED | NOT TESTED | NOT TESTED | Existing signature/path tests; installed package service boundary |
| 22 | Signed synthetic Core install | FAIL | NOT TESTED | NOT TESTED | Governed stage/activation interface |
| 23 | Synthetic start/stop/detach | FAIL | NOT TESTED | NOT TESTED | Governed process lifecycle |
| 24 | Removal leaves Platform healthy | FAIL | NOT TESTED | NOT TESTED | Running Core-free service |
| 25 | Cross-platform compatibility | NOT TESTED | NOT TESTED | NOT TESTED | Existing contract CI; complete release candidate |
| 26 | Recovery without second writer | NOT TESTED | NOT TESTED | NOT TESTED | Existing writer fencing; new service composition |
| 27 | Native Rust regressions | NOT TESTED | NOT TESTED | NOT TESTED | Existing R1/R2 CI; release service integration tests pending |
| 28 | Installed-wheel isolation | NOT TESTED | NOT TESTED | NOT TESTED | Component CI + minimal dependency test; final exact release receipt pending |
| 29 | Exact-SHA release CI | NOT TESTED | NOT TESTED | NOT TESTED | Distinct Platform-only gate plus signed release artifacts |
| 30 | Complete operator runbook | FAIL | NOT TESTED | NOT TESTED | Installed service, recovery and diagnostic commands |

## Audit reconciliation

A: uncaught signed-definition CLI rejection did not reproduce at baseline:
`CoreDefinitionRejected` inherits `PermissionError` / `OSError`, already caught.
Eight denial variants and an actual subprocess now verify structured REJECTED,
exit 2, no traceback and no database creation.

B: reproduced prohibited returned proposals despite disabled worker/request tools.
Reject proposals before releasing the inference response; proposal data is never
execution authorization.

C: signed-definition verifier already checks root/ancestors. A separate installed
worker digest erased ancestor redirects through resolve(); explicit and implicit
roots and nested redirects now have fail-before-read regressions.

D: baseline metadata already omits Ollama and transport imports are lazy. Add an
explicit optional extra and prove a real pip installation using only SDK/Platform
and mandatory dependencies, without preinstalled Ollama or Core.

E: retain Fleet stale trust, verified durable admission and removal/revocation
regressions. No retired credentials are reintroduced.

The five live Ollama failures stay visible in full-project suite evidence.
They are not a Platform-only dependency. Neither verdict is promoted by separating
CI scopes. Next batch: authoritative Rust service process/lifetime ownership.
