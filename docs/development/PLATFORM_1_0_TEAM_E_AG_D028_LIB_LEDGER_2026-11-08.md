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
