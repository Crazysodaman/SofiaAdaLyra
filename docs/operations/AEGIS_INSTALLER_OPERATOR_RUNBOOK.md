# Aegis Platform 1.0 | Installer operator runbook (pre-release)

**Status: PREVIEW ONLY / NOT INSTALLED / PLATFORM GO = NO-GO.**
This runbook covers the reviewed UX-1 entrypoints on draft PR #244. A verified signature, artifact staging, unit test or theme preview
is **not** permission to install, register a service or activate Core.
Use a disposable Windows or Debian 12 host for future installation tests.
Do not supply the owner secret to any preview CLI.

## Safe preflight, available today

### Windows PowerShell 5.1

From the repository root, in a normal (non-elevated) terminal:

```powershell
powershell.exe -NoProfile -NonInteractive -File .\packaging\installers\Install-Aegis.ps1 -Check -NoColor
powershell.exe -NoProfile -File .\packaging\installers\Install-Aegis.ps1
```

The first command must print `MODE=PREVIEW_ONLY`,
`SIGNED_RELEASE=NOT_VERIFIED`, `SERVICE_STATE=NOT_OBSERVED`,
`INSTALL_AUTHORITY=NOT_CONNECTED` and `RESULT=NO_CHANGES_MADE`.
The second displays a keyboard-only setup menu. Install, update, repair,
rollback and uninstall selections are **BLOCKED**; the menu never asks for
the owner secret or touches Windows SCM.

The native GUI shell is separately provided by PR #222 while in review:

```powershell
powershell.exe -STA -NoProfile -File .\packaging\ui\Start-AegisControlCenter.ps1 -Check
powershell.exe -STA -NoProfile -File .\packaging\ui\Start-AegisControlCenter.ps1
```

It shows `OFFLINE` until authenticated service IPC is installed; do not
interpret its visible menus as enabled Platform management authority.

### Debian 12 / Bash

```bash
bash ./packaging/installers/install-aegis.sh --check --plain
bash ./packaging/installers/install-aegis.sh
```

The noninteractive preflight reports `SIGNED_RELEASE=NOT_VERIFIED` and
`RESULT=NO_CHANGES_MADE`, without ANSI color escapes. The interactive
mode requires a real terminal. `NO_COLOR=1` forces plain output:

```bash
NO_COLOR=1 bash ./packaging/installers/install-aegis.sh
```

Native cross-platform terminal shell (development toolchain only):

```bash
cargo run --locked -p sofia-ui-broker --bin aegis_tui -- --plain
cargo run --locked -p sofia-ui-broker --bin aegis_tui -- --status
```

The `--status` probe intentionally returns exit code **3** and
`status=UNAVAILABLE source=UNVERIFIED`. It must not report a connected,
healthy or installed service without authenticated IPC.

## Signed offline capsule staging (Debian Bash; inert files only)

The one-script Bash launcher now has an explicit, **non-service** staging mode.
Use an independently trusted copy of the launcher and its companion
`verify-aegis-capsule.sh`, `inspect-aegis-capsule-members.sh`, and
`stage-aegis-capsule.sh`. Do not execute copies from an unverified ZIP.
The public publisher key and its SHA-256 pin MUST be obtained separately from
the capsule, with current publisher trust/revocation reviewed out of band.

Create or select an existing owner-owned **0700 directory** for the new stage
parent, then run (no sudo or owner secret):

```bash
bash ./packaging/installers/install-aegis.sh \
  --stage-capsule /path/to/aegis-offline.zip \
  --capsule-signature /path/to/publisher-capsule.raw64 \
  --publisher-key /separately/trusted/publisher.pem \
  --publisher-sha256 ACTUAL_INDEPENDENTLY_PINNED_SHA256 \
  --publisher-signer ACTUAL_APPROVED_SIGNER_ID \
  --staging-destination /private/0700-parent/new-release-staging
```

The launcher delegates to the existing stock OpenSSL Ed25519 outer publisher
seal verifier and the exact ZIP member index checker **before creating the
staging destination**. It then re-hashes every extracted member, caps each
member to 512 MiB, refuses path redirection and occupied destinations, uses
owner-private directories and regular files, and re-hashes the complete ZIP
before publishing a new staging directory without overwriting anything.

The only successful result is
`SIGNED_MEDIA_STAGED_NOT_INSTALLED`, with
`native_service_registered=false`, `owner_approved=false`, and
`core_activated=false`. This does **not** independently validate the inner
PlatformReleaseManifest schema/signature using the bundled Python verifier,
establish publisher revocation freshness, create a Platform identity, enroll
Fleet, install code into B1, or start/enable any native service. Those steps
still need the separate canonical B1 and attended SAFE/native transaction
chain. The staging script has no automatic installation fallback.

For interrupted staging, inspect the owner-private parent for
`.aegis-stage-*` directories. Do not manually adopt any intermediate bytes
as a verified release. Check the caller's exit code and repeat only after
reconciling the exact capsule and publisher pins.

## Available internal signed verifier and lifecycle planning (not shell-enabled)

The Platform Python package now exposes `verify_offline_installer_bundle` in
`sofia.platform.ops.platform_installer_bundle`: it reuses
`PlatformReleaseVerifier` to verify the detached Ed25519 release signature,
every declared asset, exact source SHA, trusted key fingerprint provisioned
**outside** the bundle, target architecture and revision/predecessor constraints.

`preview_platform_lifecycle` in
`sofia.platform.ops.platform_installer_lifecycle` uses the existing B1
`PlatformInstallationStore` to preview install, update, repair, rollback and
retention-preserving uninstall. A preview is non-executable and refuses an
unreconciled attempt or missing active installation. These APIs require an
already authenticated and independently trusted runtime. They are **not**
invoked from the two untrusted shell launchers, and do not provide an installer.

## Planned installed-host procedure, NOT YET ENABLED

The installed release executor must consume an exact, verified Platform-only
bundle signed by an approved production signer. The owner must review the
target OS/architecture, manifest hash, revision floor, destination, service
identity, protected-state policy and required approvals before enabling
consequential operations.

1. Verify the **original** signed release and all installed asset hashes.
   Do not use an arbitrary local Git checkout as the production trust root.
2. Review the B1 plan from
   `sofia.platform.ops.platform_installer_preview.preview_signed_platform_install`.
   It is non-executable, does not alter service state and grants no authority.
3. Execute signed installation only through the future reviewed native
   Windows SCM/Debian systemd executor. Recheck signature, current approved
   principal, STOP, revocation and anti-rollback at the last execution boundary.
4. Verify service identity, single-writer ownership, Core-free startup,
   durable receipts, reboot, clean stop and forced-crash recovery.
5. Update, repair, rollback and uninstall must remain independent protected
   operations. Uninstall **preserves canonical protected state by default**;
   any destructive purge requires a distinct owner authorization.

**Do not treat the preview commands above as these five steps.** They only
verify the user-facing entrypoint.

## Release evidence required by #201

| Row | Evidence still required |
| --- | --- |
| 01 | Actual signed PowerShell/Bash installer with OS service registration on two disposable host types |
| 06–08 | Real Windows SCM/Debian systemd start, stop and crash/reboot recovery |
| 10, 31 | Local OS peer authentication, fresh enrollment/revocation and SAFE-bound management IPC/CLI |
| 19 | Exact signed update, repair and rollback with interrupted-host recovery receipts |
| 20 | Uninstall/reinstall identity preservation and no second writer |
| 30 | This runbook updated with **tested** install/repair/uninstall commands and error recovery |
| 32–38 | Working native GUI/TUI management, shared theme, live status/approval flow and accessibility |

Acceptance remains `NOT TESTED` or `FAIL` until complete signed installed-host
receipts pass. Source tests alone never mark a release row PASS.

## Safe diagnostics

A service is not assumed to be installed during preview. For explicitly
disposable Debian host testing, use read-only `systemctl status
aegis-platform.service` and `journalctl -u aegis-platform.service
--no-pager -n 40`, but do not publish raw owner/private runtime logs.
The VM harness produces sanitized two-boot receipts through the
`Aegis Debian12 Offline VM Service Contract` CI workflow.

If a preflight says `UNAVAILABLE` or a signed/authorization check fails,
**do not retry with elevated privileges or disabled checks**. Preserve the
failure evidence and return to the Platform installer and SAFE owner.
