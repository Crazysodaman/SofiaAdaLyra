# Team B B-006 | Core-free signed Debian12 offline installer handoff

STATUS: DRAFT SOURCE ONLY. IG-001 is NOT CERTIFIED. Platform 1.0 NO-GO.
Never merge, deploy to owner's VM, activate Core/Hub, bypass owner SAFE, or
claim a production signing root based on disposable test keys.

## One canonical signer / one canonical installation engine

1. Canonical Platform release verifier independently authenticates one
   Ed25519-signed release manifest, target, source SHA, strict revision
   and EVERY SDK, Platform, service, Python runtime, dependency, SBOM and
   provenance asset. Test fixture release signatures are not production.
2. The existing build-host-only platform_installer_offline_capsule.py
   re-verifies the signed assets then builds a deterministic ZIP containing
   ALL of those assets and SIX explicit delivery files: Windows installer,
   Bash installer, Debian prerequisites probe, capsule signature verifier,
   native systemd evidence collector, and the canonical UI theme.
3. New offline_capsule_publisher_seal_message constructs exact bytes:
   domain ASCII aegis.offline.capsule.v1, a NUL, the SAME canonical
   release signer ID, a NUL, and lowercase ASCII capsule SHA256.
   Only the existing approved release publisher may sign those bytes.
   This separate delivery signature protects included launcher/theme
   bytes without inventing another signing authority. Draft CI can
   exercise the format using an explicitly disposable software test key.
4. On clean Debian12, verify-aegis-capsule.sh uses stock OpenSSL Ed25519,
   sha256sum and independently pinned publisher PEM fingerprint/signer.
   It authenticates the COMPLETE ZIP byte digest, then reports
   SIGNED_CAPSULE_BYTES_ONLY, not installed, not fully typed release
   verified, not currently nonrevoked, not owner approved or activated.
5. The existing B1 engine is still the only signed code publisher.
   Actual native install requires Team A's current enrolled principal,
   one-time SAFE approval, STOP/revocation and generation fences.
   Neither Bash nor PowerShell has an enabled protected mutation flag.
   The signed runtime archive still needs safe offline extraction and
   canonical B1 verification before ANY included code may execute.

## Explicit Debian12 prerequisites, without hidden network

On a disposable Debian12 AMD64 VM (real systemd manager) run:

  bash packaging/installers/debian12-offline-prerequisites.sh --json

The probe requires stock Bash, coreutils, getent, id, flock, timeout,
tar, unzip, OpenSSL with Ed25519 support, and running systemd.
Missing OpenSSL/unzip may need separately verified offline OS media.
There is NO automatic apt, curl, pip, Git, Cargo, Python, Core or WAN fetch.
Missing prerequisite results in BLOCKED exit 3 without service mutation.

After independently provisioning approved publisher trust:

  bash packaging/installers/verify-aegis-capsule.sh
    --capsule /offline/aegis-capsule.zip
    --signature /offline/capsule-signature.raw
    --publisher-key /out-of-band/publisher.pem
    --publisher-sha256 TRUSTED_PEM_SHA256
    --publisher-signer TRUSTED_SIGNER_ID

The PEM pin must be provided independently from the untrusted ZIP.

## Native Debian installed-host receipts ONLY AFTER A auth and OS install

Team E can run a read-only observer on a real disposable guest after
current owner-authorized signed installation. Unit digest is independently
obtained from the reviewed B1 native service configuration receipt:

  bash packaging/installers/observe-debian12-service.sh
    --expected-unit-sha256 SIGNED_B1_SERVICE_UNIT_SHA256

It records native unit path/SHA, boot ID, systemd PID/status/restarts
and a bounded journal digest without exposing journal content.
It deliberately marks platform_ready_authenticated=FALSE and
platform_uuid_authenticated=FALSE. Do not infer Platform READY from
systemd ACTIVE, a process ID or a running unit. Team E must additionally
witness an authenticated current platform.status, STOP, live generation,
single writer and unchanged Platform UUID across TWO actual guest boots.

## Local execution this turn (NOT an exact SHA clone or guest receipt)

Environment: Debian 13 container, Python 3.13.5, OpenSSL 3.5.5;
PID1 supervisord, no systemd manager, pwsh or Rust toolchain.
The GitHub checkout is not mounted and github.com DNS resolution fails.

Mirrored Bash implementation snippets copied into /tmp:
  bash -n /tmp/aegis-b006-debian12-prerequisites.sh
  bash -n /tmp/aegis-b006-verify-capsule.sh
  python3 -m pytest -q /tmp/aegis-b006-tests/test_prerequisites.py
                           /tmp/aegis-b006-tests/test_capsule.py

Actual observations: 12 passed in 0.21 seconds, including real
disposable Ed25519 signature success, changed capsule/wrong signer
refusal, wrong public PEM pin, malformed signature, internal key and
protected-flag denial, Debian13/no-systemd denial. The exact committed
tests and any real Debian12 positive must run on a real checkout/host;
do not relabel these mirrored local checks as exact-head CI or host PASS.

## Unresolved IG-001 blockers

- No production publisher-signed self-contained native Debian installer;
  release promotion correctly restricts production signing to authorized
  successful main release candidates, not this draft branch.
- The stock-native shell verifier itself must have independent trusted
  delivery; signed ZIP verification alone cannot safely bootstrap an
  arbitrary unsigned verifier or replace fresh signer-revocation checks.
- Team A management v1 parity/freeze, enrolled Debian UID/GID/socket
  and current SAFE/STOP/revocation/one-use owner proof remain pending.
- No actual Debian12 signed native B1 install, service PID/READY,
  systemd boot ID, journal witness or Platform UUID retention was
  collected in this environment.
- No real Windows publisher-signed EXE, SCM host lifecycle, repair,
  rollback/uninstall/reinstall or authenticated owner SID/DACL receipts.
- Team C optional signed GUI/TUI, Team D signed Library package
  ABI/license/dependency and atomic cache/pin/transfer contracts,
  and Team E independent IG-001/final installed-host proof pending.

Do not add a second installer, signer, shared writer, Hub-controlled
owner permission, undocumented network fallback or release PASS.
