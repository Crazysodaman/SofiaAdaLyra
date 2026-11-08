# AG-D011 | One-script ASCII Aegis Platform installer

**Decision:** OWNER-APPROVED and REQUIRED FOR PLATFORM 1.0 GO (2026-11-08 owner directive); CLI-first Windows and Debian setup experience originally chosen 2026-11-07.
**Implementation:** RELEASE-BLOCKING SPECIFICATION, NOT IMPLEMENTED/CERTIFIED. Neither shell entrypoint below is currently a certified or published installer.
**Scope:** AG-D011 is now an explicit Platform 1.0 GO blocker through existing #201 acceptance rows 01, 19, 20, 30 and 38 (also 06–08 and 10 for service/recovery/management). No second installation authority and no new acceptance row.
**Dependency:** Implement using Platform 1.0 #201 work (signed release verifier/stager, identity, real Rust-owned native service, OS registration, SAFE/STOP, authenticated management CLI/IPC and recovery). It is approved release implementation scope but does not authorize deployment, personal Core activation or real-host cutover.

## 1. Owner-facing contract

An owner downloads one **reviewed, signed** release bundle or offline installer, runs **one script**, and answers ASCII CLI prompts. No Git clone, Rust, Cargo, Python, manually installed dependencies, compiled wheels, Core package, model, GPU or desktop login is required.

Proposed entrypoints included in signed release bundles:

- Windows 10/11 and supported Windows Server: `./Install-Aegis.ps1` (PowerShell; exact OS support must be established by release acceptance).
- Debian 12: `bash ./install-aegis.sh` (Bash and systemd).
- After a verified installation: `aegis platform status`, `aegis platform doctor`, `aegis platform update`, `aegis platform repair`, `aegis platform uninstall` (PROPOSED COMMANDS, not existing certified CLI).

Install should leave an **operational, Core-free Aegis Platform** with its own immutable installation identity and a native managed service. Core, model, modules, desktop GUI and Fleet enrollment are independently optional; ordinary installation does not silently do any of them.

### First menu (ASCII only; all values below illustrative, not real host observations)

```text
+------------------------------------------------------------+
|                       AEGIS PLATFORM                       |
|                   Installation Wizard                      |
+------------------------------------------------------------+
| Host:  <observed-hostname>                                  |
| OS:    <observed-windows-or-debian-version>                 |
| CPU:   <observed-architecture>                             |
| Mode:  INTERACTIVE                                        |
+------------------------------------------------------------+
| [1] Install Aegis Platform (Core-free)                     |
| [2] Update installed Platform                             |
| [3] Repair an existing installation                       |
| [4] Uninstall Platform                                    |
| [5] Diagnostics and environment checks                    |
| [0] Exit                                                  |
+------------------------------------------------------------+
Select [1]: _
```

Install walkthrough:

```text
STEP 1/7  System check        [PASS / BLOCKED / UNKNOWN]
STEP 2/7  Trusted release     [signer, SHA-256, OS/ABI, version]
STEP 3/7  Install settings    [paths, service account, role]
STEP 4/7  Identity policy     [new or exact approved recovery]
STEP 5/7  Review             [file/service/state diff, downtime]
STEP 6/7  Authorize           [protected local owner ceremony]
STEP 7/7  Install and verify  [actual executor receipts]
```

Final screen must show distinct facts: artifact VERIFIED, service RUNNING/STOPPED/UNKNOWN, service HEALTHY/DEGRADED/UNKNOWN, Platform identity serial/fingerprint, Core NOT INSTALLED when absent, Fleet NOT ENROLLED when not enrolled, exact release revision/digest, service origin, and log/diagnostics location. Never equate process RUNNING with full health, trust, Core cognition or model inference.

## Canonical CLI/TUI installer color scheme (mandatory for Platform 1.0)

All interactive installer TUI menus, ASCII fallback prompts, preflight displays, action review and status/diagnostic output **must** use the owner-defined [shared Aegis GUI/TUI color theme](AEGIS_SHARED_GUI_TUI_THEME.md) by default; [terminal-specific color and monochrome rules](AEGIS_CLI_TUI_COLOR_THEME.md) apply where the terminal supports it: purple `#9400D3` branding, cyan `#00C2FF` accent, lime `#39FF14` success, black `#000000` background, `#0B1020` panels, light text `#E5E7EB`, amber `#FFB000` warnings and red `#9F0202` danger accents, plus the complete HUD/hover/focus palette specified there. Monochrome ASCII remains a first-class fallback for SSH, serial terminals, `NO_COLOR`, narrow displays and redirected output. Never rely on color alone to identify protected operations or imply an install succeeded. Implement the shared theme only through presentation, without overriding service/owner authority.

## 2. Cross-platform bootstrap architecture

Use two minimal OS-native, auditable launchers, with **the same prompts and the same backend installation API**:

1. `Install-Aegis.ps1`: signed PowerShell bootstrap for Windows. Use PowerShell supplied by the OS where supported; no recommendation to disable execution policy, AV, certificate validation or script signatures. Elevate only after verification and the reviewed privilege boundary, for the exact OS service operations requiring administrator rights.
2. `install-aegis.sh`: portable Bash bootstrap for Debian 12. Run preflight as the interactive owner; obtain narrowly scoped `sudo` for OS package/service operations after release checks. No blind `curl | bash`, no untrusted `sudo` download/execute, and no universal assumption that the shell process is root.
3. Both invoke an included signed/native installer executable or an approved native package operation from the release bundle, which calls the existing Platform release verification and governance owners. The launchers **must not reimplement** signature, trusted-root, authorization, identity, state, transaction or service semantics independently.
4. Provide a reviewed offline package mode from local removable media, with verified exact digest/signature and full dependency/runtime closure. An optional online acquisition mode may retrieve an exact trusted release, but download transport and a signature from the same untrusted origin are not sufficient as the root of trust: approved publisher/trust key must be provisioned or verified independently.
5. Production releases bundle all required components, including neutral Python runtime where applicable, compatible SDK/Platform wheels and Rust native binary. Never demand local developer build tools or infer correctness from a wheel import.

Do not confuse the existing `packaging/services/aegis-platform.service`, Rust `aegis-platform-service` binary, `component_artifacts.py` wheel builder, or disposable VM staging receipts with a completed installer. They are existing foundations to reuse, not proof that these scripts are available or safe to run in production.

## 3. Default choices and questions

- Default menu selection: Install only when no existing Platform installation is detected; otherwise Status/Repair/Update first. Never silently overwrite or create a second Platform identity.
- Default deployment: **Local Core-free Platform**. Never install personal Sofía, Ollama or a model without a later explicit separate request and applicable approvals.
- Mode: `[1] Standard (recommended)`, `[2] Advanced`, `[0] Back`. Standard uses reviewed per-OS install locations, restricted service identity, owner-private state and native service start-at-boot; show exact paths, ownership and resource changes before applying. Advanced accepts only normalized, guarded paths within authorized boundaries.
- Platforms may operate unpaired. After installation, present **optional separately governed Fleet enrollment** with a fresh approval, independent of download/installation consent. Decline is an ordinary successful local installation.
- Service running at boot is a separate explicit choice shown in the preview. Do not force reboot or enable automatic update without a separate decision.
- Status, diagnostics and `--dry-run` should work without changing local state or requiring administrator privileges where inspection permits.
- `[B] Back`, `[C] Cancel`, `[?] Help` on every prompt. Ctrl-C must exit with a truthful interruption/unknown-outcome message and never bypass reconciliation.
- Sensitive operations default to **No**. Non-interactive mode is safe for CI/disposable acceptance but must require explicit trusted inputs and cannot turn `--yes` into owner approval.

## 4. Authority and safety

- Release signature, pinned hash, exact OS/CPU/ABI and version, permitted publisher, current revocation, monotonic revision floor and predecessor checks must be enforced by the existing Platform authorities before any install operation.
- Show non-secret review details: executable/package digests, source SHA, signer ID, target host identity, install paths, service name, reserved disk capacity, network needs, requested grants, reversible vs irreversible steps and fallback plan.
- A user answering `Y` to a generic prompt **never** creates owner cryptographic authorization. Reuse canonical SAFE/STOP, scoped one-time owner proof, current revocation, anti-replay, identity and generation checks. If owner enrollment has not yet happened, follow the separate reviewed setup/enrollment ceremony. The agreed 256-bit owner secret is never put in CLI arguments, environment variables, shell history, logs, crash reports, UI exports or Core prompts. Use protected no-echo interactive input and the canonical verifier; FIDO2 remains optional/disabled unless separately enabled.
- No secret, key, public-key authenticity assertion or approval may be derived from the optional Sofía Core, downloaded model, an LLM response, a generic confirmation click, or the host's self-declared name.
- No automatic service adoption: existing unrelated `AegisPlatform`, `SofiaAdaLyra`, or watchdog installations must be detected and handled via a clear refuse/approved migration path. Never kill or reconfigure personal Sofía production services as an installer side effect.
- Never import or modify an existing `sofia.db`, Constitution, memory, private Core identity, owner secret, personal profile or Fleet trust database as a side effect of generic Platform installation.
- File paths must be owner-private, non-redirected and reverified under the actual service/installer identity. Prevent symlink/junction traversal, broad ACLs, staged-file swaps and installer TOCTOU.
- If a step fails after effects may have occurred, record an accurate `FAILED` / `OUTCOME_UNKNOWN` receipt; reconcile exact state before offering `Resume` or `Rollback`. No blind retry, hidden cleanup or fictional success percentage.

## 5. Install / update / repair / uninstall semantics

| Operation | Expected meaning |
| --- | --- |
| Install | Verify and stage exact signed Platform release, secure local state and immutable installation identity, register native service, explicitly activate after required owner approval, prove observable service health. |
| Update | Stage a separate verified candidate, preview downtime/data compatibility, request exact approval, drain only affected workers, switch selected release durably, health-check and govern rollback. Preserve installation identity. |
| Repair | Diagnostic-first; show exact proposed repaired files/permissions/service state. No generic reset, rekey, re-enrollment, silent ownership change or destructive identity recreation. |
| Uninstall | Stop/remove the Platform service and code with governed receipts. Default to retaining protected local identity/state; display subsequent dependency impact. Personal Core data and credentials are **never silently purged**. |
| Purge | Separate explicit advanced destructive ceremony with independent owner authorization, verified backup/recovery constraints and precise preview. Not a default menu shortcut. |
| Diagnostics | Read-only facts with bounded scrubbed logs, missing prereqs, service state, installation revision and genuine recovery suggestions. |

## 6. Mandatory Platform 1.0 installed-host test matrix and release gate

- Fresh Windows nonadmin-to-admin consent, fresh Debian12 local/SSH user-to-sudo, and offline installation on disposable hosts; no Python/Cargo/GPU/Core preinstalled.
- Correct signature versus modified package; untrusted/revoked signer; wrong OS/architecture, stale release, downgrade, missing dependency, incomplete bundle and redirected extraction directory.
- Explicit lack of Core, model, network or desktop still permits supported Core-free install. No `sofia.db` or personal assets created.
- Existing Platform identity reuse; conflicting/wrong identity; existing unrelated service; interrupted stage, interrupted registration, power loss, restart, retry, repair and rollback with no duplicated service or writer.
- Lost/deleted/expired owner approval, STOP between review and execution, wrong host, replay, guest/remote identity spoof, unsafe CLI flags and redacted secret handling.
- Interactive themed TUI on Windows and Debian, exact canonical 22-token manifest reuse, truecolor/256/16-color fallback, screen-reader-friendly plain ASCII numbered-menu fallback for `NO_COLOR`, narrow/SSH/serial terminals, no ANSI in pipe/JSON/log, Windows/Linux line endings, keyboard-only prompts, cancelled/back navigation, and non-TTY refusal unless an approved explicitly scoped noninteractive mode is used.
- Report exact Git SHA, signed release digest, binary/package version, tests, OS-native installed-host lifecycle/health and cleanup evidence; only mark #201 acceptance rows PASS when their full existing criteria are met.

## 7. Milestones and non-goals

- **UX-0 (this document):** Owner has selected the one-script CLI-first installer with themed optional TUI and plain ASCII fallback as a **mandatory Platform 1.0 GO feature**. This design documents behavior; implementation and installed-host evidence are still outstanding.
- **UX-1:** Build read-only preflight + deterministic plan output and ASCII presentation using agreed service interface, with Windows/Debian tests. Cannot stage or activate real hosts.
- **UX-2:** Wire the launchers to the #201 governed signed installer and authenticated management API once those foundations have passed their own tests; add disposable installed-host acceptance.
- **UX-3:** Signed installer release packages, operator docs and approved production process; never inferred from a passing CLI demo.

**Owner-approved GO scope (2026-11-08):** AG-D011's interactive theme and fallback are now explicitly mandatory under #201 without adding a 39th row. The real signed installer and headless CLI share the same governed backend and authority as the optional TUI and future GUI. None of these interfaces is Sofía Workbench or an alternative identity authority.
