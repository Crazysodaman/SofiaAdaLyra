# AG-D022 | Aegis Terminal Control Center (headless ASCII TUI)

**Status:** OWNER-DESIRED DESIGN (2026-11-07); CAPTURED, NOT IMPLEMENTED or SCHEDULED.
**Purpose:** A complete, optional-screen Aegis management experience for headless Windows and Linux computers, local consoles and SSH sessions.
**Primary entrypoint (PROPOSED, NOT A CERTIFIED COMMAND):** `aegis` when attached to an interactive terminal; explicit `aegis tui`, `aegis status`, `aegis settings` and `aegis --help`.
**Related designs:** AG-D007 Control Center GUI, AG-D011 one-script ASCII Platform installer, AG-D003 Core CLI, AG-D012 Fleet Manager, AG-D013 Security Center, AG-D020 Jobs, AG-D023 governed Core self-configuration.
**Release fence:** Does not change the Platform-only acceptance tracker #201 or authorize agent execution, shipping a GUI, production Fleet enrollment, real Core activation, owner credential changes, or G8.

## 1. Owner decision and product promise

Provide an **ASCII/terminal control center** so Aegis remains directly usable on machines with no desktop, GPU, Ollama, local browser or personal Sofía Core. Install GUI and TUI as independently optional interfaces; all local/remote actions use the **same authenticated Platform service API, effective permission policy and action receipt system**. A TUI is not a replacement service, database, scheduler or independent security authority.

The owner should be able to SSH into a Debian machine, open `aegis` and navigate with a keyboard. On Windows PowerShell / Windows Terminal / a real terminal session, the experience should be equivalent. A terminal without full-screen support gets an ASCII numbered-menu fallback; a non-TTY script uses explicit subcommands/JSON without interactive prompts.

## 2. Proposed main screen

```text
+--------------------------------------------------------------------+
| AEGIS PLATFORM         TERMINAL CONTROL CENTER            v<...>  |
+--------------------------------------------------------------------+
| Host: <verified platform ID / callsign>     Connection: LOCAL     |
| Service: RUNNING / STOPPED / UNKNOWN       Health: <receipt>      |
| Core: NONE / PRESENT / UNKNOWN             Fleet: <trust state>   |
+--------------------------------------------------------------------+
| [1] Overview             [7] Security and Permissions            |
| [2] Platform Settings    [8] Jobs and Approvals                   |
| [3] Core Manager         [9] Backups and Recovery                 |
| [4] Models and Compute   [A] Updates and Rollback                 |
| [5] Module Manager       [B] Diagnostics and Logs                 |
| [6] Fleet Manager        [C] Developer / Aegis Lab (optional)     |
|                                                                    |
| [/] Search   [?] Help    [R] Refresh    [Q] Exit                  |
+--------------------------------------------------------------------+
| Select: _                                                          |
+--------------------------------------------------------------------+
```

This is an illustrative design, not an actual host observation. Never invent identity, model availability, service health, ratings, Fleet freshness or operation completion from cached/local display strings.

### Platform Settings page

```text
+--------------------------------------------------------------------+
| AEGIS > PLATFORM SETTINGS          Host: <verified ID>            |
+--------------------------------------------------------------------+
| [1] Service lifecycle          [5] Resource limits               |
| [2] Local installation info    [6] Network / remote access      |
| [3] Storage and retention      [7] Updates / restart policy     |
| [4] Module configuration       [8] Diagnostics preferences      |
+--------------------------------------------------------------------+
| Selected: <field>                                                   |
| Current value: <authoritative source>  Revision: <n>               |
| Apply: LIVE / NEXT_OPERATION / COMPONENT_RESTART / PLATFORM_RESTART|
| Permission: READ_ONLY / PROPOSE / APPROVAL / DELEGATED              |
| [E] Edit   [P] Preview diff   [H] History   [B] Back               |
+--------------------------------------------------------------------+
```

### Core Manager / Core Settings / Autonomy page

- List installed Cores by stable authenticated identity, separate from a nickname, including source digest, host, current generation, writer authority and operational health.
- View Core-owned settings read from the canonical Core Host (not local guesswork), value source, revision, effective revision, apply boundary, last actor and current allowed edit scope.
- Under **Core Settings > Self-Management** show per-Core autonomy policy from AG-D023: current grant, allowed field set, min/max or allowed values, expiry, rate/resource limits, change history, undo/revert and Pause Self-Changes control.
- A Core not installed or unavailable is **NONE / UNAVAILABLE**; the Platform TUI must remain fully usable.
- Install/activate/deactivate/uninstall remain governed operations from AG-D003 with exact receipts. No TUI direct Core DB writes.

### Fleet page

- Show **local identity**, trusted enrolled peers, merely discovered candidates and stale/unreachable peers as distinct categories.
- Display signed host IDs, callsign, verified scope, last observed time, connection/freshness and accepted authorization. Never grant permission through host discovery or a name.
- Select a verified target and preview operations. Remote management is unavailable until authenticated transport and host-scoped permission exist; never invoke a remote shell merely to simulate it.

### Jobs / Security / Diagnostcs pages

- Read-only operational receipts and current owner approval inbox.
- Security page shows active/expired/revoked scope with redacted secret metadata and SAFE/STOP truth. Emergency operator STOP reachable from every page but only by an authenticated, authorized principal.
- Jobs show REQUESTED, AWAITING_APPROVAL, RUNNING, SUCCEEDED_VERIFIED, FAILED, DENIED, CANCELLED and OUTCOME_UNKNOWN from actual executor receipt; no fabricated percent completion.
- Diagnostics show version, exact service ID, process observations, safe log excerpts, missing prerequisites, verified release digest and whether the data is live or stale. Never confuse running process with working Core or model.

## 3. Keyboard and accessibility

- Controls: arrows and Tab/Shift+Tab where supported, Enter selects, Esc/Backspace goes back, `/` searches, `?` help, `R` refresh, `Q` quits after warning about still-active approved jobs.
- Every action has a **numeric ASCII alternative**. Avoid color-only meanings, mouse dependence, Unicode-only borders or mandatory ANSI escape support.
- Fall back from modern full-screen TUI to a numbered line-mode menu on plain SSH, serial console, 40-column terminals, missing TERM, screen readers or Windows PowerShell limitations.
- High-contrast and monochrome display are standard; optional colors are presentation-only. Display timestamps with timezone and freshness.
- Secret input is not displayed, copied, saved in terminal scrollback, exported, or passed via environment/argv. Shell history must not record secrets. Refuse insecure/non-interactive sensitive input.
- TUI is an interactive terminal, not a browser login, remote console service or general remote execution tool.

## 4. Proposed command surfaces (not yet implemented)

```text
aegis                          # interactive TUI when a TTY; help otherwise
aegis tui                      # explicit ASCII dashboard
aegis status                   # safe local summary
aegis platform status
aegis platform doctor
aegis settings list            # show contract-backed fields and read scope
aegis settings show <field>
aegis settings history
aegis core list
aegis core settings <core-id>   # canonical host read
aegis core autonomy <core-id>   # AG-D023 policy view
aegis jobs list
aegis jobs show <job-id>
aegis fleet hosts
aegis permissions list
aegis help
```

Any mutation command should produce **preview diff, required current authority, exact host/Core identity, apply classification, revision and potential interruption**, then use the canonical service's reviewed approval / dispatch. `--yes` is not owner authentication. Scripts may use explicit non-interactive read-only JSON output, but noninteractive protected changes require already-established independent cryptographic authorization.

Do not create separate routes that issue SQL directly, rewrite config files, spawn arbitrary service management commands or bypass the verified OS operator. The Platform service remains authoritative even if TUI exits, TUI is upgraded, a display client disconnects or the personal Core is absent.

## 5. Reuse the current implementation

- `src/sofia/platform/config/settings_authority.py`: canonical revisioned values, field owner classes, CAS, durable idempotency/events and separate effective apply state.
- `src/sofia/platform/core_link/conversation.py`: authenticated Core Link `settings.snapshot`, `settings.update`, `settings.events` with scope checks.
- `src/sofia/modules/ui/core_link_settings.py`: an existing Tk client that consumes those contracts; reuse typed behaviors but do not import Tk into the headless TUI.
- `src/sofia/platform/modules/settings.py`: signed module contracts, lifecycle-bound settings updates.
- `src/sofia/platform/safe/approval_inbox_cli.py`, `permissions_cli.py`, `owner_secret_cli.py`, `src/sofia/platform/ops/backup_cli.py`, `callsign_cli.py`: existing narrow terminal interfaces, not a complete neutral TUI.
- `rust/crates/sofia-platform-lifecycle/`: Core-free service owner; `rust/crates/sofia-ui-broker/` is **not** the service's authenticated management interface.
- The full Core-free Platform service's authenticated owner management IPC/CLI is still tracked separately in #201. Build the TUI as a client after the backend contract is accepted; do not invent a second security/control API.

Technical candidate: a native Rust executable and an optional well-maintained terminal UI library such as Ratatui, with a minimal plain-ASCII fallback. Framework selection, static/dynamic linking and packaging are future implementation decisions; the UI must not require a display server or an extra language interpreter installed by the user. Windows/Linux commands should share semantics even if launcher packages differ.

## 6. Settings and change provenance

Every settings row must carry where applicable:
- Identity scope: Platform-local / signed module / selected Core / client presentation.
- Current actor and authority source (owner, Core grant, Platform policy, module contract), with privacy redaction.
- Saved revision, effective revision, LIVE/NEXT_OPERATION/COMPONENT_RESTART/PLATFORM_RESTART boundary.
- Current source-observed value, proposed value, numeric constraints, allowed enumerations, pending apply, error and actual receipt.
- Policy-effective grant and STOP status rechecked at execution, with redacted event history.

**Important:** The existing `SettingsOwner.CORE` field marker means the setting is Core-owned; it is not permission for a Core to self-authorize changes. AG-D023 defines that separately.

## 7. Owner safety / approval design

- Read-only views available to authorized local operator; remote views require host/client enrollment and freshness, with scoped identity and revocation on both request and response.
- Sensitive mutations use one narrowly scoped signed owner authorization, not an arbitrary terminal confirmation or a Core-supplied token.
- Current 256-bit owner-secret ceremony is tied to attended signed-in Venus Windows behavior in existing implementation. **Do not assume entering that secret on headless Debian/SSH is presently a valid owner proof.** Define and separately approve secure owner-side issuance/remote approval or an independently reviewed interactive terminal ceremony before enabling headless privileged writes. No weakened auth just for convenience.
- Never store an owner secret, root of trust, signing key, Core memory or unattended privileged login in TUI state, prompt history, logs or exports.
- Existing SAFE/STOP, revocation, duplicate-writer fencing and protected config precedence remain unchanged.
- A TUI user closing the interface must not shut down Platform/other approved jobs unless separately authorized.

## 8. Acceptance milestones (DESIGN, not implementation tickets)

1. **TUI-0:** Confirm navigation, per-Core autonomy page and read-only source contracts.
2. **TUI-1:** Read-only terminal dashboard runs from an actual separately installed, Core-free Windows and Debian Platform. Supported console + SSH fallback, no Tk/GPU/Ollama.
3. **TUI-2:** Exact field read/edit with revision conflicts, apply-state receipts, redaction, remote stale/STOP/revocation handling and shared GUI/CLI semantics; every write uses #201 authenticated management IPC.
4. **TUI-3:** Managed Core, Fleet, module and approved job views; local/remote controls only when their own host/service acceptance has passed.
5. **TUI-4:** Signed and reproducible installer integration with AG-D011, executable tests on disposable Windows/Linux, upgrade and rollback, non-privileged operation, crash/TTY exit and host reboot acceptance.

Never claim that existing CLI scripts, Settings GUI or Rust broker policy constitute a working full TUI. Do not merge these user-experience milestones into #201 as new release blockers without a separate owner decision.
