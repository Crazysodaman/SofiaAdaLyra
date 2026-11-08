# AG-D022 | Terminal Control Center

**Status:** OWNER-DESIRED, DETAILED DESIGN CAPTURED (2026-11-08).
**Target release:** Platform 1.0 expanded shakedown (owner directive 2026-11-08).

This document captures design intent for the Terminal Control Center (TUI).
It is created by the owner directive that scheduled GUI/TUI management
functionality into the expanded Platform 1.0 shakedown. It defines observable
behavior; the [batches document](../development/AEGIS_UI_SHAKEDOWN_BATCHES_2026-11-08.md)
sequences implementation and evidence.

## Scope

The TUI is a full-screen terminal client of the [authenticated management API]().
It serves Windows (Windows Terminal, conhost) and Debian 12 (any POSIX terminal)
and must remain usable over SSH with no graphical stack installed. Essential
management functionality inside the minimum shakedown:

* Live service/Core/module/Fleet status with automatic refresh, reconnect and
  stale-state labeling (`STALE`, `UNKNOWN`, `DISCONNECTED` reuse existing
  observation vocabulary). No cached observation is presented as current.
* Platform settings, Core Manager, Module Manager, Security/Approvals,
  Updates/Recovery and Diagnostics navigation.
* Protected actions follow the [three action classes](): read-only observation,
  configuration-proposal and protected effect. The TUI never mints authority;
  approval recording always happens through the existing SAFE owner ceremony
  (256-bit-secret-backed interactive methods; never arguments, logs, URLs,
  prompts or Core-generated attestations).

## Hard contracts (inherited verbatim from AG-D007 design)

* Platform's authenticated Rust service owns identity, SAFE/STOP, approvals,
  installed-component effects, remote trust and receipts. The TUI cannot
  bypass or become that authority.
* A versioned SDK and CLI expose the same semantics as GUI/TUI actions. No
  UI-only privileged operation exists.
* Platform startup never depends on SofA-a, an LLM, GPU, Tauri or a desktop
  session; headless hosts retain CLI/API parity with no graphical dependency.
* Closing the TUI never stops the Platform. Every protected operation is
  rechecked by the service, independent of stale UI state.
* Requested is not completed. Unknown-outcome effects are never silently
  retried; the operator resolves the explicit OUTCOME_UNKNOWN receipt first.
* Confirmation dialogs show immutable IDs, exact signed operation, affected
  host/Core, permission and consequences; never a friendly name alone.

## Implementation direction

* Rendering lives in a native Rust-based TUI component, evaluated and selected
  in batch U1 (framework review: Rust-native crates first; Python-native TUI
  stack only for the fallback oracle). Choice and rationale are recorded in
  the batches document before implementation merges.
* Read-only projections for the first pass reuse the existing
  `sofia.platform.modules.control_center` text projection contracts; nothing
  here authorizes a new managers/registries duplication.
* Live status uses the service-owned authenticated snapshot/event stream with
  bounded polling and resync fallback (AG-D006 live status requirement);
  neither a second module registry nor a second writer is permitted.

## Acceptance mapping

Shakedown rows 32 (Windows TUI), 33 (Debian 12 TUI), 35-37 (manager parity)
use the receipt discipline in
[PLATFORM_1_0_ACCEPTANCE.md](../development/PLATFORM_1_0_ACCEPTANCE.md):
exact source SHA, test IDs, CI run, artifact digests and actual Windows/Debian
host observations before PASS.
