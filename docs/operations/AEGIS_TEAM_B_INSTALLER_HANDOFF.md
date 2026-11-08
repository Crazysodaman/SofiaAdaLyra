# Aegis Platform 1.0 | Team B AG-D011 installer handoff

**State: UX-1 non-activating launchers, NOT an installed release. GO = NO-GO.**

This isolated Team B change does not merge PRs #209, #212 or #229 and does not alter Team A's IPC, SAFE/STOP, native service contracts, owner credentials, or production state. The existing launcher work is a **presentation and refusal contract**, not the signed native execution backend. No production service registration, Core activation, Fleet enrollment, protected-state creation, key handling, release publication or migration is permitted.

## Commands (normal shell, no elevation)

| Intent | Windows PowerShell 5.1+ | Debian 12 Bash |
| --- | --- | --- |
| Read-only preflight | `./packaging/installers/Install-Aegis.ps1 -Check -NoColor` | `bash packaging/installers/install-aegis.sh --check --plain` |
| Machine-readable check | `./packaging/installers/Install-Aegis.ps1 -Check -Json` | `bash packaging/installers/install-aegis.sh --check --json` |
| Read-only diagnostic preview | `./packaging/installers/Install-Aegis.ps1 -Operation doctor -Json` | `bash packaging/installers/install-aegis.sh --operation doctor --json` |
| Read-only status preview | `./packaging/installers/Install-Aegis.ps1 -Operation status -Json` | `bash packaging/installers/install-aegis.sh --operation status --json` |
| Blocked lifecycle example | `./packaging/installers/Install-Aegis.ps1 -Operation update -DryRun -Json` | `bash packaging/installers/install-aegis.sh --operation update --dry-run --json` |

The launcher produces one JSON object for `-Json` / `--json`, or line-oriented ASCII. `NO_COLOR`, `-NoColor`, `-LineMode`, `--plain`, `--no-color`, and `--line-mode` suppress optional color. Non-TTY interactive execution is refused. The canonical 22-token `contracts/ui/aegis-theme-v1.json` is consumed from either repository or future bundle-root layout; Bash supports truecolor, 256-color, 16-color, and monochrome presentation. PowerShell 5.1 uses its safe 16-color fallback.

**Exit codes:** `0` = read-only preflight completed (not successful installation); `2` = invalid/unsafe invocation; `3` = a consequential operation denied. `SIGNED_RELEASE=NOT_VERIFIED`, `SERVICE_STATE=NOT_OBSERVED`, `INSTALL_AUTHORITY=NOT_CONNECTED`, `executed=false`, and `core_activated=false` are deliberate. Status and doctor remain unverified preview facts, not live service claims. `--yes` is invalid and cannot substitute for owner authorization.

Install, update, repair, rollback, uninstall and purge are **enumerated but disabled**. They return `BLOCKED` even with `--dry-run` because no independently authenticated signed release, current owner grant or production OS executor is attached. No owner secret should ever be supplied to these preview scripts.

## Dependency reconciliation

- **PR #209:** disposable signed-staged Debian 12 two-boot VM evidence. Reuse exact-source digest and provenance verification, but a lab signer is **not** a production release trust root.
- **PR #212:** staged-release/installation state, approval and anti-rollback work remains draft; review, test, and reconcile before connecting to installation.
- **PR #229:** read-only signed candidate plan and checkpoint preview remains draft; an advisory plan cannot grant service or activation authority.
- **Team A:** must publish the authenticated bounded management and current SAFE/STOP/revocation interface. Do not silently design an alternative token, approval or IPC protocol.
- **Signed native install executor:** still missing as a certified OS boundary on Windows and Debian. It must verify independent production trust, target architecture, source SHA, staged content and revocation, and reconcile operations under privileges before making changes.

## Required work before release certification

1. Build a single reviewed native installer executor shipped inside the complete self-contained, independently signed Windows/Debian 12 bundle. Launchers must call the same backend after signature, publisher/root and target checks; no download-and-execute or local toolchain dependency.
2. Wire the approved read-only signed plan from #229 to reviewed installation execution from #212, with durable transaction/recovery receipts, strict state ownership, current SAFE/STOP and nonce-scoped owner authorization from Team A. No activation from a generic yes/flag.
3. Add OS-native service installation and provenance for *owned* SCM/systemd units only; refuse unrelated service adoption and preserve existing identity through update, repair, rollback, uninstall and reinstall. Purge requires separate protected authorization.
4. Test on actual disposable Windows and Debian 12 installed hosts: offline clean machine; authentic/tampered/revoked/wrong-target/stale release; noninteractive refusal; live STOP/revocation; crash/reboot/reconcile; service registration/start/stop/health; single writer; uninstall/reinstall with unchanged protected identity; native theme and accessibility.
5. Produce **exact commit SHA**, independently verified production signature and all asset digests, CI run/job IDs, post-reboot native OS receipts, installation identity fingerprints, provenance, cleanup and unclosed limitation summary. Only then review #201 rows 01, 06–08, 10, 19, 20, 30, 31 and 38 for acceptance.

### Non-acceptance notice

Neither these scripts nor the included unit/CI tests satisfy actual signed installation, service health, update or identity-retention acceptance. No Platform-only or full-project shakedown GO assertion may be derived from this branch. Keep PR draft until the coordinator reconciles other branches and release evidence.

## B-001 reconciliation checkpoint (draft; no installed-host acceptance)

- **#209 reuse:** the signed two-boot Debian 12 release fixture and canonical `PlatformReleaseVerifier` already exist on main. `platform_installer_bundle.verify_offline_installer_bundle` now verifies exact OS target, source SHA, external trust-key fingerprint, signer, revision floor, expected predecessor, signature and all mandatory assets using that same verifier. Verification does not grant owner permission.
- **#212 reuse:** the existing B1 `PlatformInstallationStore`, `verify_staged_release_candidate`, `install_staged_release`, `verify_installed` and `ExecutionApprovalVerifier` remain canonical. No new installation/authority SQLite engine was added. An internal, **non-OS** `publish_owner_approved_code` wrapper requires a one-use exact SAFE proof, rechecks STOP and generation, then delegates signed code publication to B1. It reports OS service not registered and zero Core/Fleet activation. The provisional internal capability must be reconciled with Team A before any management/CLI access.
- **#229 reuse:** `preview_signed_platform_install` is integrated unchanged as the advisory signed install plan; `preview_platform_lifecycle` extends its presentation across future install, update, repair, approved rollback and retention-preserving uninstall without executing them.
- **Native observation:** `platform_installer_native_preflight` reads SCM/systemd service origins, detects foreign/redirected/unknown units and never equates RUNNING with HEALTHY or verified service ownership. This is not native registration.
- **Regression scope:** tests now cover fake signer/tampered signature/tampered asset/wrong source/target/key/revision/parent, no owner proof, one-use code-only SAFE approval, interrupted B1 attempts, identity-reuse plan, Windows SCM and Debian systemd non-adoption. CI workflow has Linux and Windows matrices, exact-head not yet accepted.
- **Still unavailable:** a signed self-contained executable bootstrap trusted *before* its bundled runtime executes; native SCM/systemd **installation, update, repair, rollback, uninstall/reinstall and boot/recovery** orchestration; Team A current enrollment/STOP/revocation/generation IPC handoff; real signed installed-host receipts for Windows and Debian 12; signed GUI/TUI distribution; rollback on interrupted native effects. Existing shell entrypoints still refuse all protected operations. Neither test software keys nor green code-stage tests can be called release certification.
