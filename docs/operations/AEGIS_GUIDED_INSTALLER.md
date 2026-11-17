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
  release-manifest.json
  release-signature.json
  assets/
    sofia_sdk-<version>-py3-none-any.whl
    sofia_platform-<version>-py3-none-any.whl
    aegis-platform-service[.exe]
    python-runtime.zip
    dependency-index.json | dependency-inventory.json
    observed-sbom.json | sbom.json
    assembly-provenance.json
  runtime/
    python/
      bin/python3.12        # Debian 12
      python.exe            # Windows x86-64
  stage-receipt.json        # staged candidate evidence, not an approval
```

The publisher trust anchor is deliberately **not** part of the bundle:

```text
<independent trust root>/
  publisher.pem
  trust-anchor.json
```

`trust-anchor.json` is the acceptance fixture convention. A production trust
anchor must be provisioned out of band and must bind at least the reviewed
publisher key fingerprint, signer ID, exact source SHA, target and minimum
revision floor. A public key placed inside the bundle, or a SHA printed by the
bundle, is never its own trust root.

## Windows: double-click instructions

1. Place the generated bundle at `C:\AegisBundle`.
2. Provision the independent trust anchor at
   `C:\ProgramData\Aegis\trust` (or `%LOCALAPPDATA%\Aegis\trust` for a
   non-elevated installation).
3. Double-click `C:\AegisBundle\Install-Aegis.cmd`.

The double-click wrapper must be a generated, signed bundle entrypoint. It must:

- discover `publisher.pem`, `trust-anchor.json`, the release root and the
  bundled `runtime\python\python.exe` without prompting for a SHA, approval ID
  or Python path;
- call the existing `packaging\installers\Install-Aegis.ps1 -Wired` adapter;
- display whether the release verified before requesting any owner approval;
- use the existing attended SAFE owner ceremony for the separate code and
  native-service approvals;
- show `DENIED`, `STOP`, revocation or bundle-integrity errors without making
  any service, launcher or `PATH` change.

The current source tree does not ship or certify that wrapper. The harness
validates the same lifecycle behind the canonical adapter; it does not turn the
preview-only PowerShell entrypoint into a certified installer.

If a wrapper is unavailable, the existing explicit source path remains:

```powershell
powershell.exe -NoProfile -NonInteractive -File .\packaging\installers\Install-Aegis.ps1 `
  -Wired -Operation verify -ReleaseRoot C:\AegisBundle `
  -PublisherKey C:\ProgramData\Aegis\trust\publisher.pem `
  -PublisherKeySha256 <INDEPENDENT_PIN> -PublisherSigner <APPROVED_SIGNER> `
  -ExpectedSourceSha <EXACT_SOURCE_SHA> -Target windows-x86_64 `
  -MinimumRevision 1 -Json -NoColor
```

Do not treat a successful verify as installation permission. Each mutating
operation still requires its own exact one-use SAFE approval.

## Debian 12: one-command instructions

1. Extract the generated bundle to `/opt/aegis-bundle`.
2. Provision the independent trust anchor at `/etc/aegis/trust`.
3. Run the generated guided entrypoint as the intended service owner:

```bash
bash /opt/aegis-bundle/install-aegis.sh \
  --bundle-root /opt/aegis-bundle \
  --trust-root /etc/aegis/trust \
  --guided
```

The guided entrypoint must discover the bundle runtime at
`runtime/python/bin/python3.12`, verify the full signed release, then request
the separate code-publication and native-service owner approvals. It must not
elevate by itself, change a service before approval, accept a caller-supplied
self-signed key, or use a zipped archive or printed SHA as trust.

The current source script exposes the explicit wired operation path instead of
the guided wrapper above:

```bash
bash ./packaging/installers/install-aegis.sh --wired --operation verify \
  --release-root /opt/aegis-bundle \
  --publisher-key /etc/aegis/trust/publisher.pem \
  --publisher-sha256 <INDEPENDENT_PIN> --publisher-signer <APPROVED_SIGNER> \
  --expected-source-sha <EXACT_SOURCE_SHA> \
  --target debian12-x86_64 --minimum-revision 1 --json
```

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

## Observed blocker in this checkout

The harness currently reports `pass: false` for the requested
`install -> verify -> update -> repair -> rollback -> uninstall -> reinstall`
sequence. Repair of the current release before update succeeds. Repair after
an update is recorded as `repair_after_update` and fails.

`platform_installer_cli._verify_installed_release` calls `_verify_release`
without forwarding the trusted predecessor manifest digest. A signed child
release therefore cannot be re-verified for repair after an update, and repair
is denied before any native effect. The harness does not bypass, monkey-patch
or fabricate success for this production contract. The blocker must be fixed
and re-tested under the normal reviewed installer change process.

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
- A reviewed repair fix for the child-release predecessor forwarding blocker.
- A generated and signed Windows double-click entrypoint and Debian guided
  entrypoint shipped inside the complete offline bundle.
- Exact final commit SHA, all artifact digests, CI/run evidence, post-reboot
  native receipts and an explicit remaining-limitations summary.

Until those gates pass on real signed disposable hosts, the installer is
**not certified**, `installed_host_verified` remains `false`, and
`production_authorized` remains `false`.
