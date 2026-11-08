# B-005 | Team B signed bootstrap / CI / native host acceptance ledger

**As of 2026-11-08, PR #244 remains DRAFT and Platform 1.0 remains NO-GO.**
This file is a development handoff. No production release signer, native
installed host, Core activation, Hub activation or protected mutation is
attested by this report.

## 1. Exact-head CI

The exact PR SHA is printed in the pull request and must be compared to
`git rev-parse HEAD` by the first step of the installer CI, before any test.
Existing workflows are asynchronous and **queued or pending** at this
checkpoint, so no pass/fail job logs or completed test-produced capsule hash
can be reported. Individual workflow names:

| Workflow family | Required result before acceptance |
| --- | --- |
| Aegis Installer B-002 / D028 Offline Seed and Native Contract | Windows/Ubuntu complete exact-sha syntax + host/gate negatives |
| Aegis B1 Governed Installation Contract | Windows/Ubuntu signed B1 exact-sha controls |
| Aegis Platform-only Development Gate | Platform no-Core host/source validation |
| Aegis Debian12 Offline VM Service Contract | actual signed two-boot guest and bounded recovery evidence |
| G0-G1 Release Integrity CI | signed source/provenance requirements |
| G4 Core Link Transport CI | deny stale/duplicate/revoked operator |
| G5 Recovery Evidence CI | interrupted/forced-kill recovery |
| G6 Module Lifecycle CI | unauthorized/unselected module denial |
| G7 Handoff Preflight CI | independent handoff and absence of false READY |
| GO LIVE Cross-Gate Regression | cross-family source/regression integrity |

PR-head checkout and PS5.1/Bash syntax are now first-in-matrix
fail-fast gates. No jobs may be declared green based on schema previews,
old SHAs, synthetic keys or repository comments.

## 2. Trust chain with TRUE current scope

| Layer | Implemented candidate | Acceptance blocker |
| --- | --- | --- |
| Independently provisioned publisher trust | External PEM SHA256 and signer key ID; Windows code-signing leaf thumbprint and EXE digest | Team A/E signed root enrollment, revocation and validity snapshots |
| Manifest publisher authentication | Stock Bash/OpenSSL Ed25519 checks exact canonical Platform release-manifest digest; Windows Authenticode checks native EXE | Debian OpenSSL documented prerequisite or bundled signed static verifier; independently signed real Windows executable |
| Every signed Platform asset | Canonical `PlatformReleaseVerifier` rehashes SDK, Platform, service binary, Python runtime, dependency, SBOM and provenance | End-to-end native bootstrap must verify **all** bytes on fresh OS before running bundled runtime |
| Launcher / theme delivery integrity | Deterministic ZIP includes paths, digests for all signed Platform assets AND all three unsigned wrapper assets separately | Their **publisher delivery signature is MISSING**, and ZIP digest alone is not publisher identity |
| Native installation | B1 one-store verifier, native SCM/systemd code, owner-only service files and `OUTCOME_UNKNOWN` journal | Team A enrolled SID/UID/GID/SAFE/STOP/expiry/revocation/one-use native executor and proper file DACL/service-account provisioning |
| Healthy & continuous Platform | No activation by launchers, no second writer | Two disposable OS installed-host traces with exact platform UUID, READY health, service PID/generation, start/reboot/repair/rollback/reinstall, exclusive writer, STOP/replay refusal |

**IMPORTANT:** A structurally valid Ed25519 signature from a synthetic
CI fixture does not equal an approved production publisher or a
freshly nonrevoked key. Windows native code signing is NOT available
on draft PR #244: the existing repository
`.github/workflows/release-promotion.yml` intentionally permits
the production signing environment only for successful `main`
candidate runs. Do not weaken that guard, export signing secrets or
run a production promotion for this draft. Publisher-root freshness,
certificate revocation and signed launcher delivery remain unresolved.
There is no independently signed distributable executable hash yet.

## 3. CI test-only capsule / Team E handoff

When the **Linux installer job completes successfully**, the workflow
can publish:

- `aegis-b004-disposable-signed-core-free-capsule`
  (GitHub Actions artifact name).
- `aegis-disposable-core-free-capsule.zip`: reproducible test-only ZIP,
  not a trusted installable release.
- `disposable-test-publisher.pem`: disposable public verifier key
  generated in tests; never production trust.
- `test-only-capsule-evidence.json`: archive SHA256,
  exact release-manifest SHA256, canonical signer, all signed asset
  SHA256/path/byte lengths, and all launcher/theme delivery digests
  explicitly marked **unsigned**.

Independent QA must download the exact-run artifact, rehash the original
ZIP, and inspect every included signed asset before even considering it
for source-level acceptance. It does not satisfy LIB-01/02 or any
installed-host acceptance case.

## 4. Runtime/host acceptance gate and receipt schema needed

Both **Windows 11/Server Windows SCM** and **Debian 12 x86_64 systemd**
require independently witnessed disposable-host boot/start and
reboot/recovery. A valid receipt must bind:

- exact git SHA, signed manifest SHA256, signer + current independently
  pinned publisher trust-root digest, target ABI, complete signed asset
  digests, and exact released native executable SHA256;
- host boot ID, service path/config SHA, service SID or UID/GID and
  actual security descriptor, installed Platform UUID/public-key SHA,
  native process ID, authoritative RUN generation, observed health;
- current owner principal enrollment and exact one-use SAFE approval
  scope/fingerprint, STOP/revocation before/during action and after
  restart, replay denial, no unrelated service adoption;
- install, update, repair, approved rollback with retained monotonic
  B1 revision floor, uninstall/reinstall with same protected identity,
  crash and two-boot recovery, and exclusive writer evidence.

No such live host receipt exists at this checkpoint. Do not turn
unit/mock service state, `HASH_MATCH_ONLY`, `SIGNED_MANIFEST_ONLY`,
`AUTHENTICODE_BINARY_ONLY` or `CACHED_VERIFIED` into installed
or active acceptance.

## 5. D028 dependency order and authority separation

D028-00 must freeze Team A/C/D/E signed catalog identity/version,
publisher versus serving Hub identity, license/ABI/SDK/dependencies,
per-host verified/staged/installed/active inventories, source order,
chunk retries/STOP, separate one-use install permission, and owner
enrollment/revocation. Team B has only internal `OfflineArtifactCache`
signed local admission with exact B1 revision/generation; no public
Hub/P2P fetching, installation or activation. GC remains disabled until
Team D supplies atomic active/staged/installed disabled-dependency/
rollback/in-flight/operator pin graph, Team A supplies one-use
retention-grant contract, and Team E verifies quota/pin/rollback behavior.
Team C owns separately signed optional GUI/TUI packages.

**Priority order:**
1. Finish ten exact-SHA workflows and investigate any real failing logs.
2. Complete independently signed full-chain clean-host OS-native
   bootstrap using the SAME publisher authority and B1 engine.
3. Integrate A enrolled Windows SID/SCM ACL and Debian UID/GID/socket
   owner proof; prove current STOP/revocation/replay gates.
4. Run actual disposable Windows/Debian native installation lifecycle
   and independent Team E host receipts.
5. Complete frozen D028 catalog, package/ABI/license admission,
   optional C UI artifacts, quota/pin/GC/transfer integration.
6. Team E certifies original #201 38 rows plus LIB-01..16 separately.

No merge, main modification, production deployment, Core/Hub activation,
second signer, second owner permission service or second install writer.
