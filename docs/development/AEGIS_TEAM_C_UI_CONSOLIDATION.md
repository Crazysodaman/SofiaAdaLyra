# Platform 1.0 Team C | GUI / TUI consolidation

**Branch:** chatgpt/team-c-platform-ui-consolidation-20261108
**Base SHA:** dd7020ce48c06e82684d3439779266de9ea965b4
**Safety:** no production activation, IPC listener, owner ceremony, service writes, or Core import.

## Reconciliation

- **#217:** reuse the Rust authority-free module observation model. Its source flag is a display precondition, not authentication; a separately reviewed Team A adapter must verify each service observation. Missing heartbeat makes health unknown, not uninstalled. A signed removal receipt and new module generation are required for uninstall/reinstall display state.
- **#222:** WinForms preview duplicates #230's window and workflow paths. Do not merge as a second GUI. Preserve #222's useful ideas only through tests/requirements.
- **#228:** WPF proof of concept duplicates the Windows preview entrypoint used by #222. Do not merge it with WinForms or claim a separate supported native binary.
- **#230:** chosen single Windows WinForms PowerShell 5.1 preview, at packaging/gui/Start-AegisControlCenter.ps1. Navigation, disabled actions, high-contrast fallback and theme display do not invoke any service or perform maintenance.
- **#231:** retain exact executable Rust TUI smoke test (Windows and Debian-like Ubuntu CI), plus Rust policy unit tests. Main's existing aegis_tui.rs stays the canonical binary; no second TUI implementation.

## Shared status contract (presentation only)

The Rust ControlCenterView handles OFFLINE, CONNECTING, UNVERIFIED, STALE, RESTARTING, ACCESS_DENIED and OBSERVED states. All state passed to this model is **unauthoritative** until a trusted Team A client verifies the origin and generation.

- Offline, stale and restarting **never** equate to NOT_INSTALLED, REMOVED or HEALTHY; installed lifecycle persists separately.
- Saved settings revision and applied revision are separate. Editor review is mandatory after generation, revision, installation, source trust or permission changes.
- STOP active, unknown SAFE state, denied/unknown permissions, missing generation, or unverified installed lifecycle prevent any offered mutation.
- Even when an action is displayed as \`RecheckWithService\`, this is **not permission or an execution decision**. The authenticated Platform service must recheck current generation, owner approval, SAFE/STOP, revocation, install receipt, signed identity and target.
- The WinForms shell and TUI currently have no approved authenticated management adapter. Both stay read-only and explicitly UNAVAILABLE. A local file, PID, unit status or UI flag cannot supply authority.

## Team A / Team B dependencies (integration blockers)

1. Team A supplies a reviewed versioned, OS-authenticated client for service reads and bounded requests, documented error/safe/revoke semantics and live generation / freshness. Team C must not modify its IPC wire contracts by assumption.
2. Team B supplies signed installed-host GUI packaging and single installer lifecycle. Team C must not duplicate updater/install/uninstall engines or claim signed native installer evidence.
3. Connect GUI/TUI to the *same* approved management client, then test revoked owners, stopped service, host restart, stale observations, module removal receipt, settings revision conflict and service-side rechecks on Windows and Debian 12.

## Tests, evidence and acceptance

- CI: cargo test --locked -p sofia-ui-broker; compiled \`aegis_tui\` smoke (status returns nonzero, NO_COLOR, unknown command denied, safe help); Windows GUI PowerShell \`-Check\` plus Linux source policy checks.
- Required later: actual Windows desktop interactive/keyboard/200%-scaling/high-contrast and Windows/Debian 12 installed-host lifecycle evidence; exact signed release and authenticated service integration.
- #201 rows 31–38: **NOT ACCEPTED** by this preview. Successful tests validate the read-only presentation and binaries only. Release remains NO-GO.
