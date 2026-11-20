# Aegis owner-private Windows installation release

**Status:** OWNER-PRIVATE RELEASE CANDIDATE; NOT INSTALLED; NOT PRODUCTION.

This procedure covers the explicitly authorized private installation on VENUS at
`D:\Aegis`. It does not authorize a public or production release, does not
modify protected Core state, and does not install on VENUS until the owner
explicitly approves the verified candidate.

## Authority and identity

The owner authorized generation of a new owner-private Ed25519 release identity
and an unsigned-launcher exception for this private deployment.

| Field | Value |
| --- | --- |
| Signer key ID | `aegis-owner-private-2026-11-19` |
| Public key SHA-256 | `4ef931d94491216502ba8c8e7459d38acc064b50d7b1c60a993607605a0ef343` |
| Owner authorization reference | `owner-approved-private-venus-2026-11-19` |
| Private key location | Owner-only directory outside Git and release media |
| Private key included in release | No |
| Production authorized | No |

The disposable `aegis-test-disposable-2026-11-19` identity and its R2 bundle
must not be promoted or used as trusted private media.

## Unsigned-launcher exception

`Aegis-Setup.exe` remains Authenticode `NotSigned`. The owner explicitly
authorized an unsigned launcher for this private deployment only. The exception
does not weaken the internal release verification:

- `Install-Aegis.ps1` still requires an independent owner-controlled trust root;
- the canonical `PlatformReleaseVerifier` still checks the Ed25519 release
  signature and every asset digest;
- SAFE/STOP, owner authentication, one-use approvals, and protected-state rules
  remain mandatory;
- the release receipt records `private_deployment_authorized=true` and
  `production_authorized=false`.

Do not use this exception for public distribution, VENUS until approval, or any
release whose signer identity or fingerprint is not independently verified.

## Owner-private signing ceremony

1. Provision the owner key on a dedicated owner-controlled host or directory.
   The private key must be non-exported and readable only by the owner. Record
   the public key fingerprint out of band.
2. Confirm the signer ID and authorization reference in a reviewed owner record.
3. Confirm the source commit is clean and matches the intended review SHA.
4. Build the release with the owner key, independent public key, owner
   authorization reference, installer payload, wheelhouse, service, TUI and
   runtime archive.
5. Verify the release with a separately supplied public key. Do not use the
   bundle's own `installer/trusted-publisher.pem` as its trust root.
6. Run the guided installer in `-Check` mode against `D:\Aegis`.
7. Obtain explicit owner approval before running the actual installation.

Example ceremony shape:

```powershell
$keyDir = 'C:\OWNER-PRIVATE-KEY-DIRECTORY'
$bundleOutput = 'D:\SofiaDev\SofiaAdaLyra\build\aegis-release-windows-owner-private-2026-11-19'
$python = 'C:\Users\kenny\AppData\Local\Programs\Python\Python312\python.exe'
$env:PYTHONPATH = 'D:\SofiaDev\SofiaAdaLyra\src'

& $python tools\build_aegis_release.py `
  --repo D:\SofiaDev\SofiaAdaLyra `
  --source-sha FULL_SOURCE_SHA `
  --output $bundleOutput `
  --target windows-x86_64 `
  --test-signing-key "$keyDir\release-private.pem" `
  --signer-key-id aegis-owner-private-2026-11-19 `
  --owner-private-authorization owner-approved-private-venus-2026-11-19 `
  --installer-dir D:\SofiaDev\SofiaAdaLyra\build\installer-payload `
  --trusted-public-key "$keyDir\release-public.pem" `
  --trusted-signer-key-id aegis-owner-private-2026-11-19 `
  --dependency-wheelhouse D:\SofiaDev\SofiaAdaLyra\build\wheelhouse `
  --service-binary D:\SofiaDev\SofiaAdaLyra\target\release\aegis-platform-service.exe `
  --tui-binary D:\SofiaDev\SofiaAdaLyra\target\release\aegis_tui.exe `
  --runtime-archive PATH_TO_VERIFIED_PYTHON_RUNTIME_ZIP `
  --application-version 0.1.0 `
  --python-version 3.12.10 `
  --revision 1
```

The assembler refuses an owner-private release if the source tree is dirty,
`--allow-dirty` is present, or independent installer trust is missing.

## Independent verification

```powershell
$bundle = 'D:\SofiaDev\SofiaAdaLyra\build\aegis-release-windows-owner-private-2026-11-19\windows-x86_64'
$trust = 'D:\SofiaDev\SofiaAdaLyra\build\owner-private-trust-2026-11-19'
$env:AEGIS_INSTALLER_TRUST_ROOT = $trust

powershell.exe -NoProfile -NonInteractive -File `
  "$bundle\installer\Install-Aegis.ps1" -Check -Json
```

The owner trust root must contain `trusted-publisher.pem` and `trust.json`
provisioned separately from the bundle. Require:

- `outcome=PREVIEW_OK`;
- signer key ID `aegis-owner-private-2026-11-19`;
- public-key SHA-256 `4ef931d9...ef343`;
- the expected source SHA, release ID, manifest digest and revision;
- no blocker for missing trust, mismatched trust, or unsupported host.

The launcher itself remains `NotSigned`; this is accepted only under the
explicit owner-private exception above.

## Installation commands for later owner approval

Do not run these until the owner approves this verified candidate.
`D:\Aegis` is the chosen install root; the guided wizard shows it before any
effect and still requires attended owner authentication and UAC.

```powershell
powershell.exe -ExecutionPolicy Bypass -NoProfile -File `
  'D:\SofiaDev\SofiaAdaLyra\build\aegis-release-windows-owner-private-2026-11-19\windows-x86_64\installer\Install-Aegis.ps1'
```

When prompted, accept `D:\Aegis` as the installation directory, select the
desired components, and complete the existing attended SAFE approval and UAC
steps. The unsigned `Aegis-Setup.exe` may also be used only after the owner
explicitly accepts the SmartScreen/unsigned-launcher warning.

## Fail-closed conditions

Stop if any of the following occurs:

- trust root missing, inside the bundle, or mismatched;
- public-key fingerprint or signer ID differs from the owner record;
- release source SHA, manifest, signature, or asset digest differs;
- revoked or unavailable publisher trust;
- owner approval, SAFE, or STOP is unavailable;
- an unexpected host or target is selected;
- any attempt to install without explicit owner approval.

This candidate is `OWNER_PRIVATE_RELEASE_ASSEMBLED_NOT_INSTALLED`. It is not a
production release, has not been installed, and has not been live-verified.
