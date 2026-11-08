# AG-D028 Team B | signed installer, offline seed and Artifact Library boundary

**Status: D028-01/B-002 PARTIAL, release/host GO = NO.** This is a source
handoff on isolated draft PR #244, not an active installation workflow or
approval. [Draft design #248](https://github.com/Crazysodaman/SofiaAdaLyra/pull/248);
[implementation tracking #250](https://github.com/Crazysodaman/SofiaAdaLyra/issues/250);
[acceptance #201](https://github.com/Crazysodaman/SofiaAdaLyra/issues/201).
D028 defines 16 mandatory LIB installed-host scenarios; the existing
acceptance matrix remains exactly 38 rows.

## Owned batches and specific library cases

| Batch | Team B responsibility | Release cases and current state |
| --- | --- | --- |
| D028-00 | Sign off one Team A authenticated versioned catalog/transfer/install API, publisher trust and SAFE/STOP/revocation; no second owner auth | Contract **UNFROZEN** |
| D028-01 (B lead) | Independently signed, Core-free offline seed verified before native Windows/Debian install with no network fallback | LIB-01/02 **NOT CERTIFIED** |
| D028-02 (A/B/D) | Map signed index/verified CAS artifact to B1 install plan; dependency preview and separate install/activation | LIB-04/05/06 **NOT CERTIFIED** |
| D028-03 (A/B) | Package Core-free owner-activated Hub role; read-only signed index/immutable bytes; per-peer ACL/quota | LIB-03/08/09 **NOT CERTIFIED** |
| D028-04 (A/B/D) | Recipient independently re-verifies sender bytes, signer, target, license, STOP and fresh owner install approval | LIB-07/08/10/13 **NOT CERTIFIED** |
| D028-05 (B/D) | Integrate existing bounded OfflineArtifactCache, active/staged/rollback pins, quota-safe GC and identity-retaining reinstall | LIB-09/10/11/12/13/15 **NOT CERTIFIED** |
| D028-06 (C lead, B package) | Separately signed optional WinForms GUI and Rust TUI artifacts using shared theme, not mandatory headless dependencies | LIB-14/16 **NOT CERTIFIED** |
| D028-07 (E independent) | Full 4-host exact-SHA signed negative/positive evidence, including reboot/STOP/revocation/install and privacy/retention | LIB-01..16 **NOT CERTIFIED** |

## Canonical code reuse (no new installer/signer/owner writer)

- **Canonical release signer verifier:** `sofia.platform.ops.platform_release.PlatformReleaseVerifier`.
  `platform_installer_bundle.verify_offline_installer_bundle` requires exact
  signed manifest/assets/target/source/revision and independent pinned
  publisher public-key fingerprint. Signature alone grants no permission.
- **D028-01 neutral seed review:** `platform_installer_offline_seed.review_core_free_offline_seed`
  only accepts explicitly selected local media or verified local-cache bytes,
  reuses the canonical signed release verifier, inspects dependency wheels for
  Core/module/model contamination, traversal, ZIP redirects, duplicates and
  expansion. Its output is a **read-only source review**, not a native bootstrap.
- **Canonical B1 install authority:** `PlatformInstallationStore`,
  `install_staged_release`, `verify_installed`, signed revision floor and
  `ExecutionApprovalVerifier`. The existing B1 verifier now authenticates a
  manifest's signed parent, while publication requires that exact parent in
  successful durable B1 history; native update further binds it to the
  selected previous signed service release. This is not a replacement B1 engine.
- **B-002 native effect adapter:** `platform_installer_native_service` has
  Windows SCM and Debian12 systemd register/start/repair/replace/remove
  primitives from exact verified B1 service identity. Native CLI/public
  wiring is **disabled**, service status is UNKNOWN until actual health
  evidence, and no Core or Hub activation is inferred.
- **B-002 owner/OS transaction:** `platform_installer_native_transaction`
  requires an existing one-use exact SAFE owner approval, current STOP and B1
  generation/identity, and writes a B1-owned OS-effect journal with explicit
  `OUTCOME_UNKNOWN` after an uncertain native effect. This is subordinate
  service-effect evidence, never a second canonical Core/Platform writer.
- **Existing cache:** `OfflineArtifactCache` from `platform_install` has
  SHA-pinned, bounded local import. It is **not** yet a full D028 immutable CAS,
  chunked resume or active/rollback-aware garbage collector; do not claim so.
- **One API boundary:** Team A owns authenticated service session, current
  enrollment, operator SID/UID/group, revision/STOP, revocation and proof
  policy. Do not add a second Hub HTTP owner grant, IPC wire schema or
  client-supplied `approved` boolean.
- **UI distribution:** Team C canonical
  `packaging/gui/Start-AegisControlCenter.ps1` (Windows) and Rust
  `aegis_tui` (`sofia-ui-broker`), shared
  `contracts/ui/aegis-theme-v1.json`. Package only signed reviewed
  artifacts by optional explicit request; no headless GUI requirement.
- **Modules/Core:** Team D provides separately signed SDK definitions and
  dependency/ABI/license closure; a library object is never allowed to clone
  Core private identity, personality, memory, secrets or a writer.
- **QA:** Team E supplies independent release digests, source/target,
  disposable OS identity and negative tests before any LIB case or #201
  row may be marked accepted.

## Mandatory bootstrap and service boundaries still open

1. An independently authenticated **native seed bootstrap itself** must run
   on a fresh Windows/Debian12 host with no project Python, Git, Cargo, Ollama,
   model, personal Core, or WAN. Current Python verification runs **after a
   trusted interpreter exists** and is not a bootstrapper.
2. Team A must freeze exact `D028-00` schemas, live owner enrollment/SAFE/STOP,
   SID/UID and signing/revocation checks. Only after this can the blocked
   PowerShell/Bash entrypoints route authorized mutations to the native service.
3. Native driver must provision/reconcile service account + protected state
   permissions, Windows DACL and Debian systemd runtime socket compatibility,
   installed executable/native health proof, boot-time recovery and
   revocation **during** a pending effect, without broad ACLs/PrivateTmp
   isolation or adoption of foreign service.
4. B1 code install + native service transaction must be integrated into one
   installer orchestration with exact owner consent and durable reboot/crash
   recovery on each disposable OS, including signed rollback, removal and
   reinstall preserving the same Platform UUID/key. Current tests use mock
   native adapters and synthetic signer/owner credentials.
5. D028 package metadata needs one frozen signed index/schema for
   `sdk/core_runtime/core_definition/module/model/asset`, per-host inventory
   and separate verified-cache/installed/active receipts, dependency graph,
   licenses and signed optional UI contents.
6. Hub/peer transfer needs current mutual enrollment, per-artifact allowed
   source, no Internet fallback, chunk admission and digest/signature/license
   verification on receiver, quota/pin graph and explicit separate owner
   install grant. Current installer branch has **no Hub or P2P transfer**.
7. Team E must run LIB-01..16 on signed disposable W-EMPTY, D-HUB, D-CLIENT
   and W-PEER hosts, two-boot and interruption cases, preserve independent
   artifacts and mark all remaining rows no better than NOT CERTIFIED.

## Suggested dependency order

D028-00 authority/schema freeze → D028-01 independently signed Core-free
bootstrap and native service transaction → D028-02 signed catalog/plan and
separate install receipts → D028-03 Hub and D028-04 peer transport (after
enrollment) → D028-05 safe chunk/quota/pins/rollback → D028-06 optional UI
packaging and parity → D028-07 independent signed installed-host matrix.

Parallel work is permitted only where the stable interfaces are not guessed.
No independent "Hub admin" permission, implicit WAN download, automatic
Core activation, second local state writer, production deployment or main
merge is authorized.


## B-003 continuation: stock-OS media preflight + SAFE-fenced cache (2026-11-08)

**P1, clean-host prerequisite now available, NOT complete installation:**
Existing `packaging/installers/install-aegis.sh` and
`packaging/installers/Install-Aegis.ps1` accept, respectively:

```bash
bash packaging/installers/install-aegis.sh \
  --verify-seed /media/OWNER/aegis-offline-seed.zip \
  --trusted-seed-sha256 <independently-pinned-64-hex-digest> --json
```

```powershell
& .\packaging\installers\Install-Aegis.ps1 `
  -VerifySeed 'D:\reviewed\aegis-offline-seed.zip' `
  -TrustedSeedSha256 '<independently-pinned-64-hex-digest>' -Json
```

Uses stock Debian 12 `sha256sum/realpath/stat` and Windows PowerShell
5.1 `Get-FileHash`, WITHOUT any installed project Python, Git, Cargo,
Ollama, Core or network. Refuses missing/incorrect hash, redirected
media, oversized/unavailable file and combining seed mode with protected
operations. **`HASH_MATCH_ONLY` is not a verified Ed25519 publisher signature,
approval, extraction or installation.** The hash must come from a reviewed
independent signed release provenance, never merely from the seed volume.
The packaged, independently verifiable self-contained native bootstrap is
still a required unimplemented P1 deliverable.

**P2, native enrollment:** Team A's one broker, current operator enrollment,
owner SAFE/STOP and revocation are NOT signed off. The systemd driver now
demands a dedicated non-root noninteractive `aegis` account and service-owned
private executable/runtime/identity/state paths before writing a native unit.
Runtime directory name is reserved as `/run/aegis-platform` with **0700**
private mode; do not broaden to proposed 0750/operator-group/0660 until
Team A authenticates exact enrolled UID/GID and Team E tests Linux external
client access. Windows LocalService file DACL and enrolled one-SID pipe access
still require a signed native provisioning/host proof. The shell launchers
remain protected-operation DENY (exit 3); stock media check cannot grant access.

**P3, signed native service:** B1 code install, existing one-use SAFE
proof, signed native SCM/systemd code registration/update/repair/rollback/
unregister primitives and `OUTCOME_UNKNOWN` journal exist in this draft.
They have NOT been joined to a fully governed signed host bootstrap with
independent native health/start/reboot/service ownership evidence; no
disposable-host PASS. Protected Platform UUID retention is unit/mock-test
only; actual reinstall proof remains required.

**P4, D028-02:** `platform_library_admission` reuses the exact
`OfflineArtifactCache` byte store and B1 installation receipts.
It independently verifies the signed Core-free release before selecting
a SHA-bound asset for local cache; a separate one-time existing SAFE grant
and B1 generation/floor recheck are mandatory for the INTERNAL
`platform.library.cache_admit_verified_seed` candidate operation. This
candidate is NOT on the Team A public wire and MUST be reconciled with
D028-00 before activation. Read-only inventory distinguishes
`CACHED_VERIFIED` from `installed: null` and `active: null`.
A Hub's claim cannot become a local installed/active receipt.

**P5, D028-05:** read-only cache/storage review reports verified object bytes,
quota, physical free bytes/inodes, signed B1 historical-receipt retention
and unknown pins. **No garbage collection or Hub transfer listener is enabled.**
All deletion is denied until Team D supplies the full
ACTIVE/STAGED/INSTALLED_DISABLED_DEPENDENCY/ROLLBACK_RETAINED/
IN_FLIGHT_VERIFICATION/OPERATOR_PIN graph and Team A supplies separately
approved one-use retention authority with atomic revision fencing. Keep the
one intended Sofía VM primary Library separate from Core private state and
the live deployment strictly unperformed.

**Evidence limitation:** New stock-OS CLI and internal SAFE/cache tests are
part of exact-head GitHub CI; unit and runner tests do not prove a clean-host
signed release, a real Windows SCM/Debian systemd service or LIB acceptance.
Team E must independently verify actual signed artifacts and four-host
installed-service receipts. The original 38 acceptance rows and LIB-01..16
are still unaccepted. No main edit, production deployment, automatic Core or
Hub activation, independent signing root, second installer or writer.


## B-004: independent publisher proof and staged offline media (2026-11-08)

**Exact-HEAD unit/runner CI not yet resolved. No production-signed artifact or installed-host receipt is claimed.**

**Debian signature proof:** The existing `install-aegis.sh` now additionally accepts:

```bash
bash packaging/installers/install-aegis.sh \
  --verify-publisher /absolute/offline/staged-release \
  --publisher-key /absolute/out-of-band/trusted-publisher.pem \
  --publisher-sha256 <64-lowercase-hex-SHA256-of-public-PEM> \
  --publisher-signer <reviewed-signer-key-id> --json
```

It uses stock shell, `sha256sum`, `base64`, and OpenSSL's Ed25519
`pkeyutl -verify -rawin` implementation to check the **exact canonical
PlatformReleaseManifest.digest** using the existing release signature and
an independently pinned public-key fingerprint. It denies an untrusted
signer, incorrect key, malformed/duplicated signature envelope, changed
manifest, and mixed install/owner-authorization flags. Linux images without
OpenSSL fail closed: OpenSSL is not guaranteed present on every minimal
Debian 12 install. The output is only `SIGNED_MANIFEST_ONLY`; it has
**not** verified all assets, OS compatibility, complete Python runtime,
installed anything, or consumed current SAFE permission.

**Windows publisher trust:** `Install-Aegis.ps1` also offers:
`-VerifyPublisherBootstrap <reviewed-native-exe>`,
`-TrustedPublisherThumbprint <independently-pinned-40-hex-thumbprint>`,
`-TrustedBootstrapSha256 <independently-pinned-64-hex-digest>`,
plus optional `-Json`. Uses stock Windows PowerShell 5.1
`Get-AuthenticodeSignature` and `Get-FileHash`, requires valid
code-signing EKU/certificate and exact SHA. This checks the native
bootstrap **executable's** Authenticode signature, not the canonical
Ed25519 PlatformReleaseManifest. No approved production-signed native
bootstrap executable has been built or witnessed in #244. Its successful
result would be `AUTHENTICODE_BINARY_ONLY`, not installation authority.

**Offline media assembler:** `platform_installer_offline_capsule.py`
uses the existing canonical signed Platform verifier and
`review_core_free_offline_seed` on a **release builder** to reproducibly
package the complete signed release asset set, both launchers and the
shared UI theme under one `aegis/` archive tree. It refuses unsigned
asset drift, symlinked staging, overwrite and optional Core/model bytes.
SHA-256 and exact release-manifest digest are recorded. Since the
launchers/theme are not themselves in the signed release manifest,
`launcher_publisher_signature_verified=false` and
`self_contained_native_installer_certified=false` remain mandatory
receipt fields. No signing private key enters this builder; the release
publisher/CI certificate workflow must independently attest the capsule
and signed native executor before any external release claim.

**Disposable CI artifact:** The installer workflow can emit a synthetic
software-signed Core-free capsule, its test-only public PEM and
`test-only-capsule-evidence.json` with exact SHA-256 for Team E. This
fixture uses an ephemeral non-production signer and fake service/runtime
payload and **cannot be deployed**. GitHub Actions artifacts are queued
until actual execution; only after a completed, rehashed run can E cite
their exact artifact hash and evidence ID.

**Remaining end-to-end install blockers:** Actual stock-host
certification requires a signed native executable capable of verifying
the complete Ed25519 manifest/assets without any preinstalled Python,
an independently pinned publisher root and code-signing certificate,
signed native service-account ACL and Windows operator SID/Unix socket
provisioning, current Team A authenticated enrollment/SAFE/STOP/expiry/
revocation, B1 native install/update/repair/rollback/uninstall/reinstall
with persistent UUID, and Team E signed Windows/Debian disposable-host
receipts through reboot and failure. Until then, protected shell/GUI
operations remain denied. Neither a capsule hash, Authenticode-only
check nor raw manifest signature is a complete installer certificate.
