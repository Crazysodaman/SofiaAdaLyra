# Team E E-003 | Disposable four-host Artifact Library execution and evidence protocol

**Status: TEST PLAN ONLY, NOT EXECUTED.** Platform 1.0 `GO=NO`; canonical release matrix `38` rows (**7 FAIL, 31 NOT TESTED, zero accepted**); mandatory `LIB-01..16` (**all 16 NOT TESTED**). This plan does **not** contain verified operating-system host IDs, valid owner approvals, installed release signatures, actual certificates, endpoint addresses, installed service receipts or network captures.

**Reference requirements:** [#201](https://github.com/Crazysodaman/SofiaAdaLyra/issues/201); [#250](https://github.com/Crazysodaman/SofiaAdaLyra/issues/250); [PR #248 design](https://github.com/Crazysodaman/SofiaAdaLyra/pull/248) inspected at `8d5c7ae58fde4a51a3beb3d0d73ad956c0a80f21`; [Sofía VM one-primary deployment specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/8d5c7ae58fde4a51a3beb3d0d73ad956c0a80f21/docs/roadmaps/AG_D028_SOFIA_VM_PRIMARY_LIBRARY_DEPLOYMENT.md); [canonical 16-case QA runbook](https://github.com/Crazysodaman/SofiaAdaLyra/blob/8d5c7ae58fde4a51a3beb3d0d73ad956c0a80f21/docs/roadmaps/AG_D028_ARTIFACT_LIBRARY_QA_RUNBOOK.md); [Team E 16-case ledger](PLATFORM_1_0_TEAM_E_AG_D028_LIB_LEDGER_2026-11-08.md), [original 38-row ledger](PLATFORM_1_0_TEAM_E_EVIDENCE_2026-11-08.md), [combined integration plan](PLATFORM_1_0_TEAM_E_COMBINED_INTEGRATION_PLAN_2026-11-08.md). The machine-readable **inert fixture** is `test/fixtures/aegis_d028/qa_four_host_topology.json`, guarded by two additional `test/test_ops_platform_row_preflight.py` tests. No second acceptance runner or signer.

## 1. Real future placement vs disposable test roles

**Owner-approved future deployment:** ONE logical Library with ONE PRIMARY Hub on the existing Sofía VM, zero production replicas initially, separately governed optional Sofía Core worker, and potential read-only replicas later. **This is a design target, not a deployed service or automatic Core cutover.** The earlier VM Debian version, dynamic memory, real disk capacity, supported ABI, systemd configuration, actual Core/Platform identity and canonical writer placement must be *measured* before any owner-authorized installation. In particular Debian 13 cannot be assumed equivalent to the required signed Debian **12** release. No calls to Artemis, Venus, Sofía VM, the production LAN, real Portainer, or the owner secret are part of this QA plan.

The **four disposable independent hosts** below use isolated fresh OS images; no fixed public/private IPs, persistent service credentials or actual production DNS are recorded in the source fixture.

| Symbolic test host | Installed OS contract | Initial test role | Native proof |
| --- | --- | --- | --- |
| `W-EMPTY` | Supported Windows 11 / Server build recorded at run start | Empty recipient, optional **signed** WinForms, CLI/TUI | Offline native signed AG-D011 bootstrap and SCM identity; no Python/Git/Cargo/Ollama/Core |
| `D-HUB` | Exactly **Debian 12**, kernel/ABI recorded | One owner-enabled **PRIMARY Hub** and separate Core-free Platform | Offline signed AG-D011 bootstrap, systemd PID1, unique Platform identity and signed index; headless CLI/TUI |
| `D-CLIENT` | Exactly Debian 12, separate fresh OS instance | Independent enrolled receiver | Offline boot, SDK and native service, no Core, bounded transfer and recipient verifier |
| `W-PEER` | Supported Windows build, distinct Platform identity | Enrolled signed artifact sender, later **test-only READ_REPLICA** phase | Exact digest offer, peer authorization, current signer and no remote install grant |

The one **logical Library ID** is distinct from all **four per-Platform IDs**, all sender/receiver transport identities, the publisher signing root, and all synthetic Core identity/lineage IDs. Initial catalog role state: `D-HUB PRIMARY`, epoch/generation **observed rather than fabricated**, **zero replicas**. Local caches are not independently writable master Libraries. No package transfer may clone protected `sofia.db`, a live Core writer, owner secret, keys, personality/memory or module credentials.

**Network boundary:** an explicitly approved *disposable* lab-only network with WAN default DENY, no production LAN routing, DNS discovery trust, Internet fallback or public listener. Packet capture, system firewall state and physical isolation are independently recorded. Permit only exact enrolled lab peers/Hub addresses and mTLS current credentials; authentication does **not** equal the SAFE permission to transfer or install. If the runner cannot reliably isolate its network, mark the relevant LIB case **BLOCKED** rather than using the owner's real LAN.

## 2. Entry fence before anything runs

1. Coordinator freezes immutable exact SHA for each contributing source PR and its base parents, supported Windows/Debian version and a **single** resulting integrated tree/commit, with conflicts reviewed (especially stacked A #235→#241, D #238→#239→#246, D #236→#249 and signed D #251 planner).
2. Team A and C jointly sign off **ONE** versioned Rust/Python authenticated management/Library request+response contract, typed STOP/revocation/denial/unknown/stale state, generation, fresh observed-at, idempotency, signed catalog logical ID/role/epoch/revision, explicit enrolled SID/UID/audience and no duplicated REST/IPC authority.
3. Team B signs off **ONE** native governed installer + package/verifier boundary with independently trusted publisher roots, complete offline Platform-only Windows/Debian artifacts, support ABI and installation receipt semantics. A signed **full-Sofía** Core-containing RC wheel is not a substitute.
4. D signs off pinned exact dependency, license/source distribution, signed module and synthetic Core fixtures and worker crash/hot-unplug, plus *recipient-side* independent signature check. #251's source-only `VerifiedModulePackage` object cannot grant source authenticity, acquisition or install.
5. Team E confirms CI at the **current exact head** for each source, preserves red historical negative workflows and the latest successful isolated #249 recovery comparison without reclassifying #236's failed source. A red mandatory negative or pending unreviewed contract blocks assembly.
6. Only after (1)–(5) may the team assemble **one isolated integration test branch**, never main, and create CI jobs for the four disposable machines. No production service enrollment/Hub/real Core.

## 3. Ordered host exercises, witness points and failure injection

| Phase | Mandatory actual observations | LIB cases |
| --- | --- | --- |
| First boot | Signed offline Platform+SDK only, native Windows SCM/Debian systemd, own runtime, no installed Core/optional modules/models/developer toolchain; approved UI optional | LIB-01,02,15 |
| Primary setup | Initial one logical Library, primary on D-HUB, **zero replicas**, unique IDs, verified current publisher-signed index, owner-enrolled LAN client, no externally exposed Hub | LIB-03,08,15 |
| Selective acquisition | Exactly chosen synthetic Core A but not B, later A+B under distinct identities; module A then dependency B→A with unselected C absent; state transitions `INDEXED/CACHED_UNVERIFIED/CACHED_VERIFIED/STAGED/INSTALLED_DISABLED/ACTIVE` independently observed; **no auto activation** | LIB-04,05,06 |
| Signed peer | Disable Hub and WAN; W-PEER offers exact licensed digest to D-CLIENT, receiver independently verifies **full bytes + signer + current revocation + OS/SDK/ABI + license**, installation requires separate one-time local approval | LIB-07,08,09 |
| Adversarial transfer | Forged/expired peer, wrong library/target, stale catalog/epoch, reused idempotency, revoked signer, wrong source digest, malicious archive, tampered/missing chunk, out-of-bounds size, quota/disk pressure, fail-closed STOP during every phase | LIB-08,09,10,11,13 |
| Storage/lifecycle | Synthetic signed logical payload **larger than 512 MiB** split into bounded chunks, measured peak RAM, valid resume/reassemble digest; active/staged/rollback/transfer pins prevent GC, unreferenced CAS can be reclaimed under current approval; signer-verified local rollback/reinstall retains Platform identity | LIB-10,11,12,15 |
| Co-located Core independence | Start an **inert approved test Core worker only** on D-HUB, observe independent process/storage/identity; kill/restart Core without interrupting Hub; stop/restart Hub without altering Core identity, generation or canonical writer; invalid mount and disk/memory pressure fail closed | LIB-02,03,10,12,15 |
| Read-only replica experiment | **After** sender test, separately enroll W-PEER in test-only READ_REPLICA role; verify signed snapshot/index, exact immutable digest, revision/lag and no catalog writes; test epoch replay, split-brain, fake primary, revoked member. An owner-approved **test** manual promotion requires independent proof old primary was fenced, raises epoch and makes old primary refuse writes on return. Restore `1 PRIMARY/0 REPLICA` baseline. No auto failover | LIB-08,13,14,16 |
| Backup/recovery | Back up independently verified immutable CAS, scrubbed signed index/snapshots, pins and current encrypted trust/revocation metadata to **another physical fault domain**, not only another volume on Artemis. Test digest/recoverability and restore onto fresh disposable Platform with **new Platform identity**, approved namespace recovery, old-primary fencing, no imported Core private state | LIB-10,12,15,16 |
| Operator parity | Native Windows GUI and Windows/Debian TUI/CLI consume same A service and show precise source, signer, library role/replica/epoch, cache vs verified vs installed vs active, signed job receipts, offline/unknown, backup status; exact revision fencing, `NO_COLOR`/ASCII/JSON and no hidden Internet | LIB-14,15,16 |

**No fake progress:** `100% bytes received` remains `VERIFYING` until full hash/signature and current trust pass. Hash alone is integrity, not publisher authentication; Hub TLS alone is transport identity, not publisher provenance. Separate approval for acquisition, verification, staging, native OS install and synthetic activation, with STOP/revocation rechecked at transition. Uncertain service mutation is `OUTCOME_UNKNOWN`, not blind retry.

## 4. Evidence custody and independent source / recipient proof

Capture source SHA (40 lowercase hex), resulting integration tree/commit, real OS build/ABI, immutable signed release manifest and independently recomputed raw bytes SHA256, publisher key ID/fingerprint and separately provisioned trusted root, exact signature verification mode/revocation/anti-rollback, native installed service binary SHA, file inventory *absence of Core and Ollama*, Platform identity/key fingerprints, all actual boot IDs/generations, true Hub logical Library ID, primary membership/epoch/revision and independent source/recipient observations.

For each positive transfer save **separate source & recipient receipts**, approved exact digest/size/license/OS/SDK dependency plan, independently recomputed content hash/chunk parent hash, current SAFE enrollment, target scope and observed verified byte count. For every denied security case save refusal status and the negative **no new source access / no recipient import / no installed service effect** witness. Keep the original log secured on the disposable runner and publish scrubbed bounded receipts; redact owner secrets, Core state, private identity, raw journals, URLs with tokens, signer private keys and authentication material.

For backup capture source catalog signed revision, protected pin graph, external physical storage witness and independently recomputed restored digests. A same-Artemis backup tests a recovery *mechanism*, not the fault-domain guarantee. Storage unmount or unknown quota must not silently recreate an empty Library on root or consume Core memory/disk without quota review.

**Artifact bundles (only after tests genuinely execute):** `release-evidence/ag-d028/<integrated-source-sha>/{manifest.json,host-inventory.json,signed-artifacts.json,cross-host-receipts.json,LIB-01.json..LIB-16.json,limitations.md}`. No such installed-host receipt bundle has been created or verified by this plan.

## 5. Non-substitutable blockers and release decision

Team E preserves legacy [38-row evidence](PLATFORM_1_0_TEAM_E_EVIDENCE_2026-11-08.md) separately from [16-case LIB ledger](PLATFORM_1_0_TEAM_E_AG_D028_LIB_LEDGER_2026-11-08.md). No whole row or LIB case becomes PASS from a design spec, ZIP checksum alone, demo signer, in-process SDK plan, QEMU *development harness*, synthetic worker or host whose installer is not the signed final native release. An independently verified actual installed signed release across four hosts, source and sink, current trust root, owner SAFE/STOP and all negative tests is required. Missing records produce **BLOCKED/NOT TESTED** and a precise failed dependency.

**Coordinator decision E-003: Platform 1.0 GO remains NO.** No production download, Sofía VM mutation, native privileged installation, Hub listener, personal Core activation, branch merge or `main` change.


## E-004 | Executable source-only evidence intake, not a fake installed-host test

E-004 extends **Team E's existing** `tools/aegis_platform_row_preflight.py`; it does not add another installer, package signer, trusted network listener, Core database writer or acceptance authority. The independent cross-OS [D028 evidence-intake CI](../../.github/workflows/aegis-d028-four-host-preflight.yml) executes source-level negative tests on Windows and Linux and emits a **PLAN ONLY** artifact named with the exact checkout SHA.

From an isolated checked-out repository (runner Python allowed; the final *installation targets* must remain Python-free for offline bootstrap):

```bash
# Validate immutable test plan and display exact-source 38 + LIB-16 blockers.
python -m tools.aegis_platform_row_preflight --include-artifact-library --d028-four-host --output d028-four-host-preflight.json

# AFTER genuine signed-host test runs, inspect externally obtained receipts.
# If metadata is incomplete/tampered return 2; if metadata complete but still
# self-reported/untrusted return 3. NEVER returns 0 for a supplied evidence dir.
python -m tools.aegis_platform_row_preflight --include-artifact-library --d028-four-host --d028-evidence-dir release-evidence/ag-d028/REVIEWED_EXACT_SOURCE_SHA --output d028-host-intake.json
```

**Deliberately limited behavior:** this preflight does **not** provision VMs, start services, enroll owner peers, operate Windows SCM or systemd, verify B's publisher signature/root, sign receipts, grant SAFE, test an actual receiver or claim acceptance. Its first command returns 0 for a structurally valid **not-executed** plan. The second command returns **2** for missing, invalid or stale source-bound receipt metadata and **3** for a complete bundle requiring independent trust/signature/OS witness review. Both codes are nonzero in GitHub CI. A `PASS` string or `signature_valid=true` inside submitted JSON cannot make any LIB case or #201 row PASS.

**Provisional evidence intake directory (NOT Team A/B wire schema):**

```text
release-evidence/ag-d028/<40-hex reviewed combined source>/
  release-manifest.json
  host-inventory.json
  signed-artifacts.json
  cross-host-receipts.json
  network-denials.json
  backup-restore.json
  LIB-01.json
  ...
  LIB-16.json
  artifacts/                          # Actual signed release bytes, if available
```

Each submitted top-level or case JSON includes `"source_sha": "<exact 40-hex combined release commit>"`; each LIB JSON also includes its `"scenario_id"`. `signed-artifacts.json` may include a list `"artifacts": [{"path": "artifacts/relative-file", "sha256": "<64-hex>"}]`. The QA runner **streams and independently recomputes SHA256 on actual bytes** only inside the isolated `artifacts/` subdirectory, forbids absolute paths/traversal/backslashes/symlink chains and refuses any single input blob larger than 512 MiB. Metadata files are limited to 64 KiB. A synthetic payload larger than 512 MiB must use individually bounded chunks and a separately verified parent manifest; the intake does not claim that complete streaming transfer was executed. Digest verification is **HASH_MATCH_ONLY**, not publisher authentication. Release signature, trusted root/revocation, native service origin, actual enrolled host identity and signed index must be verified later with Team B/A's canonical frozen format and independently witnessed OS-level observations.

**Security negative CI:** deliberately forged `release_accepted`, second primary, alternate Hub owner authority, WAN/production LAN use, unexecuted phase marked PASSED, wrong source SHA, tampered bytes, symlinked metadata, wrong-case receipt and self-asserted `PASS` are all rejected or kept `NOT_CLAIMED`. Tests assert the incomplete bundle cannot return successful CI exit and that even a complete fabricated metadata bundle returns exit **3**, never PASS.

**Execution blocker:** A/C signed canonical strict Rust/Python management and D028 contract, B native signed *self-contained* Platform-only Windows/Debian12 installer and independent trust roots, plus D signer/SDK catalog/recipient semantics and CI still need exact-SHA approval. No source-level or plan-only test can manufacture missing installed-host evidence. Final release workflow requires the separate **real disposable four-host** test exercise and reviewer decisions. No synthetic progress receipts should be produced to hide a missing OS installer.
