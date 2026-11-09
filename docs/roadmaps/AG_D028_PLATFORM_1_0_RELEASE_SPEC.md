# AG-D028 | Platform 1.0 release specification: selective installation and Artifact Library

**Owner directive:** 2026-11-08. **REQUIRED BEFORE PLATFORM 1.0 GO.**
**Status:** RELEASE-BLOCKING SPECIFICATION; NOT IMPLEMENTED/CERTIFIED END TO END. `#201` still has **38** acceptance rows; requirements below refine those rows and do **not** invent a 39th. Every applicable row retains its current FAIL/BLOCKED/NOT TESTED status until Team E independently verifies actual released Windows/Debian 12 hosts.
**Owner's initial deployment:** [ONE primary Library on Sofía VM alongside separately governed Sofía Core, future redundant replicas](AG_D028_SOFIA_VM_PRIMARY_LIBRARY_DEPLOYMENT.md). **Release requirement:** support 1 primary/0 replicas and replica-ready SDK/host controls; production second Library not requested.
**Independent test work order:** [LIB-01–LIB-16 QA runbook](AG_D028_ARTIFACT_LIBRARY_QA_RUNBOOK.md). **Implementation tracker:** [#250](https://github.com/Crazysodaman/SofiaAdaLyra/issues/250).
**Design base:** [AG-D028 architecture](AG_D028_AEGIS_FEDERATED_ARTIFACT_LIBRARY.md), [AG-D011 signed Platform-only installer](AG_D011_ASCII_PLATFORM_INSTALLER.md), [AG-D021 signed component catalog](AEGIS_DESIGN_TODO.md), [Platform acceptance](../development/PLATFORM_1_0_ACCEPTANCE.md), [Platform SDK/ABI updates](../sofia2/COMPONENT_UPDATES_AND_UNIFIED_SDK_V1.md).
**Accountable workstreams:** Team A: SAFE/STOP, authenticated management/peer enrollment and revisioned API; Team B: signed Windows/Debian installer, verified artifacts and upgrade/rollback; Team C: same-contract GUI/TUI and operator management; Team D: Core/module SDK, dependency/worker lifecycle and permissions; Team E: independent multi-host and exact-SHA acceptance. Single canonical Platform authority; **no replacement installer, private-state writer, signing root or new release row**.
**No deployment authorization:** This design approves engineering and tests on disposable machines, not real host enrollment, owner-secret use, downloading content to your live server, serving public LAN endpoints, activation of a personal Core, or production migration.

## Binding owner-only use and free/private model-asset acceptance (2026-11-09)

The owner's Platform 1.0 is a **private personal deployment**, with one owner and multiple independently enrolled local hosts, NOT a commercial public artifact CDN, SaaS or model distribution business. [Binding 1.0 acceptance crosswalk](../development/AEGIS_OWNER_ONLY_1_0_GO_LIVE_ACCEPTANCE_2026-11-09.md). Apply this as **required refinements to existing 38 rows and LIB-01–LIB-16**, not new identifiers or acceptance successes. The base Platform, installer, Hub and local/offline clients must require no subscription or external service account. Models and voice packs with licenses permitting only noncommercial personal use can still be locally staged/used in permitted ways; the Hub must separately check whether the contemplated private copy/transfer is allowed, rather than treating personal ownership as blanket redistribution rights. All existing SAFE/STOP, signer/digest, owner approvals, no-public-listener and Core-free boot boundaries remain mandatory.

**Additional binding owner-use GO refinement (2026-11-09):** Platform 1.0 is an **owner-only personal Fleet and Artifact Library**, not a commercial SaaS/marketplace. [POC-P1–POC-P5 owner-only release overlay](../development/AEGIS_OWNER_ONLY_GO_LIVE_ACCEPTANCE_2026-11-09.md) refines existing 38 issue #201 rows and existing LIB-01–16 tests. The signed Core-free offline package cannot require a customer login, billing provider, cloud subscription or publicly accessible Hub; private noncommercial model weights may be locally eligible if their exact terms permit, but no permission for public or peer redistribution is assumed. Verify both permitted local synthetic artifact use and denied prohibited cross-node transfer. Owner-only does **not** weaken SAFE/STOP/host enrollment or signed independent verification. Existing row/scenario counts and test states do not change; real installed-host evidence remains necessary.

## 1. Exact Platform 1.0 scope: full function set, but no installed content by default

Every Platform 1.0 release must support the same governed local component library and client APIs, **even if it has zero Cores and zero modules installed**. It must support becoming an owner-selected library host or requesting packages from one, and independently transferring a distributable signed package between enrolled Platforms.

**Mandatory product functions (ALL required for GO):**

| Requirement | Ship-level behavior | Explicitly outside Platform 1.0 |
| --- | --- | --- |
| Core-free bootstrapping | Signed native service + required neutral SDK/runtime, offline install, no personal Core/modules/models, protected local identity | Personal Sofía Core production launch or its memory migration |
| Selective package acquisition | Catalog/download/reverify/stage one Core, one optional module, or chosen group, with exact dependency/compatibility preview | Automatically downloading every Core or all optional modules |
| Library Hub | Owner-selected Platform/server serves a versioned signed-index view and exact immutable content to enrolled authorized clients, even when WAN is disconnected | Global public anonymous package CDN, package marketplace |
| Peer-assisted transfer | Transfer verified distributable package from one approved Platform to another over authenticated bounded channel; local reverify | Sync all private state, automatic software installation on peers |
| Offline and resilient behavior | Seed with signed media, local verified cache, no surprise Internet fetch, bounded interrupted transfer resume and exact recovery | Unattended network discovery that trusts an unknown endpoint |
| Storage management | Inspect downloaded/installed/active/staged/pinned/rollback/revoked/cache-corrupt, quotas, safe GC, provenance, clear transfer history | Automatically deleting an artifact still needed by rollback or an active worker |
| Governed interfaces | Same authenticated versioned service APIs for headless CLI/TUI and Windows GUI; exact status/denial/STOP/stale/error outcomes | UI or Core independently deciding install/signer/secret trust |
| Capability-safe staging | Acquisition != install != activation; signed verified package with independent owner approvals for actual effects; no second state writer | Live Core or module as a privileged package manager |

**Boundary on models:** Release MUST correctly represent, optionally acquire, and safely cache **approved large signed/chunked data artifacts** (including a synthetic model-size fixture, with license/distributability metadata), but **does not** have to ship an Ollama engine, a real commercial model, or model inference as a prerequisite for Core-free Platform operation. Model Manager separately decides any actual model load and GPU placement.

**Boundary on private data:** Release MUST prevent shared artifact operations from accessing/transferring Core identity, constitutional assets, memory, personal secrets, protected Platform state, module credentials, and local database files without a separate purpose-built encrypted/authorized restore flow. Full private backup/failover is not silently redefined as package mirroring.

## 2. First install, bootstrap and server topology

### Bootstrap chicken-and-egg solution

1. The initial Platform installation MUST work from a fully reviewed **offline seed bundle** supplied by removable media or an explicitly owner-selected local file. Include the proper OS/architecture native binary, neutral SDK, required runtime, independently provisioned trusted publisher roots, signed manifest and all dependency closure.
2. Installer verifies bytes and trust without first needing a running Aegis server or an active Core. Nothing is downloaded implicitly. No Linux system Python, Rust/Cargo, Git, Ollama, GPU or personal Core is required on the clean host.
3. Start a **Core-free Platform** with its own unique local Platform installation identity and protected local state. The service is valid without Internet access, any Hub role, or Fleet enrollment.
4. Only after local setup may the owner choose **Hub role**, **Library Client role**, both, or **Local-only**. Separately enroll/authorize remote peers and sources using the canonical Platform SAFE/STOP authority. Do not automatically trust other hosts because they share a LAN.
5. A Hub bootstraps from the same Core-free Platform release; it can serve signed package artifacts without Core cognition or GPU inference. If hub unavailable, local hosts continue using their verified local caches and retain existing installed components.
6. **Owner's first deployment** uses **one logical library, one primary Hub, zero live replicas**, hosted on the Sofía VM beside its separately governed Sofía Core. Hub role is Platform-owned and works independently of Core lifecycle. Future read-only replicas may join the same logical library on independently enrolled hosts; signed immutable bytes can be mirrored while the mutable primary catalog stays single-writer. No automatic multi-master or unseen primary promotion. See [VM primary + replica profile](AG_D028_SOFIA_VM_PRIMARY_LIBRARY_DEPLOYMENT.md).

### Roles are configured features, not separate mandatory programs

| Role | Minimal authority | Restrictions |
| --- | --- | --- |
| Local-only Platform | Read/verify its own cache, stage and install under local approval | No network listener required for library |
| Library Client | Query owner-selected enrolled hub and peers; download allowed exact packages | Cannot distribute private protected state |
| Artifact Library Hub | Versioned catalog, immutable byte serving, per-peer ACL/quota/audit, pin/GC | Cannot sign new releases as publisher, install remotely or issue owner SAFE authority |
| Enrolled Artifact Peer | Bounded signed package advert/offer/transfer | No cross-host Core identity cloning, no automatic remote activation |
| Authorized Core | View/propose permitted catalog/acquisition/SDK work via authenticated Platform API | May not open arbitrary URLs, create signer trust, bypass review or install on another host |

**Suggested operational placement:** dedicated server's Aegis Platform in Hub+Client mode; ordinary Windows/Debian Platforms in Client mode; developer lab machines may additionally offer reviewed peers. This is a placement preference, not hard-coded naming/host-role trust.

### Platform-only release bundle proof

Team B must prove from an actual generated *installed-host* release that the neutral Platform wheel/runtime/service and SDK install **without** `sofia-core`, optional modules, large model weights, personal Core assets, personal `sofia.db` or unrelated Sofía services. Source `packaging/components.toml` already declares separate `sofia-sdk`, `sofia-platform`, `sofia-core` components; merely passing an import test is insufficient.

## 3. Catalog, inventory and identity model

Every catalog query MUST report at least:

| Field | Type / rule | Meaning |
| --- | --- | --- |
| `artifact_id` | Opaque stable publisher/product ID, bounded and case-normalized | Never a pathname, provider URL or trusted name |
| `kind` | `platform_release / sdk / core_runtime / core_definition / module / model / asset / rollback` | Data class and verifier path; never infer Core identity from release filename |
| `version`, `revision` | Version + monotonically checked signed publisher revision | Prevent stale/downgrade replay; legitimate rollback separately authorized |
| `manifest_digest`, `content_digest`, `size` | Pinned signed manifest and SHA-256 content + exact expected size | Immutable CAS identity, not origin/authentication |
| `publisher`, `signer_key_id`, `signature_scheme` | Independently trusted signer binding | Hub TLS cert is not publisher signature |
| `os_arch`, `sdk_range`, `abi_range`, `dependencies` | Bounded exact compatibility closure | Reject incompatible host and missing dependencies before install |
| `license_distribution`, `data_class` | `permitted / restricted / non_redistributable / unknown` plus public/private flags | Unknown license or private data blocks Hub/peer offer |
| `origin_allowed`, `metadata_fresh_until` | Reviewed source restrictions, signed catalog freshness | Offline stale metadata is displayed as STALE, not VALID |
| `resource_requirements`, `install_impact` | Minimum disk/free space, required runtime, expected interruption | Preview grounded in actual destination host metrics |
| `receipt_refs` | Signed verifier / transfer / installation receipt refs | Show separate download, verification and install evidence |

**Inventory is per Platform and per authority scope**, never a shared magic Boolean. A package can be `INDEXED`, `CACHED_UNVERIFIED`, `CACHED_VERIFIED`, `QUARANTINED`, `STAGED`, `INSTALLED_DISABLED`, `ACTIVE`, `ROLLBACK_PINNED`, `REMOVED_RETAINED` or `MISSING`. Transport statuses are separate: `QUEUED`, `DOWNLOADING`, `PAUSED`, `VERIFYING`, `COMPLETE`, `FAILED`, `CANCELLED`, `OUTCOME_UNKNOWN`. Disconnected remote status is `STALE` or `UNKNOWN`, not an assertion that the package vanished.

**Double state:** Cache inventory records immutable blob bytes and provenance. Installed component inventory tracks digest, host, operation generation, current settings/lifecycle and identity. Neither is another canonical Core writer.

## 4. On-disk store and quotas (conceptual paths, not permission grants)

The exact OS-native paths are chosen by the canonical installer, reviewed and protected from junctions/symlinks. The *logical layout* below illustrates separate owners and immutable CAS:

```text
<platform-data-root>/
  library/
    manifests/       # signature-bound index snapshot, generation and trust evidence
    objects/sha256/   # immutable content-addressed bytes, never by filename hint
    incoming/         # untrusted bounded partial chunks, not executable
    quarantine/       # corrupt/revoked/rejected blobs, quarantined by policy
    pins/             # metadata references only (active/staged/rollback)
    receipts/         # bounded scrubbed append-only job evidence
  platform-state/     # protected local Platform identity/authority records
<separate-core-owned-state-root>/  # NEVER a normal library child
```

**One immutable object per exact SHA-256 and declared artifact class**; multiple release/package references may point to the same verified bytes where classification permits. Apply size, filesystem boundary, path safety and no hardlink/symlink escape. Incoming partial bytes must be quarantined from executable/admitted package directories until complete digest/signature verification and atomic final move. Reject ambiguous path normalization, archives with zip bombs, malicious symlinks, traversal, duplicate casefold names, and executable bits from source metadata.

**Quota and GC algorithm:** (a) compute free/required space using actual host disk before approval; (b) reserve bounded amount for incoming transfer and unpack expansion; (c) enforce per-peer/per-class/global quotas and max concurrent jobs; (d) pin active/staged/rollback-required and currently transferring artifacts; (e) use revision-fenced mark-and-sweep only on unreferenced verified blobs; (f) require explicit review for deleting a pinned historical release; (g) preserve receipt/audit metadata while eligible bytes can be garbage-collected. LRU alone must not delete rollback or required dependency packages. Existing `OfflineArtifactCache` has a bounded cache; do not silently replace it with incompatible storage semantics.

**Local/supplier inventory** MUST display: reserved vs used bytes, deduplicated bytes, quota, verified/corrupt/unverified bytes, needed for rollback, publishable rights, last observed time and peer source status. Provide diagnostic-only repair/reverify action independent of installing a component.

## 5. Versioned service contracts (names illustrative until Team A freezes SDK)

Do not expose a second REST or IPC authentication implementation. Attach this service to the canonical Platform management broker, exact principal/audience, generation and current SAFE/STOP policy. Core, GUI and TUI clients consume the same versioned schema. Contract concepts:

| Verb / operation | Request | Successful result and rule |
| --- | --- | --- |
| `library.catalog.snapshot.v1` | Cursor, filters, target host, observed revision | Bounded redacted items, signed index generation, source freshness and observed time |
| `library.inventory.snapshot.v1` | Authenticated exact host and class | Cache/install/active states separately; no credential/private file paths |
| `library.sources.snapshot.v1` | Host/source filters | Local/hub/peer/Internet allowed flags, authenticated source IDs, freshness/availability |
| `library.plan.acquire.v1` | Selected IDs, pinned version/digest, target, allowed source IDs, offline-only flag, expected revision | Side-effect-free exact dependency closure, sizes, licenses, provider and owner approval needs |
| `library.acquire.v1` | Pinned plan digest, expected revisions, authenticated approval reference, idempotency key | `QUEUED` bounded job receipt; no install, worker, Core or Platform activation |
| `library.transfer.status.v1` | Transfer ID, expected target and principal | Bytes received/verified, current source, state, errors, last current evidence; no false progress |
| `library.transfer.cancel.v1` | Exact transfer ID, generation, current authority | Drained/cancelled or `OUTCOME_UNKNOWN` with reconciliation; no executable side effects |
| `library.verify.v1` | Artifact ID, expected digest, publisher/trust floor | Independent verifier report and immutable CAS admission, never an install permit |
| `library.install.plan.v1` | Verified digest, target, expected installed revision | Existing B/D governed installer plan; permission and downtime preview |
| `library.install.execute.v1` | Separate one-use owner authorization, plan digest, STOP checked again | Actual installer lifecycle receipt; no library provider bypass |
| `library.pin/unpin.v1` | ID, expected retention revision, reason and owner scope | Reference metadata changed; cannot remove active/rollback pins |
| `library.retire.cache.v1` | Exact digest and pin graph, current approval | Bounded documented deletion after dependency/retention preflight |
| `library.hub.offer.v1` | Enrolled target, signed catalog generation, distributable classes | Authenticated offer metadata only, no unrequested private Core data |
| `library.peer.fetch.v1` | Exact bytes digest, transfer bound token, offset/chunk plan | Bounded bytes only, source/target independently bound; no command execution |

All requests must include or derive: `protocol_version`, `request_id`, `correlation_id`, `idempotency_key`, `target_platform_id`, `component_id`, `caller_principal` and `audience` **from authenticated channel**, `operation_scope`, `expected_generation`, `expected_revision`, `deadline`, `current_STOP`, `proposed_digest`. Caller-supplied identity strings cannot become an owner principal. Prefer current source-bound timestamp + nonce and SDK canonical serialization. Unknown schema/version/field: reject or negotiate known compatible versions. Never expose a raw archive filename as a local install path.

**Authorization tiers:** READ_CATALOG (read-only, redacted), REQUEST_DOWNLOAD (create proposal), APPROVE_ACQUISITION (explicit scoped transfer), PUBLISH_OFFER (host library service permission), MANAGE_PINS (retention authority), EXECUTE_INSTALL (independent owner/target one-time grant), ACTIVATE_CORE/MODULE (separate operation). SDK object construction grants **nothing**; there is no catchall `manage_everything` permission.

## 6. Artifact transfer, resumable chunks and fail-closed sources

### Discovery and precedence

By default: verified local CAS → explicitly configured authenticated Hub → current enrolled authorized peer → explicitly selected verified offline media. The Internet source remains **disabled unless the owner opts in**. Source discovery may list unknown peers for operator review but cannot trust or use them. A source cannot force a target Platform to broaden permission or accept unsigned software. Explicit owner order override is allowed only inside the set of currently permitted sources and current approval.

### Transfer handshake (all mandatory)

1. Receiver knows exact expected manifest/content digests, size, artifact kind and approved source ID from a review plan; it does **not** accept a peer-chosen replacement version.
2. Hub/peer mutually authenticates through current Platform enrollment; check revocation, role, channel binding and source permit for specific artifact/data class.
3. Sender offers immutable signed manifest/catalog metadata, size, chunk scheme, supported resume behavior and license distribution rights. Sender may not send protected local credentials or arbitrary path previews.
4. Receiver creates a bounded temporary transfer ID and resource reservation. A resume token is bound to artifact digest, both Platform identities, role/permission scope, catalog generation and expiry; it conveys **only** the right to resume an approved data read, never install or activation.
5. Sender streams fixed-size bounded chunks with index and declared digest/offset, optionally over a mutually authenticated encrypted channel. Reject overlapping/conflicting/out-of-bounds chunks, size inflation, replay, path traversal or unexpected source. Per-chunk proof is for integrity during transfer; full final SHA and publisher signature remain mandatory.
6. If disconnected, preserve only isolated partial chunks and accurate receipts. Resume only authorized missing chunks after current enrollment, STOP/revocation, grant scope, quota and metadata freshness are rechecked. Partial data is never importable/executable.
7. On completion, reassemble into quarantine, re-open securely, verify total length/digest, verified signed manifest, publisher trust/revocation/antirollback, OS/architecture/SDK/ABI, license and data class. Only then atomic CAS import.
8. Any later **install** or **activation** requires a separate target-host SAFE/owner approval and existing B/D governed operation, plus a new current check just before effects. A Core can request and inspect this process but never grant it by writing into a metadata file.

### Large weights and media

The current `ArtifactReference` bound is 512 MiB per file. A large-model artifact must be modeled as a signed parent manifest with individually bounded chunk objects and an exact ordered reconstruction digest. Example: a synthetic 1 GiB test artifact represented by bounded chunks, whose manifest declares total size, chunk count, chunk digests, license, target class and no actual model inference. Never weaken the existing 512 MiB single-object API to accept unlimited bytes, and never accidentally cache 1 GiB into RAM. The receiver must stream/verify with bounded memory and disk quota. Private model/media redistribution is OFF without affirmative rights.

### Failure taxonomy and safe behavior

| Condition | Result | Required handling |
| --- | --- | --- |
| No local/hub/peer artifact; WAN disabled | `UNAVAILABLE` | Show missing exact digest; no secret Internet fallback |
| Hub unreachable / peer stale | `OFFLINE` or `UNKNOWN` | Keep installed components running; wait/request approved alternate source |
| Signature, digest, manifest or license rejected | `REJECTED` / `QUARANTINED` | Preserve bounded scrubbed evidence; no install |
| Peer enrollment or owner authority revoked mid-stream | `DENIED` / `CANCELLED` | Fence transfer, purge/disallow uncertain partials per policy |
| Source swaps bytes after planning | `CONFLICT` / `REJECTED` | Pin digest, restart only with new explicit plan/approval |
| Disk full, quota, attack-size or decompress limit | `BLOCKED` | No partial object admission; no GC of required pinned releases |
| Transport interruption | `PAUSED` or `OUTCOME_UNKNOWN` | Bounded resume/reconciliation; no duplicate install/executable effects |
| Bad/replayed request or stale generation | `DENIED` | Never call installer or module worker |
| STOP during transfer/install | `DENIED` / `CANCELLED` / `UNKNOWN` | Transfer abort safely; installed effect reconciled by canonical RUN |
| Current active/rollback-pinned blob proposed for deletion | `DENIED` | Show exact holders; no last-resort forced GC |
| Unverified Hub reports package as VERIFIED | Locally `UNVERIFIED` | Receiving verifier must independently check signatures and hash |

## 7. GUI/TUI/CLI parity and concrete screens

No second privileged UI data model. Team C consumes Team A's versioned management contract; Team B/D own operation execution; Team E owns acceptance. Owner palette is defined by `contracts/ui/aegis-theme-v1.json`; purple `#9400D3`, cyan `#00C2FF`, lime `#39FF14`, black `#000000`. Honor `NO_COLOR`, ANSI-free JSON/logs, limited-color and SSH ASCII fallback.

**Minimum navigation in Platform 1.0:**
- `Library > Catalog`: available verified/signed candidates, unverified suggestions distinctly labeled, target-host filtered compatibility; one/selected set cart.
- `Library > Sources`: local, USB, enrolled Hub, enrolled peers, Internet OFF; source ID, current trust/revocation, last response and policy scope; no passwords or raw tokens.
- `Library > Downloads`: exact job+artifact, source, progress based only on received bytes, speed as measured not invented, resume/cancel/current failure and independent verified status.
- `Library > Installed`: per-platform local cached/staged/installed/active vs library-only records, existing Core Manager/Module Manager deep links, own service never assumed active from package presence.
- `Library > Storage`: used/reserved/free quota, active/rollback pins, duplicate hashes, safe cleanup preview, root-trust/config revision.
- `Library > Hub`: role enablement, authenticated allowlist, allowed package/data classes, quota, public-network exposure OFF, served/current clients and log.
- `Library > History`: downloaded/verified/staged/installed/activated/revoked/removed separate receipts, exact SHA, source and target, negative evidence, stale status.
- `Installer first-run`: platform-only default, "No Core/model/modules will be downloaded", optional explicit server library enrollment later, offline source selection and total byte preview.

**Controls must never lie:** A package can be `DOWNLOADED` and `NOT INSTALLED`. A transfer can reach 100% bytes and still be `VERIFYING` or `REJECTED`. A verified installed module may be `PAUSED`. Unplugging the source or closing GUI/TUI doesn't kill Platform; on reconnect, events reconcile using sequence/cursor and snapshot generation. Core-free CLI works with no desktop GUI.

## 8. Release test matrix: immutable 38 acceptance rows

Every test below must be run on **actual disposable signed installed Windows + Debian 12 hosts** at an exact common SHA/release digest. Team E independently evaluates, stores negative receipts and reports failure; design docs/green mocks **never** mark a row PASS.

| Scenario ID | Exact runnable acceptance goal | Existing #201 rows refined |
| --- | --- | --- |
| **LIB-01** | Offline seed install on fresh Windows, no Internet, no Core/model/optional modules, no Git/Cargo/Python; OS-native running Core-free service; installs own Platform state only | 01, 02, 03, 05, 28, 30, 38 |
| **LIB-02** | Same Debian 12 offline/SSH path and native systemd service with clean restart; no GUI needed | 01, 02, 03, 07, 28, 30, 33, 38 |
| **LIB-03** | Start Core-free Hub Platform and independent Client Platform; WAN disconnected, authenticated local mTLS and explicit owner approval, verified index/byte fetch | 10–14, 19, 29, 31 |
| **LIB-04** | Download/stage ONLY one selected signed synthetic Core on client; other reviewed Cores absent; no auto-activation or private state copying | 02, 03, 21, 22, 24, 28, 35 |
| **LIB-05** | Acquire two distinct synthetic Core definitions/runtimes independently; one active per identical identity lineage and one independent Core active only if separately authorized | 21–24, 26, 35 |
| **LIB-06** | Download one signed disposable module, then separately a two-module group with pinned dependency closure; deny missing dependency, unselected artifacts stay absent, no auto-activation | 17, 18, 25, 28, 36 |
| **LIB-07** | One enrolled Platform serves a verified module to another via peer link while Hub/Internet unavailable; receiver independently checks signature/revocation/license and requires own install approval | 10–14, 17–19, 29, 31, 36 |
| **LIB-08** | Unknown peer, revoked peer, wrong host, unauthorized Core requests, expired grant and spoofed source all refused; no transfer/install/privileged data leak | 10–14, 21, 31, 37 |
| **LIB-09** | Corrupt blob, valid hash with untrusted signer, revoked publisher, wrong OS/ABI, downgrade, source swap and malicious archive all rejected/quarantined | 17–19, 21, 25, 28, 29 |
| **LIB-10** | Interrupt/restart/cancel/resume transfer with bounded chunks; disk full/quota; dedupe; post-restart correct receipt and no blind install retry or second writer | 08–09, 19, 20, 26, 29 |
| **LIB-11** | Signed synthetic chunked data artifact exceeding 512 MiB uses bounded memory/space and restores exact total digest, no real model load/redistribution without license | 19, 25, 28, 29 |
| **LIB-12** | Block deleting active/staged/dependency/rollback pinned objects; allow governed GC of unreferenced cache; preserve installation identity across uninstall/reinstall and repair | 19, 20, 26, 29, 37 |
| **LIB-13** | Stop/revoke between plan, transfer, verification, install and activation; show distinct state/approval receipts and no leaked owner secret; third-party private data absent | 10–12, 19, 22, 29, 37 |
| **LIB-14** | Windows GUI, Windows+Debian headless TUI/ASCII/JSON show matching catalog, install/cache/hub/peer states and truthful offline/stale/live updates; operator help docs | 30–38 |
| **LIB-15** | Entire ecosystem offline after previous install: local Platform and any authorized running components remain healthy; cache supports reinstall/rollback without network; hub offline reported accurately | 01, 05, 08, 16, 19, 20, 29, 30 |
| **LIB-16** | Installed-host operator runbook exercises bootstrap, Hub role, enroll client, source order, one Core, module group, transfer, GUI/TUI, audit, revoke, cleanup | 29, 30, 32–38 |

**No bypass:** The full **LIB-01 through LIB-16** suite is mandatory before Platform 1.0 GO, together with existing unrelated 38-row criteria. This is additional evidence inside the 38 criteria, not a claim that success in one scenario completes a row. Test actual application binary, service origin, signed artifact bytes, exact source SHA, SDK/native version, signer chain and revocation, Windows/Debian host identity, time, installer job and independent watcher. A test-only release signer and synthetic Core are acceptable in isolated disposable hosts when explicitly identified; never treat them as production owner authority.

## 9. Delivery batches, prerequisites and strict dependency order

| Batch | Team / prerequisite | Code and evidence deliverable | Dependency / GO |
| --- | --- | --- | --- |
| D028-00 | A + B + E | Freeze SDK/service library schema/version and trust boundary; negative test matrix/fixtures, exact artifact schema | First; otherwise clients create incompatible versions |
| D028-01 | B + A | Reusable signed Platform-only offline seed on Windows/Debian; no Core required; local SHA-pinned cache and installer source choice | Existing AG-D011 and #201 release blocker |
| D028-02 | A + B + D | Unified catalog/inventory metadata, permissioned acquisition plan, exact multi-package dependency preview and states, revision/idempotency | Required |
| D028-03 | A + B | Hub role + read-only signed/versioned index + immutable byte serving, ACL/quota, stop/offline failure | Required |
| D028-04 | A + B + D | Enrolled peer offer/transfer; bounded chunk/resume, revalidation and recipient-side independently governed stage/install | Required |
| D028-05 | B + D | Large artifact chunk parent manifest, opt-in model/asset rights, cache pin/GC and rollback safety | Required |
| D028-06 | C + A | GUI/TUI/CLI parity for inventory, downloads, management, storage, Hub/peer/offline and receipts | Required |
| D028-07 | E (independent) | 16 scenario signed disposable multi-host conformance, exact-SHA GitHub CI, digest/provenance, failed negatives fixed without weakening security | **GO = NO until done** |

**Active code ownership:** Team A remains canonical service/SAFE/API authority; Team B integrates only with the existing single installer, no new ungoverned release engine; Team D consumes reviewed module SDK/lifecycle and synthetic Core reference; Team C only uses the frozen response contract; Team E never marks a row PASS from supplier self-report. Use isolated draft PRs and independent merger review. No autonomous live deployment or direct main merge implied.

### Dependencies that can be done in parallel

- A/B: exact offline seed and artifact acquisition contracts can start while SDK schema is frozen, but cannot ship conflicting interfaces.
- C: read-only catalog UI shell over mock/typed responses may start early; production controls require A's authenticated API.
- D: standalone module dependency manifests and negative compatibility fixtures can be prepared without live Portainer/Docker.
- E: build disposable 2 Windows + 2 Debian host test topology and signed synthetic packages, negative suite, trace collection and preserved artifact receipts.
- Central Hub/Peer transfer needs current host enrollment/SAFE grants, transport, signed verifier and bounded content store; do not call this independent of those prerequisites.

### Single-primary deployment and replica-readiness acceptance

Platform 1.0 must support **one primary and zero replicas** as a valid healthy configuration, with one Core hosted on the same VM **without Core dependency**. It must not hardcode a single mutable Hub endpoint instead of a logical library identity, host-bound primary role and revision/fencing. The release test suite shall exercise a **disposable read-only second replica** and refusal of simultaneous primary writes, while **not requiring the owner to deploy any second live Library**. Manual owner-approved promotion may be staged only with old-primary fence evidence; automated failover is explicitly out of scope. Co-located Core shutdown does not stop Hub, and Hub cache/disk pressure cannot corrupt Core state. Evidence in [deployment profile](AG_D028_SOFIA_VM_PRIMARY_LIBRARY_DEPLOYMENT.md) extends existing LIB-02/03/08/10/12/13/14/15/16 and does not add another acceptance row or scenario number.

## 10. Engineering checklist and release dashboard

- [ ] Platform-only clean offline bootstrap, signed Windows/Debian (LIB-01/02)
- [ ] Source selection and offline/no-fallback rules (LIB-03/15)
- [ ] Local content-addressed verified cache with quota, pins, GC, strict path handling (LIB-09/10/12)
- [ ] Per-host versioned catalog/inventory states and exact dependency planner (LIB-04/05/06)
- [ ] Hub role owner config and signed index, authenticated allowlist, non-public default (LIB-03/08)
- [ ] Peer-assisted bounded transfer + recipient reverify, reconnect and revocation (LIB-07/08/10)
- [ ] Large artifact streaming manifest with license rights and size controls (LIB-11)
- [ ] Separate download, install, activate and removal approvals + receipts (LIB-04/06/13)
- [ ] Remote platform trust/STOP/current session and anti-replay (LIB-07/08/13)
- [ ] GUI/TUI/headless CLI documented parity and diagnostics (LIB-14/16)
- [ ] Whole multi-host repeatable exact-SHA CI on disposable signed releases; every negative test (LIB-01–16)
- [ ] Team E independent #201 evidence update, GO still NO until complete

## 11. Explicit non-goals to avoid accidental security regressions

No requirement to predownload all Cores, every module, arbitrary public marketplace content, all models, or optional personal data. No writable `sofia.db` federation, no online user account requirement to install an offline Platform, no Core self-signing/owner credential delegation, no silent Internet downloads, no direct shell execution triggered by catalog metadata, no shared signer keys just because Platforms share a Hub, no real-time distributed database consensus, no default private-memory replication or automatic model GPU placement. A 1.0 library is **a secure distribution plane**, not an autonomous software supply chain.

**Status vocabulary:** DESIGN APPROVED BY OWNER; SOURCE IN PROGRESS only when an actual PR implements specific batch; TESTED only with documented command + exact SHA; HOST ACCEPTED only with Team E independent installed-host evidence; PRODUCTION READY only after every mapped original row and LIB-01–16 pass. Preserve original failures/unknown states and record evidence, never improve the GO status from Markdown alone.
