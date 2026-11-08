# Team E | AG-D028 mandatory Artifact Library acceptance ledger

**Status: INDEPENDENT QA PLAN ONLY · 0/16 LIB certified · 0/38 existing release rows PASS · GO = NO.**

**Source:** [draft PR #248](https://github.com/Crazysodaman/SofiaAdaLyra/pull/248) at exact design SHA `2e6d2ccafa7daff32a60f3030800f41a05a81046`; [AG-D028 issue #250](https://github.com/Crazysodaman/SofiaAdaLyra/issues/250); [canonical LIB QA runbook](https://github.com/Crazysodaman/SofiaAdaLyra/blob/2e6d2ccafa7daff32a60f3030800f41a05a81046/docs/roadmaps/AG_D028_ARTIFACT_LIBRARY_QA_RUNBOOK.md); [original 38-row ledger](PLATFORM_1_0_TEAM_E_EVIDENCE_2026-11-08.md); [isolated integration plan](PLATFORM_1_0_TEAM_E_COMBINED_INTEGRATION_PLAN_2026-11-08.md).

This document is a **crosswalk and evidence collection plan**, not a 39th acceptance row and not permission to merge, run personal Core, sign/publish production artifacts, start a Hub on a real server or move protected Core data. Team E owns **D028-07**, and independently signs off the failure/permission/receipt requirements for **D028-00**. Other batches have source owners; QA cannot substitute for those implementations. No signed installed-host Artifact Library receipt exists at this checkpoint.

## 1. Canonical required LIB-01 through LIB-16

Each entry has independent status **NOT TESTED** for the *complete signed installed-host scenario*, even where underlying unit/process or disposable VM checks happen to pass. A failed mandatory denial remains a release blocker. **All listed #201 references refine existing rows; none promotes their states.**

| ID | Assigned D028 dependency | Disposable host(s) | Installed-host demonstration required | Negative / fail-closed proof | Existing #201 rows | Case status |
| --- | --- | --- | --- | --- | --- | --- |
| LIB-01 | D028-01 | `W-EMPTY` | Signed offline Windows SCM; SDK+Platform only, no Core/Ollama/Git/Python | Wrong signer/ABI; interrupted/nonadmin installer | 01,02,03,05,28,30,38 | **NOT TESTED** |
| LIB-02 | D028-01 | `D-HUB` | Signed offline Debian12 systemd + reboot, no Core; SSH monochrome | Sudo/path spoof; no implicit download; missing authorization | 01,02,03,07,28,30,33,38 | **NOT TESTED** |
| LIB-03 | D028-03 | `D-HUB`, `D-CLIENT` | Opt-in Core-free Hub; signed index+exact byte fetch over enrolled WAN-off LAN | Unknown client; public listener; expired grant; tampered catalog | 10–14,19,29,31 | **NOT TESTED** |
| LIB-04 | D028-02 | `D-CLIENT` | Select/stage synthetic Core A only; B absent; no auto activation | Implicit prefetch; private identity copy; wrong lineage | 02,03,21,22,24,28,35 | **NOT TESTED** |
| LIB-05 | D028-02 | `D-CLIENT`, `W-PEER` | Distinct synthetic Cores with separate approval and single-writer lineage fencing | Duplicate acting identity; forged display name; stale generation | 21–24,26,35 | **NOT TESTED** |
| LIB-06 | D028-02 | `D-CLIENT` | Single module then two-module pinned dependency group; unselected absent | Wrong/missing/circular dependency; bad SDK/OS; partial group | 17,18,25,28,36 | **NOT TESTED** |
| LIB-07 | D028-04 | `W-PEER`, `D-CLIENT` | Hub/WAN down; enrolled exact digest peer transfer; recipient verifies signer | Source swap; digest mismatch; implicit install | 10–14,17–19,29,31,36 | **NOT TESTED** |
| LIB-08 | D028-00,D028-03,D028-04 | `D-HUB`, `D-CLIENT`, `W-PEER` | Host-bound trust, current SAFE/STOP/revocation across Hub and peer requests | Unknown/revoked/spoofed peer; leaked tokens, state or owner secret | 10–14,21,31,37 | **NOT TESTED** |
| LIB-09 | D028-02,D028-04 | `W-EMPTY`, `D-CLIENT` | Independent exact publisher signature/trust/ABI/license validation on all sources | Tamper; revoked signer; stale index; traversal/zip-bomb; TLS-only trust | 17–19,21,25,28,29 | **NOT TESTED** |
| LIB-10 | D028-04,D028-05 | `D-HUB`, `D-CLIENT` | Bounded interrupted chunk transfer, replay-safe resume, true progress | Disk full; wrong chunk; replay; concurrent writer; pinned GC | 08,09,19,20,26,29 | **NOT TESTED** |
| LIB-11 | D028-05 | `D-HUB`, `D-CLIENT` | Synthetic signed >512 MiB logical payload with bounded chunks/memory | Corrupt parent/chunk; wrong order; forbidden redistribution | 19,25,28,29 | **NOT TESTED** |
| LIB-12 | D028-01,D028-05 | `W-EMPTY`, `D-HUB`, `D-CLIENT` | Active/staged/rollback pins preserved; governed GC + reinstall identity | Delete pinned blob; unsafe purge; stale plan | 19,20,26,29,37 | **NOT TESTED** |
| LIB-13 | D028-00,D028-04,D028-05 | `W-EMPTY`, `D-HUB`, `D-CLIENT` | Recheck STOP/revocation at plan/transfer/verify/install/activate | Mid-stream revocation; secret leak; blind effect replay | 10–12,19,22,29,37 | **NOT TESTED** |
| LIB-14 | D028-06 | `W-EMPTY`, `W-PEER`, `D-CLIENT` | Windows GUI and CLI; Win/Debian TUI; consistent authoritative cache/install/active | Forged UI approval; stale revision; ANSI in NO_COLOR; fake progress | 30–38 | **NOT TESTED** |
| LIB-15 | D028-01,D028-05 | `W-EMPTY`, `D-HUB`, `D-CLIENT` | WAN/LAN down after install; local service/approved cached rollback/reinstall | Silent Internet fallback; offline unknown shown as healthy | 01,05,08,16,19,20,29,30 | **NOT TESTED** |
| LIB-16 | D028-07 | `W-EMPTY`, `D-HUB`, `D-CLIENT`, `W-PEER` | Independent operator runbook, consented Hub/enroll/transfer/cache/reinstall | Unattended activation; unreviewed signer; missing negative receipts | 29,30,32–38 | **NOT TESTED** |

**Counts:** LIB scenarios 16, statuses NOT TESTED 16, accepted 0. Existing canonical #201 states remain **7 FAIL / 31 NOT TESTED / 0 PASS** at the referenced baseline. These counts are not cumulative across the two matrices: LIB cases must be witnessed *within* original rows as additional criteria.

## 2. Required independent four-host topology

| Role | Exact fixture purpose | Release proof |
| --- | --- | --- |
| `W-EMPTY` | Fresh supported Windows 11/Server, no Python/Cargo/Git/Core or model; native SCM and optional WinForms GUI | Trusted offline signed Platform-only installer, independent UUID, nonadoption, reboot/reinstall |
| `D-HUB` | Fresh Debian12 systemd; **owner-enabled** LAN Hub with WAN unavailable | Core-free service, owner-enrolled Hub role, independently verifiable current signed catalog/ACL, no public listener |
| `D-CLIENT` | Second fresh Debian12 headless TUI/CLI client with no WAN | Signed seed, exact verified cache/acquisition, bounded chunks, independent recipient verifier |
| `W-PEER` | Independently signed and enrolled Windows disposable package peer | Current host-bound authentication, restricted offer/transfer, revoked/STOP denial and no private Core state |

These are names for test machines, **not** DNS identities or auth grants. Exact OS version, ABI, service binary path/hash, UUID, public-key fingerprint, trusted signer ID, boot IDs, network firewall evidence and test-run SHA must be recorded for each applicable scenario. Use **synthetic inert** Core definitions, two harmless signed modules and a synthetic large chunk set; no real model weights, private user data, Portainer production endpoints or owner 256-bit secret.

## 3. Release artifact and security evidence contract

For **each** LIB case, record one independently reviewable, secret-free receipt with at least:

- `scenario_id` exactly `LIB-01` through `LIB-16`; canonical 38-row references; `status=NOT_TESTED/BLOCKED/FAIL/PASS` is a **reviewer decision only**, never inferred from CI.
- `source_sha` full 40 hex of the **same integrated release**, all source PR SHA parents, exact CI run/job/JUnit testcase IDs and target OS/ABI/SDK/management protocol.
- `release_manifest_sha256`, `signed_payload_sha256`, independent trusted publisher signer fingerprint/trust root, current revocation/trust floor; distinguish lab test signer from production root.
- `platform_uuid`, current enrolled peer principal/audience, session/generation, service installation identity/origin, process/boot IDs and OS timestamps on each witness host.
- `catalog_generation`, immutable `artifact_id/kind/version/revision`, exact `manifest/content_digest`, size, license/data class, dependency graph and platform target.
- Source selection/written allowlist; exact Hub or peer authenticated endpoint; no unwanted Internet connections; source and target digest independently recomputed; chunk index/offset/limit and partial/restart bytes observed from the wire, not guessed.
- Separate **acquisition**, **verification**, **governed installation**, **activation** and **pin/GC** approval/receipt references. None of these permissions implies the others. Preserve `OUTCOME_UNKNOWN` when effects cannot be proven.
- Negative evidence for unknown/expired/revoked peer, STOP before/during operation, spoofed sender, wrong signer/OS/ABI/license, forged index, stale generation, attack archives, missing chunk, over quota, pinned rollback GC, second writer and secret/private-state transfer attempts.
- Independent Team E reviewer, time, observed result and limitations. Include source host and recipient receipts, binary inventory, local Platform state/absence checks and redacted network deny observations.
  
**No authorized source?** `OFFLINE`/`UNAVAILABLE` not silent Internet fallback. **Bytes downloaded?** Not installed/active. **Hash matches?** Not publisher authenticity. **Valid test-signature?** Not owner-granted execution. **Client says healthy?** Not service proof. **Incomplete/revoked/uncertain transfer?** Never retry execution blindly.

## 4. Contract and package gate before an integrated QA branch

**D028-00 (Team A lead, B/C/D/E signoff) is P0**: freeze one authenticated versioned A Platform service / Rust-Python SDK protocol and agreed library extension for bounded catalogs, inventory, source/transfer plans, acquire/cancel/status, verify, install plan/execute, pin/GC and Hub/peer offers. The operation names in PR #248 are **illustrative until formal A authority signs**. Correlation/sequence, generation, expected revision, time/nonce, strict unknown-field rejection and protocol negotiation must align with Team C's UI/TUI and Team B's single installer.

**No duplicate authority boundary**: A owns enrollment, SAFE/STOP and peers. B owns the **single AG-D011 signed** Windows SCM / Debian12 systemd native install executor, signer verification, OS service ownership, cache path permissions and approved rollback. C is a read-only consumer and governed action surface, never an owner grant. D owns signed Core/module SDK metadata, lifecycle and worker isolation. **Hub is a catalog/byte server, not a signer, owner permission engine or second writable Core memory database**. Peer and Hub token/signer roots are not granted merely by sharing LAN, a SHA or a TLS cert.

**D028-01 through D028-06 ownership:** 01 B (offline Core-free Windows/Debian installs); 02 A+B+D (signed catalog/dependency/source state); 03 A+B (explicit Hub role); 04 A+B+D (enrolled peer chunk transfer); 05 B+D (quota/GC/rollback and synthetic >512 MiB data); 06 C (API-backed GUI/TUI/CLI). Team E's D028-07 observes all with independent artifacts.

**Blocked prerequisite:** The combined exact-SHA QA branch from E-002 remains **NOT CREATED**. Create exactly one isolated combined integration test ref only *after* joint A/C contract signoff, B signed self-contained Platform-only installer boundary, D signed dependency/negative contracts and source ancestry review; never merge to `main`.

## 5. Runner implementation and acceptance safety

The preexisting `tools/aegis_platform_row_preflight.py` is the **only** E component preflight inventory; Team E extends it with an **opt-in** `--include-artifact-library` switch. The default output still contains exactly 38 canonical rows unchanged. Opt-in output adds 16 explicit `BLOCKED_NO_SIGNED_INSTALLED_HOST_EVIDENCE` cases with `acceptance=NOT_CLAIMED`, `production_authorized=false`, and an exact crosswalk to original rows. Its tests deliberately prove that an all-green component JUnit can never set LIB acceptance PASS. This is an inventory, not a fabricated installed-host observation. CI must run at each **new exact PR head**; until complete, report PENDING, not PASS.

Final independent **D028-07** run executes LIB-01–16 on installed signed hosts **plus all unrelated original 38 requirements**, including untouched preexisting blockers such as forced-kill recovery, versioned OS-authenticated IPC, signed lifecycle, operator runbook and Portainer negative redaction. A single red mandatory security negative or missing signer/installed-host proof keeps **GO=NO**.


## E-003 | Single-primary and independently installed-host gate

**Updated design review pin:** [PR #248](https://github.com/Crazysodaman/SofiaAdaLyra/pull/248) at `8d5c7ae58fde4a51a3beb3d0d73ad956c0a80f21` adds the [owner's one-primary Sofía VM deployment requirement](https://github.com/Crazysodaman/SofiaAdaLyra/blob/8d5c7ae58fde4a51a3beb3d0d73ad956c0a80f21/docs/roadmaps/AG_D028_SOFIA_VM_PRIMARY_LIBRARY_DEPLOYMENT.md). This extends **existing** LIB scenarios: no LIB-17 and no #201 row 39. The earlier design pin above documents the original source work only; exact integrated source must be refrozen before any host test.

**Team E disposable four-host plan:** [E-003 execution and evidence protocol](PLATFORM_1_0_TEAM_E_D028_DISPOSABLE_TOPOLOGY_2026-11-08.md), machine-readable *inert* fixture `test/fixtures/aegis_d028/qa_four_host_topology.json`. Exactly one logical Library with D-HUB as the **sole initial PRIMARY**, **zero initial READ_REPLICA**, W-EMPTY + W-PEER Windows and D-CLIENT Debian12; all are *new test-only identities*, never actual Sofía VM endpoints. A later separate approval can temporarily re-role W-PEER as a read-only test replica to witness lag, signed catalog, permission denial and manually fenced primary promotion, restoring the baseline afterward. Live VM deployment remains unauthorized and untested; current actual VM OS/resources/identity are unverified.

| Required extension | Existing case(s) | Mandatory independent host evidence |
| --- | --- | --- |
| Single PRIMARY / 0 replicas, fresh Core-free Hub, independent optional synthetic Core worker | LIB-02,03,15 | Verified separate Platform/Hub/Core IDs and PIDs, signed catalog, Core stop not stopping Hub, Hub stop not corrupting Core, offline-cache truth |
| Core+Hub co-location resource pressure and protected storage | LIB-10,12,15 | Measured RAM/CPU/free/reserved quota, bad mount/pressure refusal, no new fallback root, pinned rollback and no Core writer collision |
| Revoked/fake member, stale primary epoch and split-brain denied | LIB-08,13,14 | Current A SAFE/STOP enrollment and signed logical Library membership, owner-fenced manual promo and old-primary write refusal |
| Read-only replica with authenticated bounded digest replication | LIB-08,14,16 | Separately approved test replica, recipient publisher re-verification, signed source hash, revision/lag, no second mutable catalog signer or authority |
| Off-Hub *physical* fault-domain backup and independent restore | LIB-10,12,15,16 | Signed object/index snapshots, pin/retention/revocation metadata, off-physical fault-domain witness, fresh Platform ID and independently authorized namespace recovery, no private Core state |
| Windows GUI + headless Win/Debian TUI/CLI identity/backup/replica parity | LIB-14,16 | A/C signed management schema, B packaged native client, true 1-primary/0-replica and stale/unknown state, strict NO_COLOR, no client-issued grants |

**Independent historical artifact verification (not LIB acceptance):** Team D draft #249 exact `1ee89b8cf4fdb6c98a1a18ea694a081e5794901b` had 4/4 CI success and actual Debian12 two-boot disposable VM artifact #13621438983. Team E re-downloaded ZIP bytes: `sha256:343582b49848ce0f597915dc9f80aeb5d1ea693bb64d9008b2895554f6720bc3` matching GitHub metadata, CRC valid; two distinct boot IDs, stable Platform ID/manifest, crash recovery and duplicate denials, and both receipts say `production_authorized=false`, `release_accepted=false`. Team D #240 (`8f0a9f9a72bc2ec314ef7cc2b182cdb41f312bb1`) and #242 (`43404546d6c8d012b701f2faf6e22f6e86cdd434`) each had red actual Debian VM *first-ready* tests: failed diagnostic ZIPs #13622651250 (SHA256 `457261ee840247d2ae15f877fe6cdb24e19f813c89b58c1215a964082c6b2a1c`) and #13622621383 (`0e4af3e06c64a2206fe68171eaaea1c9c7c044398fd5c5f64cc0cfa4a97293f3`) passed archive integrity but include no success boot receipts. These cannot promote any LIB case.

**Current source-only #251 exact `1c013e28f4cb26b3a4c4426d04064714bd0e9846`:** implements inert deterministic module closure with exact digest and pinned dependencies but cannot itself authenticate publisher roots, revocation, license, download, install or activation. Its exact-head CI was pending when inspected. It may inform LIB-06 preflight only after Team A/B contracts freeze; **LIB-06 remains NOT TESTED**.

**Release blockers:** A/C immutable management and signed library contract parity + native operator enrollment, B signed self-contained offline Windows/Debian12 install/service and trusted independent roots, D catalog/index/dependency/package/recipient verifier, real current SAFE/STOP/retention/transfer, four actual independent OS host receipts, and original #201 unrelated safety rows. **All 16 LIB statuses above remain NOT TESTED. No production Sofía VM or real Hub action.**

## E-004 | D028-07 evidence intake milestone, not certification

The [same Team E evidence runner](../../tools/aegis_platform_row_preflight.py) accepts `--include-artifact-library --d028-four-host` to emit a **read-only** host plan and 16 source-scoped receipt slots. A separate `--d028-evidence-dir` may check JSON source binding, restricted paths, tampered/symlinked evidence, stream SHA256 of supplied bytes and completeness of **all LIB-01..16**. Any supplied directory returns nonzero exit (2 incomplete/corrupt, 3 review required), even if source JSON self-reports `PASS` or an unsigned Boolean `signature_valid=true`. [Exact-head source-only Windows/Linux job](../../.github/workflows/aegis-d028-four-host-preflight.yml) emits only a **PLAN ONLY** artifact. No direct network/scm/systemd/Hub/peer tests are run by this stage.

The current mandatory four-host test plan remains `W-EMPTY` Windows, `D-HUB` Debian12 **sole initial PRIMARY**, `D-CLIENT` Debian12 independently enrolled recipient and `W-PEER` Windows peer, with no production endpoints and zero initial replicas. Team A/C formal management and Library schema freeze is absent; Team B notes SHA-only offline seed integrity is not independent publisher trust nor its final signed native installer. Team D #251 recipient metadata and #247 worker safety cannot certify a live installed transfer or activation. **16/16 LIB cases remain NOT TESTED; zero certified.** The older [38-row ledger](PLATFORM_1_0_TEAM_E_EVIDENCE_2026-11-08.md) remains **7 FAIL / 31 NOT TESTED / 0 PASS**. No release GO, no production Sofía VM contact or private Core state.
