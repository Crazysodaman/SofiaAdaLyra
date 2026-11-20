# Aegis Windows Authenticode signing procedure

**Status:** owner-controlled procedure; no production signing credential is
provided by this repository. Do not treat an unsigned launcher, a test
certificate, or a successful local build as a signed release.

## Scope and authority

This procedure covers the Windows launcher (`Aegis-Setup.exe`) and the
independent verification of the Platform release signature. It does not:

- generate, replace, escrow, or trust any signing credential;
- convert test signing into production authority;
- authorize installation on VENUS or any other host;
- replace SAFE, STOP, release verification, or owner approval.

Authenticode and the Ed25519 release signature are independent controls. A
valid Authenticode signature does not authenticate the release manifest or its
assets. A valid release signature does not authenticate the launcher binary.
Both must be verified before a candidate is considered install-ready.

## Implemented signing support

`packaging/installers/build-aegis-setup.ps1` accepts a caller-supplied
certificate from the Windows certificate store:

```powershell
$build = Join-Path $PWD 'packaging\installers\build-aegis-setup.ps1'
powershell.exe -NoProfile -NonInteractive -File $build `
  -OutputPath 'C:\reviewed\installer\Aegis-Setup.exe' `
  -SigningThumbprint 'CERTIFICATE_SHA1_THUMBPRINT' `
  -SigningStore 'My' `
  -TimestampUrl 'https://owner-approved-rfc3161.example' `
  -SigntoolPath 'C:\Program Files (x86)\Windows Kits\10\bin\<version>\x64\signtool.exe'
```

The script signs with SHA-256, optionally timestamps with SHA-256, and runs
`signtool verify /pa /v` after signing. It never reads, copies, or embeds a
private key or PFX password. If no thumbprint is supplied, it emits
`AUTHENTICODE=NOT_SIGNED` and the output remains test media.

The current host has `signtool.exe` available under the Windows SDK, but no
certificate with a code-signing EKU and private key in `CurrentUser\My` or
`LocalMachine\My`. Therefore the audited `Aegis-Setup.exe` remains
`NotSigned`.

## Owner provisioning prerequisites

The owner must provision, out of band:

1. A code-signing certificate whose subject, issuer, serial, SHA-1 thumbprint,
   SHA-256 fingerprint, and SPKI digest are recorded in the owner trust record.
2. A private key protected by a non-exportable CNG/HSM-backed key or an
   equivalently protected owner signing host. Do not export a PFX to the
   repository, shell history, environment variable, or release media.
3. An independently distributed trust root/chain for verifiers. Never obtain
   the trust root from the same bundle being verified.
4. A current revocation source and freshness policy. For connected signing,
   use OCSP/CRL. For an offline host, use an owner-controlled, reviewed
   revocation snapshot with an explicit validity window.
5. An RFC 3161 timestamp authority approved by the owner, or a documented
   decision to require timestamping before release.

## Pre-signing certificate validation

Run this on the owner signing host before building:

```powershell
$thumbprint = 'CERTIFICATE_SHA1_THUMBPRINT'
$cert = Get-ChildItem Cert:\CurrentUser\My, Cert:\LocalMachine\My |
  Where-Object Thumbprint -eq $thumbprint
if (-not $cert) { throw 'Signing certificate not found' }
if (-not $cert.HasPrivateKey) { throw 'Signing key is not available' }
if ($cert.NotBefore.ToUniversalTime() -gt [DateTime]::UtcNow -or
    $cert.NotAfter.ToUniversalTime() -lt [DateTime]::UtcNow) {
  throw 'Signing certificate is not currently valid'
}
$eku = $cert.Extensions |
  Where-Object { $_.Oid.Value -eq '2.5.29.37' } |
  ForEach-Object { $_.Format($false) }
if ($eku -notmatch '1\.3\.6\.1\.5\.5\.7\.3\.3') {
  throw 'Signing certificate lacks the code-signing EKU'
}
$chain = New-Object Security.Cryptography.X509Certificates.X509Chain
if (-not $chain.Build($cert)) { throw 'Signing certificate chain is not trusted' }
```

Record the thumbprint, subject, issuer, serial, validity window, chain result,
and revocation result in the signing receipt. Do not record private key
material or PFX passwords.

## Signing ceremony

1. Confirm the source commit and clean worktree.
2. Confirm the release Ed25519 public key, signer ID, source SHA, target, and
   revision floor were provisioned independently.
3. Build `Aegis-Setup.exe` with the validated thumbprint and timestamp URL.
4. Reject the candidate if the build emits `AUTHENTICODE=NOT_SIGNED`,
   `AUTHENTICODE_VERIFICATION=SKIPPED_BY_CALLER`, or a nonzero exit.
5. Copy the signed launcher into the installer payload and assemble the
   offline release.
6. Verify the launcher and release independently as described below.
7. Present the exact artifacts to the owner for install approval. Do not
   install on VENUS before that approval.

## Independent verification

### Launcher

Use a separately trusted `signtool.exe` and chain, not a verifier copied from
the candidate bundle:

```powershell
& $signtool verify /pa /all /v 'C:\reviewed\installer\Aegis-Setup.exe'
Get-AuthenticodeSignature 'C:\reviewed\installer\Aegis-Setup.exe' |
  Format-List Status, StatusMessage, SignerCertificate, TimeStamperCertificate
Get-FileHash 'C:\reviewed\installer\Aegis-Setup.exe' -Algorithm SHA256
```

Require `Status=Valid`, a code-signing signer certificate matching the
independently pinned thumbprint and SHA-256 fingerprint, a valid timestamp
where policy requires it, and the expected EXE SHA-256. `NotSigned`,
`HashMismatch`, `NotTrusted`, an expired certificate, or an unverified
timestamp is a failure.

### Release

Use the canonical `PlatformReleaseVerifier` with an independently supplied
publisher public key. Do not use `installer/trusted-publisher.pem` from the
same bundle as its own trust root.

```powershell
$env:PYTHONPATH = 'C:\reviewed\checkout\src'
python -c "from pathlib import Path; import json; from sofia.platform.ops.platform_release import PlatformReleaseVerifier; from sofia.sdk.platform_release import PlatformReleaseTarget; root=Path(r'C:\reviewed\bundle\windows-x86_64'); key=Path(r'C:\owner-trust\publisher.pem').read_bytes(); manifest=json.loads((root/'release/release-manifest.json').read_text()); sig=json.loads((root/'release/release-signature.json').read_text()); result=PlatformReleaseVerifier({'OWNER_SIGNER_ID':key}).verify(manifest, signature_b64=sig['signature_b64'], signer_key_id=sig['signer_key_id'], assets_root=root/'release/assets', expected_source_sha='FULL_SOURCE_SHA', expected_target=PlatformReleaseTarget.WINDOWS_X86_64, minimum_revision=1); print(result.release_id, result.source_sha, len(result.assets))"
```

Also run the bundled guided installer in preview mode with an independently
provisioned trust root:

```powershell
$env:AEGIS_INSTALLER_TRUST_ROOT = 'C:\owner-trust'
powershell.exe -NoProfile -NonInteractive -File `
  'C:\reviewed\bundle\windows-x86_64\installer\Install-Aegis.ps1' -Check -Json
```

`PREVIEW_OK` is evidence only; it is not installation approval.

## Revocation policy

- Check revocation at signing time and at release verification time.
- For online verification, require a successful OCSP response or a current CRL.
- For offline/disposable hosts, require a signed or owner-reviewed revocation
  snapshot with an explicit `issued_at`, `next_update`, publisher identity, and
  freshness bound.
- Do not pass `-noCheck`, ignore revocation errors, or use an expired snapshot.
- If revocation status is UNKNOWN, report UNKNOWN and block release acceptance.
- The owner must retain a revocation list for compromised launcher certificates
  and must re-verify previously issued media after any revocation event.

## Private-key protection

- Prefer a hardware-backed, non-exportable CNG key or HSM.
- Restrict certificate/key access to the owner and a named signing operator.
- Sign only on a dedicated, reviewed signing host; do not sign on a general
  development workstation or a host with untrusted build scripts.
- Keep the signing host offline except for the approved timestamp and
  revocation calls.
- Use attended/MFA owner approval for each release signing ceremony.
- Never place a PFX, password, private PEM, or exported key in Git, build
  output, chat, logs, or environment variables.
- Rotate and revoke the certificate immediately on suspected key exposure.

## Failure and blockers

The following are release blockers, not reasons to self-sign:

- no owner-provided code-signing certificate or private key;
- untrusted or incomplete certificate chain;
- missing code-signing EKU;
- expired or not-yet-valid certificate;
- unavailable or stale revocation status;
- missing trusted timestamp when policy requires it;
- `Aegis-Setup.exe` remains `NotSigned`;
- release Ed25519 verification fails or uses an in-bundle trust root;
- no disposable Windows host for installed-host acceptance.

A test-only Ed25519 release signature and a test-only Windows build remain
`TEST_SIGNED_RELEASE_ASSEMBLED_NOT_INSTALLED`; they are not a production
release and do not authorize VENUS installation.
