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
