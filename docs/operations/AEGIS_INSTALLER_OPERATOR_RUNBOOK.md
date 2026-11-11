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

### Independent inner B1 review after private staging

The new internal Python verifier
`sofia.platform.ops.platform_installer_verified_stage.review_staged_publisher_signed_capsule`
can validate the original sealed ZIP and detached Ed25519 outer signature
**again**, compare every staged file to the exact signed delivery inventory,
require private 0700 directories and 0600 regular files, and then invoke the
canonical `verify_offline_installer_bundle` on the inner B1 manifest and all
release assets. Both signatures must verify against the SAME independently
pinned publisher key. No new signer or release database is invented.

Provide the original capsule, signature, private staged directory, externally
trusted public-key path/fingerprint and signer ID, exact expected source SHA,
OS target and revision floor. All are reviewed inputs: an untrusted Hub,
download directory or self-signed manifest cannot supply the authority.

Its only successful result is
`OUTER_AND_INNER_SIGNED_BYTES_VERIFIED_ONLY`. It intentionally reports
`publisher_revocation_current_verified=false`,
`owner_approved=false`, `install_executed=false`,
`native_service_registered=false` and `service_health=UNKNOWN`.
Fresh publisher revocation, attended owner authentication, B1 receipt/rollback
policy and installed system service READY remain separate gates. A read-only
review does **not** become an installation approval when saved as JSON.

### Canonical B1 code staging and separately approved publication

**Do not hand `aegis/` extracted ZIP contents directly to
`publish_owner_approved_code`.** A folder containing correctly signed assets
is not the canonical B1 staging candidate. B1 requires its original
`stage-receipt.json` and independently verified runtime inventory.

After successful outer capsule staging and read-only double-signature review,
the **internal** (not shell-exposed) function
`sofia.platform.ops.platform_installer_capsule_b1_stage.stage_sealed_capsule_for_b1`
takes the original capsule/signature, private staged media directory,
out-of-band publisher key and SHA256 pin, signed release source/target/floor,
and a **new, distinct, absent** `b1_staging_candidate` directory.
It reuses `stage_platform_release` to produce the true
`VERIFIED_PLATFORM_CODE_STAGED` receipt and verified, materialized runtime.
Its result is only `SIGNED_B1_CODE_STAGED_NOT_INSTALLED`; it creates no
owner grant, canonical installation, native service or Core.

Next, the separate internal function
`signed_capsule_code_publication_request` must be given BOTH the original
sealed media directory and the **genuine B1 staged candidate**. It rechecks
the outer and inner publisher signatures and requires B1 to verify the
stage receipt. The existing canonical `platform.install_verified_code`
one-use owner-approval fingerprint includes **both** the outer ZIP SHA256
and signed delivery-index SHA256, along with the ordinary B1 manifest,
revision, destination, owner identity and checkpoint. A different ZIP or
inventory cannot reuse the reviewed approval.

Only an independently authenticated SAFE owner proof matching the exact
fingerprint permits `publish_owner_approved_sealed_capsule_code` to call
the existing B1 code publisher. Successful publication means
`PLATFORM_RELEASE_INSTALLED`, **not** running or healthy. The owner must
separately approve the next `native_service_operation_request` under
`platform.native_service.apply` before the reviewed systemd/SCM driver
may register/start a service. Current RUN generation, owner enrollment,
publisher revocation, STOP and installed-host READY must still be checked.

This is an implemented **internal source boundary**, not a complete
public installer. Do not expose these privileged functions directly to
an unauthenticated GUI, TUI, Bash shell or remote Fleet caller.

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

## Focused exact-SHA source shakedown (developer checkout only)

After branch reconciliation, on a clean checkout containing Python 3.12,
pytest, installed project dependencies and stock Debian ZIP/OpenSSL tools,
run the dedicated **source-only** integration gate:

```bash
git rev-parse HEAD
bash tools/aegis_offline_b1_shakedown.sh --source-sha "$(git rev-parse HEAD)"
```

This checks the **actual Bash launcher/stager/verifier**, the Python B1
candidate-stage/one-use SAFE transaction sources, and related native service
simulator tests from the same source SHA. It intentionally refuses a dirty
checkout or mismatched supplied SHA. It performs no production signing or
native service install and does **not** convert disposable test signer results
into 38-row/16-LIB host acceptance. It cannot replace the separately approved
four-host Windows/Debian release shakedown and publisher trust ceremony.

The source test must pass before promoting installer integration work further.
Any failure leaves the installer milestone open; never bypass it with a
synthetic success flag or an unchecked directory.

## Crash, unknown-outcome and removal observation

The source-level native driver now exposes **read-only SCM/systemd
observation** without OS service mutation. Debian checks the exact signed
unit, filesystem origin and PID; Windows opens SCM/service handles with
`SC_MANAGER_CONNECT` and `SERVICE_QUERY_CONFIG | SERVICE_QUERY_STATUS`,
verifies the signed executable/account/start policy and distinguishes
running from stopped. Neither observer is an authenticated Platform RUN/READY
or publisher-revocation proof.

For a journal in `PENDING` or `OUTCOME_UNKNOWN`, the internal
`review_native_outcome_for_reconciliation` function independently rechecks
the canonical signed B1 installed release, observes the native OS service,
and re-reads the same journal and release identity. It reports
`RECONCILIATION_REQUIRED` even if SCM/systemd reports the process
`RUNNING`. The function never consumes a SAFE approval, starts, stops or
deletes a service, rewrites the journal, or clears the recovery fence.

On Windows, successful `DeleteService` is only a **deletion request**.
The service must actually disappear from SCM after closing the opened
handles before the native driver emits a `REMOVED` receipt. A prolonged
`ERROR_SERVICE_MARKED_FOR_DELETE` state produces a bounded timeout and
an unresolved transaction, not a false clean uninstall. On Debian and
Windows, the removal receipt must identify the **exact signed Platform UUID
and release manifest**. Protected state/identity remain retained by default.

This read-only review is **not a journal-repair command**. An authorized
operator must separately review authentic native OS, B1 installation and SAFE
evidence before implementing any future approved reconciliation action.
Never delete a `native-service-transaction.json` file to bypass an
uncertain outcome, and never treat process state as service health.

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
