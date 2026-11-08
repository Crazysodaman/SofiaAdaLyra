# Team E E-006 | IG-001 isolated source assembly and execution runbook

**Classification:** reproducible *unassembled* source manifest. **IG-001 functional execution: NOT YET OBSERVED**. **No authenticated live `platform.status` receipt.** Not a signed-release installation, platform GO, or license to merge. See the machine-readable [exact SHA manifest](PLATFORM_1_0_TEAM_E_IG001_REPRODUCIBLE_SOURCE_MANIFEST_2026-11-08.json). These files live on independent draft [#245](https://github.com/Crazysodaman/SofiaAdaLyra/pull/245). Original Platform 38-row acceptance remains **7 FAIL, 31 NOT TESTED, 0 PASS**; LIB-01..16 remain **NOT TESTED, 0 certified**.

## 1. Development-first status and tooling boundary

The available author's local runtime on 2026-11-08 is **Debian GNU/Linux 13.3 (trixie), Python 3.13.5, pytest 9.0.2, git available**. There is **no Cargo/Rust compiler, no QEMU Debian12 VM, no Windows/SCM, no checked-out source tree and no direct GitHub clone DNS** in this runtime. Team E therefore **did not** execute a fresh Debian 12 Platform install or a live authenticated `platform.status`; all such IG-001 acceptance cells remain `NOT_EXECUTED` or `BLOCKED`. Dev-first policy permits source inspection, local archive cryptographic integrity and targeted unit tests without waiting for GitHub Actions; it does **not** permit inventing native execution.

**Actual independent local test:** `python /mnt/data/ig001_artifact_audit.py --output /mnt/data/ig001_archive_audit_results.json` then `python -m pytest -q /mnt/data/test_ig001_artifact_audit.py --disable-warnings --maxfail=1` completed **7 passed in 0.09 seconds** against the four real previously downloaded workflow ZIP files. The independent local test checks exact file bytes and SHA256, ZIP CRC, recorded source SHA, compiler-binary digest, first-ready vs post-kill systemd state and successful two-boot receipts; it rejects modified ZIP, forged receipt `release_accepted=true` and false readiness classification. This proves **artifact custody/test-history classification only**, not a new installed-host test, independently trusted publisher signing root or actual service status.

## 2. Reproducible source selection and conflict resolution

**Fixed baseline:** `668e403d91b98a9cc467c6fc2caa554063aedeb9` on `main` at manifest authoring. **Team E parent head:** `b4c864202e65482a2a49f06109b277b640e37c4f`; creating this manifest creates a newer *E documentation commit only*, not an integrated Platform code tree.

The [JSON source manifest](PLATFORM_1_0_TEAM_E_IG001_REPRODUCIBLE_SOURCE_MANIFEST_2026-11-08.json) pins A #241, B #244, C #243, D #251/#247, D diagnostic #249/#255, E #245, and AG-D028 design #248, including PR-specific bases and derived conflict decisions. All nine are `integrated=false`. Do not infer that an arbitrary old green PR is in the assembled candidate or that a PR head implies its parent is already in the candidate.

**Disposable integration checkout recipe, when a full fetch and appropriate toolchain are available:**

```bash
# Only a new disposable, nonproduction full repository checkout.
git fetch origin main
git fetch origin pull/241/head:refs/ig001/source-a
git fetch origin pull/244/head:refs/ig001/source-b
git fetch origin pull/243/head:refs/ig001/source-c
git fetch origin pull/251/head:refs/ig001/source-d
git fetch origin pull/247/head:refs/ig001/source-worker
git fetch origin pull/245/head:refs/ig001/source-e
git fetch origin pull/249/head:refs/ig001/source-recovery

# Hard fail if any fetched ref differs from the pinned JSON full SHA.
git rev-parse refs/ig001/source-a
git rev-parse refs/ig001/source-b
git rev-parse refs/ig001/source-c
git rev-parse refs/ig001/source-d
git rev-parse refs/ig001/source-worker
git rev-parse refs/ig001/source-e
git rev-parse refs/ig001/source-recovery

# Create an isolated development-only local branch; NOT main.
git switch --detach 668e403d91b98a9cc467c6fc2caa554063aedeb9
git switch -c chatgpt/team-e-ig001-platform-disposable-20261108
```

**Do not automatically merge PRs or run the patch commands unreviewed.** Use a verified, path-scoped `git diff <PR base SHA> <PR head SHA> --binary` (A includes ancestry #235, whose current base is `fddc4ae78c61b3a1227920a667b6aa60cf8f5389`). Stage only the reviewed A then B then C then D then E *diffs* in the disposable integration checkout; for every candidate use `git apply --check` and `git apply --3way` with explicit conflict inspection. Do not cherry-pick historical ancestor commits wholesale, which could reintroduce unwanted second writers, signer code or stale security logic. Record the exact resulting local combined commit and all file blob resolutions in the manifest **before** any protected operation. The baseline main SHA may require a reviewed ancestry reconciliation because A's stacked lineage is not the latest main.

**Known conflicts requiring human-visible resolutions:**

- `.github/workflows/aegis-debian12-vm.yml`: A #241 already checks out exact PR head; E #245 corrects artifact **name** to use that exact SHA. Keep both in final workflow. Verify `inputs.json` source SHA and the actual uploaded ZIP filename, not a synthetic merge SHA.
- `rust/crates/sofia-platform-lifecycle/src/bin/platform_service.rs`: A #241 already contains 12s first handshake and 5s later health **plus other canonical service and management changes**. Never wholesale apply #249 or #255's older Rust service over A. A current blob `3b5ab81a3334f6eac7e61e0868972635d29716b5`, #249 diagnostic blob `60ade556c4e77e68b1bcd9ff7d719673224281f3`. Review only narrow observed semantics.
- `test/fixtures/aegis_debian_vm/probe.py`: #249 and #255 share blob `a3c59eb3ea101ce006f15161d1a664be07337e63`. Add bounded allowlisted diagnostics *once*, preserving 45s deadline and two-boot/SIGKILL/duplicate checks. #255 is a separate #242-based FIRST-READY experiment, not an integration ingredient.
- `test/conftest.py`: D #251, #236 and #239 overlap package ownership. Preserve explicit markers and `test/test_package_grouping.py` unchanged. D #246 Portainer changes are a separate later release negative audit, not IG-001's platform.status prerequisite.
- A #241 already stacks on #235's single Unix SO_PEERCRED intake. Do not apply #235 twice. A's `safe/permissions.py` must remain the **only** SAFE/STOP authority even if D module drafts are later added.

## 3. Minimal executable IG-001 acceptance sequence

The following requires **one combined exact-SHA candidate**, an isolated disposable Debian 12 host, and an independently verified signed stock-OS Core-free installer. The current Team B candidate still explicitly reports unsigned delivery wrappers and disabled native mutations; **these entry conditions are not satisfied**.

| Gate | Actual evidence required | Current state |
| --- | --- | --- |
| IG0 | Exact combined SHA, source provenance, conflicts resolved, all `git diff --check`, no private Core | **NOT ASSEMBLED** |
| IG1 | Python negative tests for IPC/SID/UID, SAFE/STOP, C1/typed denials, source paths and package grouping; actual per-test counts | **NOT EXECUTED** |
| IG2 | Cargo fmt + Clippy + Rust workspace tests on same source | **NO RUST TOOLCHAIN / NOT EXECUTED** |
| IG3 | B's independent publisher root verifies *every executable/runtime/launcher*, complete signed manifest and offline seed, no Python/Git/Cargo/model | **B SIGNED NATIVE BOUNDARY NOT READY** |
| IG4 | Native systemd installation on **Debian 12**, actual service READY, observed PID/boot/platform identity, service journal and whole-source SHA | **NOT EXECUTED** |
| IG5 | An independently enrolled **second OS operator** obtains actual A-owned `platform.status` through native CLI/TUI, same generation/freshness and service origin | **A/C ENROLLED CONTRACT HOLD; NOT EXECUTED** |
| IG6 | Unknown/revoked caller denied before private bytes; STOP/mid-request revocation; stale generation/secret rotation fail closed | **NOT EXECUTED ON INTEGRATED HOST** |
| IG7 | Service SIGKILL/restart and two boots, exactly one canonical writer, no duplicate identity adoption, 12s initial / 5s steady / 45s test bound | **NOT EXECUTED ON INTEGRATED HOST** |
| IG8 | All exact-SHA milestone GitHub workflows executed and independently reviewed; signed logs/host receipts attached | **NOT TRIGGERED FOR ANY COMBINED HEAD** |

Reference test commands, **only after** a checked-out compatible source and OS are present:

```bash
python -m pytest -q test/test_run_management_unix_listener.py \
  test/test_platform_service_management_ipc.py \
  test/test_run_management_read_dispatch.py \
  test/test_ui_platform_management_response.py \
  test/test_ops_platform_row_preflight.py \
  test/test_package_grouping.py

cargo fmt --all --check
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo test --workspace --locked

python -m pytest -q -rs test/test_rust_platform_systemd.py

# Real native Debian12 disposable runner; observe the checked-out version's
# CLI options first. The existing CI workflow pins --checkout and --output-dir.
python -m tools.aegis_debian_vm --help
```

The first actual `platform.status` acceptance transcript must show `source SHA`, `authenticated OS principal`, `current SAFE grant`, `service Platform ID`, `RUN generation`, `request ID`, `observed at`, `status`, `STOP/revoked/stale` mappings, `CLI/TUI query result`, and **actual service log/OS origin**. An `OfflineReader` snapshot, read-only fake mock, exported JSON, or green source parser is explicitly **NOT** that receipt. Cross-host owner secrets or private Core state must be excluded.

## 4. Prior actual Debian12 history, not integrated candidate acceptance

| PR | GitHub run | Outcome and independently rehashed ZIP SHA256 |
| --- | --- | --- |
| #240 `8f0a9f9a...` | 42491156343 | FIRST-READY FAIL, `457261ee840247d2ae15f877fe6cdb24e19f813c89b58c1215a964082c6b2a1c` |
| #242 `43404546...` | 42491245336 | FIRST-READY FAIL, `0e4af3e06c64a2206fe68171eaaea1c9c7c044398fd5c5f64cc0cfa4a97293f3` |
| #236 `33f7ba02...` | 42486942521 | POST-KILL FAIL, `cbc4b48e1d1602c042c91e9aad4293bf6615fc13dc4b30384dcd822372872bc1` |
| #249 `1ee89b8c...` | 42490998718 | Two-boot disposable VM PASS, `343582b49848ce0f597915dc9f80aeb5d1ea693bb64d9008b2895554f6720bc3` |

Independent QA local archive audit revalidated source SHA, ZIP hash, CRC, failure phase, compiled service binary and two boot receipts. The three failing sources use the *same* compiled supervisor binary SHA256 `bb7331bf8d15c268bbdecda10086e7069fce709cfdc90e29c94be2b69b039c9a`; #249 has modified compiled source `038b6735ad4a3eabb177a49a0fecfe349657326cccd29dc7d1870bf686333679`. #255 controlled first-ready experiment still lacks executed native VM/receipt. **12/5s response timeout sensitivity remains a hypothesis, not a proven cause.**

## 5. Keep later four-host release work separate

After actual IG-001 functional Debian milestone and fully reviewed exact-SHA CI, the *later* Platform 1.0 certification extends to signed Windows SCM and Debian native update/repair/rollback/uninstall; signed one-primary Hub with zero replicas on a **disposable** D-HUB guest; enrolled W-PEER and independent D-CLIENT recipient, bounded transfers, publisher trust/revocation, STOP, quotas, pins, off-physical-domain backup, GUI/TUI and private-state/writer isolation. The real owner-intended Sofía VM primary remains *completely excluded* from these tests. No source-only green promotes the separate 38-row or LIB-16 matrices.

**Coordinator GO: NO.** Never merge this IG-001 candidate into `main`, start a production Hub, migrate the live Core, download personal model weights, grant unattended SAFE or elevate any acceptance row without the specific signed installed-host proof.
