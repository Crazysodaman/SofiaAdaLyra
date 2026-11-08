# AG-D028 | Independent installed-host QA execution plan

**Status:** Mandatory Platform 1.0 release acceptance *plan*, not passed evidence. This document is a reproducible work order for independent Team E and Teams A/B/C/D. Canonical specification: [AG-D028 Release Spec](AG_D028_PLATFORM_1_0_RELEASE_SPEC.md). Parent matrix: [#201](https://github.com/Crazysodaman/SofiaAdaLyra/issues/201), implementation tracking [#250](https://github.com/Crazysodaman/SofiaAdaLyra/issues/250). Original acceptance rows stay **38**. Every LIB case below is currently **NOT CERTIFIED**.

## Environments, fixtures and independence

**Required disposable topology, no production host effects:**

| Host | OS | Role | Internet | Must prove |
| --- | --- | --- | --- | --- |
| `W-EMPTY` | Windows 11 or supported Windows Server (pin exact build) | Initially empty Core-free Platform client, optional GUI | Denied by firewall/isolation for offline tests | Correct signed installer/SCM, no Core/model/modules, restart and isolated install lifecycle |
| `D-HUB` | Debian 12 (pin minor version/kernel) | Fresh Core-free Platform + owner-activated Hub role | WAN intentionally disconnected, LAN allowed | Native systemd service, independent signer verification, hub index and exact bytes |
| `D-CLIENT` | Debian 12 | A second clean headless Platform client with CLI/TUI | Offline from Internet | Download/verify/stage, no GUI, peer/Hub and remote host trust |
| `W-PEER` | Windows 11/Server | Separate enrolled signed-package source, GUI/TUI client | Offline from Internet | Remote peer transfer to W-EMPTY/D-CLIENT, enrolled/grant-revoked tests |

The host names above are **fixture labels**, not DNS addresses, Aegis trust identities or permission grants. Test actual unique installation UUID/fingerprint and current enrolled trust ID. Destroy or revert disposable machines only after preserving evidence; never run credential-attack tests against user production network.

**Required reviewed synthetic artifacts** (test signer distinct from production trust): signed Core-free Platform+SDK per OS/architecture; synthetic Core Runtime A, Core Runtime B, two distinct Core definitions with identity lineage fixtures, one purpose-built same-identity duplicate negative; signed harmless Module A and B with one pinned dependency; a separate wrong-OS package; trusted-signer and untrusted-signer variants; corrupt package, revoked publisher/cert, stale catalog generation and wrong SDK/ABI; a synthetic signed large-data object whose total manifest size exceeds 512 MiB and is represented by bounded chunks; restricted/non-redistributable license fixture; malicious path/zip-bomb fixture. **Do not** use personal `sofia.db`, personal Core assets, real password/secrets, genuine copyrighted model weights, Portainer production stacks or physical controllers.

**For every case:** capture exact source Git SHA, PR/CI URL, full signed artifact digest and signer trust root ID, OS installed service path/binary and host UUID, SDK/ABI version, plan ID/revision/approval scope, selected source, expected/observed status, timeline and reviewer. A fabricated manifest JSON or a CI runner without a signed installed OS service is not installed-host evidence.

## Mandatory test cases: given → when → then

### LIB-01 | Windows offline Core-free bootstrap

- Given clean W-EMPTY, no project Python/Rust/Git/Ollama, Internet disabled, validated signed offline Windows seed and separately trusted signature root.
- When owner uses interactive PowerShell installer to review target OS/arch/bytes, authorizes exact plan and starts the real Windows native service.
- Then service remains healthy; ONLY neutral Platform+SDK/runtime required bytes installed; no `sofia-core`, optional module, model, GPU requirement, private Sofía database/Constitution/memory. Signature, root trust and installed-wheel isolation independently verified.
- Negative: wrong signer, altered bytes, wrong architecture, nonadmin refusal and installer interruption do not produce an adopted/untrusted active service.

### LIB-02 | Debian offline Core-free bootstrap

- Given clean D-HUB, Internet disabled, signed offline Debian 12 seed, no interpreter/Cargo dependency.
- When owner runs approved Bash bootstrap, explicitly elevates for native systemd operations and selects headless/monochrome mode.
- Then native service runs, starts after host reboot, and all Core-free/no-private-data/diagnostics statements are true; SSH `NO_COLOR` output uses no ANSI.
- Negative: noninteractive missing exact authorization refuses; no untrusted sudo script or redirected executable path.

### LIB-03 | Owner-configured Hub while WAN is off

- Given independent signed Platform on D-HUB and an enrolled D-CLIENT, owner explicitly enables Hub role for a bounded signed fixture class; WAN blocked.
- When D-CLIENT queries catalog generation, source scopes and fetches the exact signed artifact by pinned digest over authenticated LAN.
- Then Hub only serves listed immutable bytes; client locally re-verifies signature/size/manifest/revocation; identical per-target digest, provenance and one download receipt. Hub requires no Core or model running.
- Negative: unknown client, same LAN without enrollment, wrong class, expired owner grant and public listener exposure refused.

### LIB-04 | Select exactly one Core, no auto-activation

- Given D-CLIENT catalog contains two signed synthetic Core packages A/B and neither is locally installed.
- When authorized user selects **A only**, previews closure, downloads/verifies and stages A.
- Then A bytes present and verified, B absent; no personal identity state cloned/downloaded and no running Core until a separately approved activation. Status differentiates catalog/verified/staged/active.
- Negative: Core B never implicitly prefetched; untrusted Core definition or wrong owner lineage rejected.

### LIB-05 | Multiple Cores and same-identity fencing

- Given two independent, signed synthetic Core runtime definitions and an intentionally duplicated same-identity definition.
- When owner chooses A+B with separate approvals and tests independent activation, then tests a second platform claiming the same Core identity.
- Then distinct authorized Cores remain separately scoped; same identity gets at most one canonical acting writer/generation, rejected duplicate cannot activate; no private state transfer from Hub.
- Negative: wrong Core identity under same display name, wrong generation, stale binding and revoked enrollment refused.

### LIB-06 | Single module and reviewed dependency group

- Given two signed harmless modules A/B with dependency B→A, and a third unselected module.
- When owner downloads one then selects B as part of a reviewed multi-select group, installer previews dependency A, total bytes/host rights and staged-only behavior.
- Then exact required A/B downloaded, verified and staged under separate statuses; third module absent, no real effects; partial group failure shows exact per-module receipts and no implicit activation.
- Negative: wrong dependency digest, unavailable dependency, circular dependency or incompatible SDK/OS prevents install.

### LIB-07 | Direct enrolled peer transfer without Hub or Internet

- Given W-PEER has an allowed signed Module A, D-CLIENT is enrolled/authorized to receive it, Hub unavailable and WAN disabled.
- When client requests exact Module A digest and transfer happens over authenticated peer channel.
- Then only Module A bytes move, content matches the signed source digest, recipient verifies independently, and local effect/install requires distinct owner approval.
- Negative: change source after plan, switch bytes or wrong requested digest causes denial/quarantine.

### LIB-08 | Trust and permission negative cases

- Given enrolled, expired, revoked, unknown and spoofed test identities with a shared local LAN.
- When each attempts catalog index, protected package fetch, restricted data offer and install requests while SAFE/STOP policy changes mid-job.
- Then host-bound current permission governs all phases; unauthorized transfers never read protected data or initiate effectful installer. No tokens/owner secrets/private Core files appear in logs, metadata or transmitted bytes.
- Negative: unauthenticated discovery or mDNS-looking name never constitutes peer trust.

### LIB-09 | Package authenticity, compatibility, archive and license

- Given tampered bytes, correct SHA under untrusted key, revoked signer, stale catalog floor, wrong OS/ABI/SDK and path/zip-bomb fixtures.
- When each is imported from hub/peer/offline media (test all relevant sources).
- Then no source can bypass local independent signature/current revocation/compatibility/license/path verification; rejected packages are quarantined and never load/import executable code.
- Negative: server signed TLS certificate alone is never accepted as publisher provenance.

### LIB-10 | Interrupted download, retry, crash, disk pressure and duplicate request

- Given size-bounded chunked signed fixture, quota near limit and induced transport interruption/host process crash.
- When client cancels, pauses, resumes after restart, receives duplicate request ID and attempts finish with missing or corrupted chunk.
- Then progress reflects actual verified bytes, resume uses only previously authorized exact missing chunks, invalid resume token/host/generation fails; data remains nonexecutable until complete verified atomic import; no blind install replay and no duplicate canonical writer.
- Negative: disk-full/transfer-cap rejection never causes emergency deletion of active/rollback-pinned blobs.

### LIB-11 | Bounded large signed-artifact data plane

- Given a **synthetic** manifest declaring a content object larger than the current 512 MiB single-artifact bound, represented by individually bounded signed/chunk-indexed objects.
- When D-CLIENT fetches it, disconnects, resumes and verifies exact final reconstruction hash with measured memory and space.
- Then no bound is weakened, no unbounded in-memory read, no false `model installed` state, and nonredistributable license blocks peer offers. No need to install a real model or execute inference.
- Negative: missing/out-of-order/corrupt chunks and conflicting parent digest prevent VERIFIED state.

### LIB-12 | Cache pins, safe GC, upgrade/reinstall and rollback

- Given installed/staged/rollback-pinned package versions, deduplicated cached blob, unreferenced blob and active transfer.
- When owner reviews quota/GC, attempts to delete each, updates/rolls back and reinstalls Platform from verified local cache.
- Then references remain intact, only eligible unreferenced blobs deleted, package histories/receipts retained, Platform installation identity preserved and no forced Core data purge.
- Negative: unpin or delete active dependency/rollback copy without exact approved plan fails.

### LIB-13 | STOP and authority revocation between every stage

- Given authorized acquisition plan and separately authorized install/activation plan.
- When STOP, target generation change or owner revocation occurs before download, during transfer, after verify, before install and during active installer execution.
- Then acquisition and effects are fenced separately. No revoked actor installs/activates or deletes data. Any uncertain service effect is `OUTCOME_UNKNOWN` with reconciliation rather than a second execution.
- Negative: owner secret never exposed to Core, GUI logs, URLs, cache, report or synthetic fixture.

### LIB-14 | GUI, TUI and CLI management parity

- Given same installed hosts and API version, GUI on W-EMPTY/W-PEER, headless Debian TUI and CLI on D-CLIENT, two simultaneous management clients.
- When sources go offline, transfer starts/stops, Hub disabled, module paused, trust revoked and status event cursor lost/reconnected.
- Then each client shows correct verified/downloaded/staged/active/stale/unknown states, signer and last actual timestamp; correct owner theme, `NO_COLOR`, no ANSI in redirected streams and source/permission parity. No GUI bypasses Platform authorization.
- Negative: stale revision update refused, client closing cannot stop native Platform.

### LIB-15 | Entire ecosystem WAN-off after normal install

- Given several legitimately verified, cached and installed components with LAN disconnected and Hub unreachable.
- When hosts reboot and local CLI examines their state, and owner performs allowed offline reinstall/rollback using pinned trusted bytes.
- Then Core-free Platform remains healthy without Internet, no implicit remote source fallback, local cache/rollback available, and remote cache status shown OFFLINE/STALE rather than MISSING or healthy.
- Negative: unknown remote status never authorizes a cached trust or new publisher key.

### LIB-16 | End-to-end operator runbook

- Given official signed build and user-facing instructions requiring no Git clone or developer toolchain.
- When independent tester follows exact Windows and Debian sequences: install offline, explicitly configure Hub role, enroll client, request one Core, stage module group, transfer from enrolled peer, revoke offer, inspect history/GC, uninstall/reinstall with retained identity.
- Then every claim matches observed service, actual received/staged/installed artifacts, authentic signer/host evidence and GUI/TUI/CLI screens. Installer/menu share Aegis palette with monochrome ASCII fallback; user receives clear failed-state recovery steps.
- Negative: operator can stop safely at every step and nothing is silently activated.

## Owner's first topology: single Hub co-located with Core, replicas later

**Primary deployment plan:** [Sofía VM: one logical Library, exactly one primary and no replicas initially](AG_D028_SOFIA_VM_PRIMARY_LIBRARY_DEPLOYMENT.md). These **extend the existing LIB-01–LIB-16**, not a seventeenth scenario. Use **test-only synthetic Core workers and disposable Platform guests**; neither personal Sofía state nor real owner secrets are test inputs.

| Within scenario | Additional test | Independent expected evidence |
| --- | --- | --- |
| **LIB-02** | VM preflight rejects unsupported guest Debian release/ABI and too-small quota/unmounted library volume before approved install. Check real Core-free Platform startup regardless of a running Core. | Actual observed guest distro/release, signed OS target, disk/memory report, denial receipts and untouched existing service/state |
| **LIB-03** | Configure one logical Library on D-HUB with `PRIMARY` and **zero replicas**; start an independently managed synthetic Core on the same guest, then stop/restart Core while a signed content fetch is active. | Hub keeps same Platform ID, catalog epoch and correct transfer state; Core stop doesn't stop Hub; CAS contains no Core secrets or private identity |
| **LIB-07/14** | Add an **enrolled read-only replica** to the same logical Library in a separate disposable host after all single-Hub tests, then fetch an exact digest from it while primary is healthy; let primary add a new signed artifact without replica updating yet. | Replica reports `LAGGING` and last verified generation; can serve already independently verified exact bytes when currently permitted; cannot overwrite primary catalog |
| **LIB-08/13** | Attempt wrong Library ID, unauthorized/expired replica join, stale epoch, two proposed primary promotions, split-brain network partition and return of previously fenced primary. | Every second-primary/catalog-write attempt is rejected; no false leadership or new package signing authority; service refuses restart of stale promoted writer |
| **LIB-10/12** | Inject quota pressure, unavailable/mis-mounted CAS volume, partial download and Core-owned storage pressure on co-located guest; test external backup snapshot and owner-governed restore to new disposable Platform ID. | No Core DB corruption, no fallback to wrong filesystem, no missing rollback refs, no restore of personal Core state, independent signed index/blob digest proof |
| **LIB-15** | Primary Hub stops or VM is offline while clients retain verified local cache and Core worker has previously installed capabilities. | Clients report `OFFLINE/STALE`; existing Core/Platform use persists if host remains up, no forced Internet fallback or hard dependency on Hub |
| **LIB-16** | Show Setup as `ONE PRIMARY / ZERO REPLICAS`, then separately show enroll read-only replica, inspect its lag, deny promotion without fence and record explicit owner-approved **manual** promotion after fencing the old primary. | Same GUI/TUI/CLI status, verified source/host identities, fresh epoch/cursor, one writer, original owner-managed library namespace retained |

**Initial owner environment is not this test cluster.** One real Library on Sofía VM is the desired future deployment. A second live production replica is not requested today, and multi-primary/automatic failover remain excluded. The optional replica *capability* still needs independent disposable-host negative certification before Platform 1.0 GO as specified by the owner's redundant-ready requirement.

## Evidence ledger template (use for EACH case, no aggregate green shortcut)

```yaml
scenario_id: LIB-XX
status: NOT_TESTED            # PASS / FAIL / BLOCKED / NOT_TESTED
owner_team: E
release_source_sha: null      # full 40 hex, exact installed release
workflow_url: null            # checked exact SHA, not another PR's run
artifact_manifest_sha256: null
artifact_content_sha256: null
publisher_signer_key_id: null
platform_host_ids: []         # actual independently observed host UUID/fingerprint
os_builds: []
sdk_protocol: null
owner_authorization_receipts: []
source_trust_receipts: []
transfer_receipts: []
install_or_runtime_receipts: []
negative_test_receipts: []
witnessed_at: null            # UTC
reviewer: null
observed_result: null
remaining_blockers: []
```

Never mark PASS using synthetic in-process reference Core/Platform demos alone. An independent reviewer must inspect the result's original signed release bytes, current authenticated identity/grants, all required negative cases, and Platform process/OS service origin.

## Deliverable structure (proposed, not present)

```text
release-evidence/
  ag-d028/
    <full-source-sha>/
      manifest.json
      host-inventory.json       # secret-free machine ID, OS and service origin
      LIB-01.json
      ...
      LIB-16.json
      signed-artifacts.json
      cross-host-receipts.json
      limitations.md
```

**Stop conditions:** active or duplicate canonical writers, exposed secret/private data, unauthenticated package execution, forced Internet install, unsigned/revoked package admission, fake healthy service/transfer results, missing installed-host reproducibility, any failed negative security case, or absent independent reviewer. Preserve fail evidence and original 38-row states. **Platform 1.0 GO = NO** until all required checks are independently accepted.
