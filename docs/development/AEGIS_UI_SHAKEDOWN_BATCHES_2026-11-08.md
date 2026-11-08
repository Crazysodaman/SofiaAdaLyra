# AEGIS UI shakedown batches (owner directive 2026-11-08)

Authoritative implementation plan for the owner directive that includes the
native GUI, TUI and their essential management functionality in the expanded
Platform 1.0 shakedown. Batch definitions are binding for scope and review;
every batch ends with a checkpoint, targeted tests, CI evidence and an exact
source SHA recorded here and in
[PLATFORM_1_0_ACCEPTANCE.md](PLATFORM_1_0_ACCEPTANCE.md).

Boundary commitments inherited from the directive and existing design docs:

* One authenticated, service-owned management API for GUI, TUI and CLI. No
  duplicate managers, stores or security authorities.
* Existing Rust Platform service and UI broker foundations are reused
  (`rust/crates/sofia-contracts`, `rust/crates/sofia-ui-broker`,
  `rust/crates/sofia-platform-lifecycle`, the Core-Free service adapter
  sessions and `sofia.platform.modules.control_center` read-only
  projections). The `sofia-ui-broker` crate remains the appearance-policy
  journal component; new management wire contracts extend `sofia-contracts`
  schema discipline instead of overloading that crate.
* Native Rust-based GUI/TUI components where appropriate; framework choice is
  evaluated and recorded before implementation merges. GUI candidates:
  Rust-backed Tauri 2 shell (already named in R-plans) with CC-1 beginning
  read-only. TUI candidates: Rust-native terminal crate; the Python fallback
  oracle exists only where an installed Python surface already is.
* The approved shared theme is applied to both interfaces
  ([AEGIS_SHARED_GUI_TUI_THEME.md](../roadmaps/AEGIS_SHARED_GUI_TUI_THEME.md)).
* Service-side authorization for every protected operation; the API layer
  never mints authority (SAFE owner ceremony stays the only fresh-proof
  source; FIDO2 remains optional/dormant).
* GUI and TUI are independently installable; headless Platform operation is
  never dependent on either.
* No Venus/Artemis production deployment and no real personal Core
  activation. Disposable installed systems only.

Out of minimum shakedown scope (preserved from AG-D005/AG-D007 fences):
advanced personal SofA-a Workbench, the full Model Manager and autonomous
Core self-management.

## Batches

| Batch | Scope | Acceptance rows | Tests / evidence committed | Exact source SHA |
| --- | --- | --- | --- | --- |
| U0 | Reconciliation of design TODOs, AG-D022/AG-D024/theme specs, rows 31-38 (this document) | (documentation only) | docs commit: reconciliation diff reviewed | pending |
| U1 | Versioned authenticated management API skeleton over existing SAFE/STOP/session authority: read-only status + snapshot/event live updates, CLI verbs first | 31 | Rust contract tests, Python adapter tests, platform-only gate run, Windows+Debian host receipts | pending |
| U2 | Terminal Control Center on Windows + Debian 12 over the U1 API, with shared-theme tokens, reconnect/stale handling and read-only manager views (Cores/Modules/Settings/Diagnostics/Updates/Revolutions from AG-D006/AG-D013 sources) | 32, 33, 34 via parity protocol (AG-D024) | TUI contract tests, Windows Terminal + Debian 12 disposable-host receipts, parity table | pending |
| U3 | GUI Control Center shell (Windows): CC-1 read-only shell + CC-2 manager views over the same U1 API; independently installable | 34, 35 | GUI smoke contract tests, disposable Windows host receipts, parity table | pending |
| U4 | Governed protected effects: Core Manager (AG-D004) and Module Manager (AG-D006, including live status, uninstall/reinstall policy and Core-originated removal proposals) through exact scoped approvals on both interfaces | 35, 36 | SAFE consumption tests, anti-replay/STOP denials per client, disposable receipts, parity table | pending |
| U5 | Security/Approvals, Updates/Recovery and Diagnostics surfaces + shared-theme verification + independent installer receipts; parity review closeout honoring AG-D024 | 37, 38 | Theme diff review, installer receipts, complete parity closeout | pending |

No batch may merge duplicates of existing managers/registries/security
authorities; extensions land inside the existing platform-owned stores and
SAFE boundaries.

Row 10 (Authenticated CLI/IPC) remains a fail-closed prerequisite: U1 only
proceeds when its row-10 boundary work (B3 in the takeover work order) is
integrated. No acceptance row is promoted to PASS without the documented
receipt discipline.
