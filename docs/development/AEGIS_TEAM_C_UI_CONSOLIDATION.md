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


## Coordinator C-001 continued implementation

The provisional GUI implementation is *only* the WinForms PowerShell 5.1 Control Center from #230/#243. #222 and #228 stay as reference prototypes; neither is an independently maintained deployment target. The existing Rust \`aegis_tui\` binary remains canonical for terminal control, including SSH/NO_COLOR tests. Both consume the one shared 22-token theme manifest; the Windows UI additionally honors OS high-contrast preference.

### New authority-free client-side state

\`rust/crates/sofia-ui-broker/src/control_center_session.rs\` defines a display-only \`DisplayReadSource\` integration seam. It has no IPC transport, wire format, service executor, owner token, approval, or independent signature verifier. The only wired implementation is \`OfflineReader\`, which never manufactures a healthy host. This is intentionally a **not-yet-integrated client contract**, not evidence of authenticated management.

The session retains installed lifecycle metadata while disconnect/restart/stale makes health unknown; it fences replayed sequence, decreasing generation, changed Platform identity, settings revision rollback, impossible saved/applied revision pairs, and a removal-receipt claim applied to the wrong lifecycle. On failure, the UI discards active permission, SAFE state and verified-removal presentation. A reconnect requires a newer sequence within the same Platform generation or a newer generation; an editor must be reviewed after a restart/revision/state change. STOP, revoked, denied, offline, stale, restarting and unknown generation all block mutating action preview. A \`RecheckWithService\` hint never executes a request and cannot authorize anything.

The TUI renders session state and unknown installed/settings values. Its source remains \`OfflineReader\` until Team A approves the response/transport composition. The WinForms shell names these denial states and keeps all management buttons disabled. The Windows \`-UiProbe\` constructs and inspects real WinForms controls without showing a desktop window or touching services; it cannot substitute for interactive host accessibility or GUI acceptance.

### Team A and Team B handoff, November 8

- Team A PR #241 has a coordination request for the **one** reconciled #232/#234 versioned response contract, typed STOP/revoked/denied/stale/unknown generation responses, correlation, generation, service identity, bounded freshness, settings revisions, and signed lifecycle evidence. Team C will not write a competing response schema, forge \`source=PLATFORM_SESSION\`, or connect the GUI to an unauthenticated socket.
- Team B PR #229 has a coordination request for **separately installable optional** WinForms GUI and native TUI components. Final signed package manifest, artifact SHA/signature chain, install/uninstall lifecycle receipts and Windows/Debian 12 installed-host evidence are Team B owned. Neither GUI nor TUI is an independent installer or updater.
- Pre-integration negative tests check no IPC shortcut/DB/owner credential access, denied/revoked/STOP/restart state, replay, generation change, revision rollback, stale clock and removal-receipt presentation.
- Exact-head tests: \`cargo fmt --all --check\`, \`cargo clippy --locked -p sofia-ui-broker --all-targets -- -D warnings\`, \`cargo test --locked -p sofia-ui-broker\`, native Windows/Ubuntu \`aegis_tui\` executable smoke, Python GUI/policy checks and Windows PowerShell \`-UiProbe\`. These are **component tests** only.
- Release acceptance: #201 rows **31–38 remain NOT ACCEPTED** until verified OS-authenticated management on disposable installed hosts, signed packaging, interactive native Windows UI and Debian 12 terminal evidence are supplied. No merge, production activation, personal Core migration or permission bypass is authorized.


## AG-D028-001 | Mandatory Artifact Library presentation, D028-06

**Source authority:** owner-approved draft PR #248 / issue #250, canonical D028-00–07 release spec and Team E LIB-01–16 QA runbook. This branch owns **D028-06**, providing GUI/TUI and headless CLI presentation targeting **LIB-14 and LIB-16**, and participates in Team A's D028-00 contract review. Existing Team C authentication/packaging/installed-host blockers remain open.

**UI-only initial slice:** canonical WinForms adds seven read-only Library pages (Catalog, Sources, Downloads, Installed, Storage, Hub, History), all disabled lifecycle/acquisition controls and truthful NOT_OBSERVED/UNKNOWN statuses. Native Rust TUI adds matching pages and ASCII `--library-status` with unavailable return code. No local cache, Hub, peer, HTTP, installer or owner authorization is contacted; `OfflineReader` remains the production client. Downloaded != installed != active, received bytes != verified bytes, and offline != missing. The source choice displays Internet fallback DISABLED without silently fetching anything. No synthetic package list, signer, progress, quota, receipt or timestamp is presented as live.

**Contract coordination:** reviewed, versioned service data and authority must come from Team A (#241), signed install/source/cache receipts from the single Team B installer (#244), module/Core lifecycle/dependency semantics from Team D (#240/SDK) and independent Windows/Debian installed-host receipts from Team E (#245). D028-00 freeze and signoff must precede enabling a real management client or mutation. Requests posted to A/B/D/E and tracker #250. No second service protocol or UI-owned authority.

**Targeted CI:** Rust fmt, Clippy, crate and binary tests on Windows/Linux, Python WinForms `-Check` and native `-UiProbe`, additional no-service library parity/policy tests. This validates the shell only, not LIB-14/LIB-16 acceptance. Team E must certify exact installed release with signatures, enrollment and actual service data before PASS; #201 remains 38 rows, GO=NO.
