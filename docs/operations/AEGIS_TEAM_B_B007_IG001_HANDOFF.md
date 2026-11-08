# Team B B-007 | IG-001 Debian offline signer and native-host evidence

**Status 2026-11-08: DRAFT / IG-001 not accepted / Platform 1.0 NO-GO.**
Only existing B1 installation, existing publisher and Team A's canonical owner
SAFE/STOP/management broker may authorize or publish code. This report does
not enable protected shell operations, install a host or claim Platform READY.

## Implemented change

- The existing build-host `platform_installer_offline_capsule.py` produces
  one deterministic Core-free ZIP, now with `aegis/delivery-index.v1`.
  Each tab-delimited row is exactly lowercase SHA256, byte length and safe
  ASCII member path. The ZIP contains every existing B1-signed SDK,
  Platform, native service, bundled Python 3.12 runtime, lock, SBOM and
  provenance file plus separately identified Bash/PowerShell verification,
  observer, theme and installer-delivery files.
- The signed **whole-capsule** Ed25519 proof stays in the original
  `verify-aegis-capsule.sh`; the signer is the existing publisher key,
  independently pinned outside the untrusted release medium.
  `SIGNED_CAPSULE_BYTES_ONLY` never means full canonical B1 validation,
  approved install, current key nonrevocation, healthy service or READY.
- New read-only `inspect-aegis-capsule-members.sh` takes the independently
  authenticated ZIP SHA256 and rehashes every bounded ZIP member against
  the outer-signed delivery index using stock Bash/unzip/sha256sum.
  It also rejects unlisted/duplicate/missing paths, unexpected index,
  traversal, unsorted rows and changed sizes. It never extracts,
  executes, contacts Internet, registers systemd or creates owner grants.
  Its result is `MEMBERS_HASHED_NOT_INSTALLABLE` and its
  `publisher_signature_verified` field deliberately remains false.
  BOTH tools must check the same ZIP and exact SHA; neither creates
  authentication or safe mutation authority for the other.
- Existing `observe-debian12-service.sh` additionally observes
  `/run/aegis-platform/mgmt-<epoch>.sock` inode count and restrictive
  owner/GID/mode. It never contacts the socket or claims current operator
  enrollment, authenticated Platform status, service generation or UUID.

## Actually executed local verification (byte-proven Git blobs)

Local OS: Debian 13 container (not Debian12), Python 3.13.5,
OpenSSL 3.5.5, with no systemd PID 1, Windows PowerShell or Rust toolchain,
no /dev/kvm, and no external GitHub DNS/checkout.

The checked Bash files and test files were reconstructed locally and verified
using `git hash-object` against the exact GitHub source blob SHA,
not source-line approximations. Representative blobs:
- `verify-aegis-capsule.sh` c389fedf0c6b91fa452ee48f1bb087e72c7e92e0
- `debian12-offline-prerequisites.sh` 904a91c7e62a36dd408c0c048f3120ade1e8d707
- `observe-debian12-service.sh` 8b3632fa8251d162906875ed1736e6f62a1a8212
- `inspect-aegis-capsule-members.sh` 4be74c87489753ff0dc6e50b1995111cd5fd2a50
- `test_ui_aegis_installer_delivery_index.py` 36a71568136e501b471973191f7e3df75702797d

Commands actually executed:

```bash
cd /tmp/aegis-b007
bash -n packaging/installers/verify-aegis-capsule.sh
bash -n packaging/installers/debian12-offline-prerequisites.sh
bash -n packaging/installers/observe-debian12-service.sh
bash -n packaging/installers/inspect-aegis-capsule-members.sh
python3 -m pytest -q -o addopts='' \
  -o filterwarnings=ignore::pytest.PytestUnknownMarkWarning \
  test/test_ui_aegis_installer_capsule_signature.py \
  test/test_ui_aegis_installer_debian_prerequisites.py \
  test/test_ui_aegis_installer_debian_observer.py \
  test/test_ui_aegis_installer_delivery_index.py
```

**Observed: 32 passed in 0.54 seconds, one expected test-fixture
duplicate-ZIP-name warning, no failing assertions.**

A further local disposable Ed25519 suite signed a synthetic ZIP using a
temporary key and exercised the stock whole-capsule verifier and exact
member-hash inspector against the SAME ZIP: 2/2 positive proof steps
accepted; 2/2 post-signing tamper denials returned exit 3. One temporary
synthetic ZIP SHA256 was
`1f34e19cdc4a74152f4f227575bf90348a76ca0bc1536cc0151b9a23d7ece588`;
it contains **NO actual Platform SDK, service or Python runtime** and
is not a release artifact or independently approved publisher root.
These tests do NOT attest the integrated Python B1 capsule builder, actual
Debian12, Windows SCM, native service health or any original #201 row.

## Commands for Team E on a disposable Debian12 guest

Run only against a trusted independently delivered, publisher-signed release,
with offline OS prerequisites already present:

```bash
bash packaging/installers/debian12-offline-prerequisites.sh --json

bash packaging/installers/verify-aegis-capsule.sh \
  --capsule /offline/aegis-capsule.zip \
  --signature /offline/aegis-capsule.sig \
  --publisher-key /independent-trust/publisher.pem \
  --publisher-sha256 PINNED_PEM_SHA256 \
  --publisher-signer PINNED_SIGNER_ID

bash packaging/installers/inspect-aegis-capsule-members.sh \
  --capsule /offline/aegis-capsule.zip \
  --expected-sha256 VERIFIED_CAPSULE_SHA256
```

This is **read-only**. Do not run `--operation install`, force systemd,
bypass a missing OpenSSL/unzip, or treat a ZIP digest as an owner grant.

The missing installer integration must securely extract the reviewed package,
verify the canonical INNER signed B1 release manifest and ALL release assets
(including the bundled runtime) before execution, and invoke the existing
B1-owned governed native transaction ONLY through Team A's current
owner-enrollment/SAFE/STOP/revocation and exact generation authority.

Only after that genuinely authorized integration works, Team E may collect
real systemd unit and journal observations:

```bash
bash packaging/installers/observe-debian12-service.sh \
  --expected-unit-sha256 PINNED_B1_SIGNED_UNIT_SHA256
```

This observer does not itself prove READY/UUID. The independent same-host
management read MUST use Team A's source-pinned
`read_linux_platform_status` authenticated Unix client, current owner
enrollment, installed service UID/GID, optional separately approved
operator socket GID, exact RUN generation and live STOP checks. Capture
the public sanitized status, separate cold boot IDs, actual PID, journal
digest and same Platform UUID across reboot/restart. Unenrolled, revoked,
STOPPED or stale-generation requests must be denied.

## Exact cross-team OS authority conflict to resolve at IG-001

Team B's native Debian unit currently has `User=aegis`,
`Group=aegis`, `RuntimeDirectoryMode=0700` (owner-only socket 0600).
Team A's optional *external operator* path requires a separately approved
`aegis-mgmt` GID, runtime 0750 and socket 0660. Its current
`systemd_management_operator_group` implementation checks the installed
runtime GID against service effective GID. Changing modes/groups before
Team A/E signoff can either break access or accidentally broaden exposure.
The B1 publisher uses private immutable files; dedicated service UID
ownership/ACL provisioning must be reconciled without a second writer
or unapproved `chown`. **No native group mode was changed.**

## Missing proof and release blockers

- No approved production-signed Core-free capsule or immutable publisher
  revocation/expiration receipt at this branch SHA; production signing is
  intentionally forbidden on an unapproved draft.
- No full clean-host B1 installation orchestration, signed runtime extraction
  and owner-grant bridge to A's current broker, nor genuinely enrolled
  external Debian operator group/socket.
- NO actual disposable Debian12 install, systemd READY, operator read,
  journal/reboot/identity-retention or STOP/revocation receipt from B-007.
  #249's historical 2-boot guest artifact belongs to Team D's own SHA,
  not to this B-007 candidate.
- Exact integrated Python B1 tests, Rust, Windows PowerShell and the
  Debian12 disposable VM **NOT EXECUTED LOCALLY** on the full repo.
  Full exact-SHA GitHub CI remains required at IG-001 and final release.
- D028 signed catalog/ABI/license/pins/transfer and C optional signed GUI/TUI
  remain under A/C/D/E contract HOLD; no Hub/peer or Core activation.

No merge, main modifications, secondary signer/installer, protected ACL
broadening, live deployment or release PASS.


## B-007 follow-on native interpreter traversal correction

The existing B1 installed release materializes its signed Python 3.12
runtime under `release/runtime/python/bin/python3.12`, while the signed
Rust native service is under `release/assets/`. A genuine systemd
`User=aegis` `ExecStart` can fail with `EACCES` even if both final
executables are correctly owned if `release/runtime` or
`release/runtime/python` remains root-owned and mode 0700.

The current native Debian driver now enumerates every directory from
the trusted B1 root down to **both** executables. It refuses wrong UID,
group/world access or a non-directory/non-owner-traversable intermediate
folder before creating any systemd unit. Two POSIX negative tests were
added, respectively for an intervening runtime UID mismatch and a
directory lacking owner-execute permission. **These two tests are
committed but not executed on this isolated full checkout locally.**
The verified B1 owner remains the sole installer/identity writer; this
change never recursively chowns paths, creates the service account,
changes sockets or grants an install capability.

Required Team A/B installation ceremony remains separately scoped:
* B1 signed byte installation and full runtime materialization;
* exact installed `aegis` non-root UID/GID and owner-only state/code
  ownership transition, attended through the canonical one-use SAFE
  permission and current STOP/revocation checks;
* optional `aegis-mgmt` supplementary GID, operator UID and precisely
  0750/0660 endpoint mode **only** after independent owner
  enrollment, signed profile and A/C/E contract signoff;
* native systemd READY and authenticated Platform status after real
  service registration, with independent Team E boot/journal/UUID
  receipts.

This is a development guard against premature service registration,
not proof of native install/start.
