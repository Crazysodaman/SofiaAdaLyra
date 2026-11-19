# Aegis Guided Installer Acceptance

**Status: SIMULATED ACCEPTANCE HARNESS / NOT A HOST CERTIFICATION / NO-GO.**

This runbook describes the disposable guided-installer acceptance harness and
the operator UX that a future certified bundle must expose. The harness
exercises the existing canonical installer modules against a synthetic offline
bundle on a temporary target. It never installs on the real host, registers a
real Windows SCM service or systemd unit, writes the real user/machine `PATH`,
creates production trust material, or authorises a production release.

Every harness report must state:

- `label: SIMULATED`
- `installed_host_verified: false`
- `production_authorized: false`
- `certified: false`

Real signed disposable-host testing remains required before the installer may
be called certified.

## Harness command

From the repository root, using the reviewed Python 3.12 environment:

```powershell
.\.venv\Scripts\python.exe tools\aegis_guided_installer_acceptance.py --json
```

Read-only preview path (verification plus non-executing install plan):

```powershell
.\.venv\Scripts\python.exe tools\aegis_guided_installer_acceptance.py --check --json
```

On Debian 12:

```bash
python3.12 tools/aegis_guided_installer_acceptance.py --json
python3.12 tools/aegis_guided_installer_acceptance.py --check --json
```

Use `--work-root <new-directory>` to retain the disposable bundles, trust
anchor and installation state for inspection. The report is valid JSON on
stdout; exit `0` means every harness scenario passed, `3` means a scenario
failed or a production blocker was observed, and `2` means the harness itself
refused invalid inputs.

The full harness validates:

- default guided lifecycle is not preview-only;
- `--check` verifies and previews with zero target effects;
- bundle, trust-anchor and runtime discovery needs no operator-entered SHA,
  approval ID or Python path;
- current-release repair succeeds, and install, verify, update, rollback,
  uninstall and reinstall complete through the canonical adapter with
  simulated native/launcher adapters;
- identity and protected local state survive update, uninstall and reinstall;
- global launcher, Windows `PATH` and shortcut plans are idempotent;
- no duplicate service registration, launcher or Platform writer state occurs;
- no native, launcher or installation effect happens before owner approval;
- operator STOP and a revoked owner proof deny before any effect;
- missing/wrong trust, tampered release bytes, missing dependency metadata and
  a missing runtime asset are denied.

Each report records the exact release source SHA, every bundle asset digest,
the equivalent CLI command, per-command outcome, approval attempts and
pass/fail evidence.

## Generated bundle layout

A complete offline bundle is produced by the reviewed release assembler
(`tools/build_aegis_release.py`) and re-verified by the canonical Platform
release verifier. The expected shape is:

```text
aegis-release/
  release/
    release-manifest.json
    release-signature.json
    artifact-digests.json
    build-receipt.json
    assets/
      sofia_sdk-<version>-py3-none-any.whl
      sofia_platform-<version>-py3-none-any.whl
      aegis-platform-service[.exe]
      aegis_tui[.exe]
      python-runtime.zip
      wheelhouse/
      dependency-inventory.json
      sbom.json
      assembly-provenance.json
  installer/
    Install-Aegis.ps1
    Aegis-Setup.exe           # when the Windows launcher was built
    Start-AegisSetup.ps1      # PowerShell fallback
    install-aegis.sh
    trusted-publisher.pem
    trust.json
    install-plan.json
```

`installer/` is deliberately outside `release/`: installer publisher trust
must never be inside signed release media. The bundle is owner-controlled test
media. **Independently verify the publisher key fingerprint and signer ID
out-of-band before running it.** A fingerprint printed inside the same bundle
is not its own trust root. Production requires the installer launcher itself
to be Authenticode/OS-package signed with an owner-approved publisher
certificate.

## Windows: double-click instructions

1. Copy the generated `windows-x86_64` bundle directory to the disposable
   Windows test host.
2. Double-click `installer\Aegis-Setup.exe`.
3. If the executable was not built, run `installer\Install-Aegis.ps1` or
   `installer\Start-AegisSetup.ps1` instead.
4. Approve the single UAC elevation prompt. The guided installer then discovers
   the bundled runtime, release and independent installer trust record; it
   verifies the signed release before any owner approval.
5. Complete the normal attended owner-authentication prompts. The installer
   creates the global `aegis` launcher/PATH entry, GUI/TUI shortcuts, service,
   and then verifies the running service.

No manual SHA, approval ID, Python path or service-registration command is
required. Owner authentication remains mandatory; signatures and SAFE/STOP are
never bypassed. A successful signature verification is not installation
permission.

## Debian 12: one-command instructions

1. Copy the generated `debian12-x86_64` bundle directory to the disposable
   Debian 12 test host.
2. Run:

```bash
sudo bash installer/install-aegis.sh
```

The script discovers the bundled Linux runtime and signed release, verifies the
installer trust record, requests the approved `sudo` elevation when needed, and
then invokes the guided installer. It creates the global `aegis` launcher, the
systemd service and the optional desktop entry, and verifies the running
service.

No manual SHA, approval ID, Python path or `systemctl` command is required.
Owner authentication remains mandatory; signatures and SAFE/STOP are never
bypassed. Use `--check` for a zero-effect preview.

## Trust anchor requirement

The release signature is necessary but not sufficient. The installer must also
receive, from an independent trust root:

- the exact publisher public key;
- its independently pinned SHA-256 fingerprint;
- the reviewed signer key ID;
- the exact source SHA;
- the exact target;
- the minimum accepted revision floor.

A missing key, wrong fingerprint, unexpected signer, wrong source, wrong target,
stale revision, trust key inside the bundle, tampered manifest/signature/asset,
missing dependency metadata or missing runtime asset must deny before any
installation, service, launcher or `PATH` effect.

## Independent trust provisioning

The bundle's `installer/trusted-publisher.pem` and `installer/trust.json` are
provisioning copies for the owner, not the authority used by the guided
installer. Provision an independent owner-controlled copy before running setup:

- Windows default: `%ProgramData%\Aegis\installer-trust\`
- Debian default: `/etc/aegis/installer-trust/`

Each directory must contain exactly `trusted-publisher.pem` and `trust.json`
with the same signer key ID and public key SHA-256 that the owner independently
verified. The guided installer refuses an absent root, a root inside the
bundle, or a bundle/root mismatch. `AEGIS_INSTALLER_TRUST_ROOT` is supported
for disposable test provisioning and must not be treated as proof of owner
trust. No commercial certificate is required for personal-use test signing.

`--no-color` is accepted by the Python guided module and forwarded by both
launchers. The launchers also honor `NO_COLOR` and their native no-color
switches. Invocation tests build real assembler output, replace only the
disposable runtime with an argument echo, and exercise Windows PowerShell and
Bash bundle discovery, `--check`, JSON, normal operation forwarding, missing
trust, and missing runtime failure paths.

## Approval, STOP and revocation

Mutating operations require distinct exact one-use SAFE approvals. The canonical
contracts enforce:

- verification and preview never imply approval;
- no destination, service or launcher effect occurs before approval;
- consumed approvals cannot be replayed;
- operator STOP denies the operation;
- a revoked owner credential denies the operation;
- identity and protected local state are retained through update, uninstall and
  reinstall.

## Windows owner-facing TUI

The bundled Python guided module remains the single security backend. The
Windows setup launcher elevates once and opens the interactive TUI; no Git,
Python installation, Rust toolchain or manual configuration is required of the
owner.

The install wizard now:

- detects the OS, architecture, target and hostname;
- discovers the complete signed release media and the independent installer
  trust root;
- verifies the signed release before prompting for any change;
- detects an existing canonical installation;
- reports free and required disk space;
- prompts for the installation directory, defaulting to `D:\Aegis` when a D:
  drive is present (otherwise the reviewed Program Files location);
- prompts for terminal TUI launcher, Start Menu shortcut, Desktop shortcut and
  optional start-at-sign-in preference;
- displays an exact read-only plan including paths, release/signature identity,
  selected components, service name, approvals, identity/state retention and
  startup preference;
- applies only after explicit plan confirmation through the existing SAFE/STOP
  owner ceremony and the launcher's single UAC elevation.

Existing facilities, state and Core databases are retained. The wizard refuses
an unsupported host, missing/tampered trust, missing bundled runtime,
insufficient disk space or an install directory inside a Git worktree before
any effect. It does not create trust material, install a Core, enroll Fleet,
activate a Core or touch production `sofia.db`.

## Repair-after-update blocker status

The previously documented `repair_after_update` blocker was resolved by
forwarding the trusted installed predecessor manifest digest into media
verification. The disposable acceptance harness now reports
`default_guided_lifecycle: true` and no `repair_after_update` failure. It
continues to label the result `SIMULATED`, `installed_host_verified=false` and
`production_authorized=false`; no production or installed-host certification is
claimed by this source test.

## Still required before certification

- A production publisher signing ceremony and independently provisioned
  production trust root; no test key in this harness may be treated as one.
- Real signed testing on disposable Windows x86-64 and Debian 12 x86-64 hosts,
  including clean offline install, update, repair, rollback, uninstall and
  reinstall.
- Real Windows SCM and Debian systemd registration/start/stop/health receipt
  verification, including reboot and interrupted-transaction recovery.
- Real Windows Start Menu/desktop shortcut, user/machine `PATH` and Debian
  desktop/global launcher behaviour, including removal idempotency.
- Real owner FIDO2 SAFE approval, STOP and revocation ceremonies.
- A production-signed Windows double-click entrypoint and Debian guided
  entrypoint shipped inside the complete offline bundle. An unsigned disposable
  `Aegis-Setup.exe` may be built for review, but it is never production media.
- Exact final commit SHA, all artifact digests, CI/run evidence, post-reboot
  native receipts and an explicit remaining-limitations summary.

Until those gates pass on real signed disposable hosts, the installer is
**not certified**, `installed_host_verified` remains `false`, and
`production_authorized` remains `false`.
