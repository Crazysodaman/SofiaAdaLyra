# AG-D028 | Aegis Artifact Library: selective installs, LAN mirror and peer distribution

**Status:** OWNER-REQUESTED ARCHITECTURE (2026-11-08). This design captures five deployment/distribution questions; it is **not** a working server, background auto-downloader, production install service or release certification.
**Scope:** Selective Platform/Core/module/model acquisition, installation, optional bundles, source precedence, locally hosted artifact library, enrolled peer transport, storage quotas, consented artifact management, safety and acceptance. The installer/hub are distinct from canonical operational state.
**Reuse, do not fork:** [AG-D011 Platform-only installer](AG_D011_ASCII_PLATFORM_INSTALLER.md), AG-D021 Signed Component Catalog in [design TODO](AEGIS_DESIGN_TODO.md), `packaging/components.toml`, `src/sofia/platform/ops/platform_install.py` (existing `OfflineArtifactCache`), `src/sofia/platform/ops/platform_release.py`, `platform/modules` signed lifecycle, `sofia.sdk.artifact`, PLAT-02/05/07/08, SDK protocols and [Platform Federation](../sofia2/PLATFORM_PEER_FEDERATION_V1.md). Do not create a second installer, authority, private-data store or permission system. Coordinate feature work with active Teams A/B/D/E and current #201 GO restrictions.

## 1. Five owner answers and non-negotiable meanings

| Owner question | Approved architectural target | Release reality / boundary |
| --- | --- | --- |
| Can I install ONLY Platform? | **YES.** Signed minimal Platform + SDK/runtime/native service and required neutral dependencies; **no** personal Core code/assets/identity/memory, optional modules, voice/2D/3D assets, model weights or GPU setup. | Platform-only packaging and offline installer are defined and source foundations exist; full signed Windows/Debian 12 installed-host acceptance remains open. SDK/shared management contracts may mention Core types without installing a Core. |
| Must every Core be downloaded? | **NO.** Catalog any number, download selected Core runtime(s) on demand, install 0/1/2/etc as host suitability and owner consent permit, and activate separately. | Installed does not mean running. Each unique Core has independent identity/private state; same Core lineage has exactly one acting writer/generation across Fleet. Never auto-clone private data when code is downloaded. |
| Must every module be downloaded? | **NO.** Single selection or dependency-aware reviewed multi-select/bundle. Fetch only missing exact artifacts and transitively required packages after a preview; allow stage-without-activate and disable/keep-cache. | No 47-module all-or-nothing user install. The current optional packaging utility preparing an unsigned 47-candidate *review batch* does not make 47 modules signed/installed or imply a mandatory bulk install. |
| Can Platform B obtain a package from Platform A instead of Internet? | **YES, future governed artifact offer/transfer.** For already verified distributable packages, B may retrieve the exact digest from an enrolled peer and validate again locally. | Transfer is not Fleet enrollment, owner approval or install. No cross-host canonical-state copy, no license-bypassing model/asset redistribution, no unauthenticated discovery-based executable download. |
| Can my server host central master downloads for Platforms and Cores? | **YES.** Platform-operated **Artifact Library Hub** provides indexed immutable verified release bytes to authorized clients, with optional mirroring and distributed cache. | Hub is authoritative for *which bytes it has*, not for another Platform's OS authority or any Core's autobiographical state. Cores may query/propose/manage only via specifically granted SDK APIs. |

**Definition of master:** A central master **distribution catalog and artifact byte store**. It must NOT become a shared writable `sofia.db`, merge Core memories, or become an authority that can install to all enrolled hosts without separate owner/host approvals.

## 2. Deployment modes and desired UX

1. **Platform-only minimum (default):** bring a reviewed offline or online signed Platform release, install the neutral SDK and Platform OS service only, create only the Platform's own installation identity/state. No Core, model, module package or personal data. No Internet required if the full signed offline bundle and trust root are provided and locally verified.
2. **Core selection:** choose one or more Core definitions/runtime releases separately. Distinguish `CATALOGED`, `DOWNLOADED`, `VERIFIED`, `STAGED`, `INSTALLED`, `ENROLLED/BOUND`, `ACTIVE`, `PAUSED`, `REMOVED`; never conflate an artifact with live cognition.
3. **Module selection:** one module or reviewed set; check package identity, dependencies, permission ceiling, host/device/resource fit and settings, size and signer. Atomic *per-package* import with an auditable multi-package plan. Partial multi-package failure must not imply all packages installed or activate anything.
4. **Models and assets separately:** model weights/download licenses and GPU placement are managed by Model Manager; a module/Core package does not silently include huge models. Private wardrobe/voice/identity assets may be classified separately and never peer-replicated without explicit policy.
5. **Sources:** `LOCAL_VERIFIED_CACHE` first; `OWNER_SELECTED_HUB` next; then enrolled `AUTHORIZED_PEER`; optional `OFFICIAL_REMOTE` only if the owner enables Internet fallback; reviewed `OFFLINE_MEDIA` may be selected explicitly at any point. No source is implicitly trusted as a publisher.
6. **Manage UI/TUI:** show `Catalog`, `Downloaded`, `Verified`, `Installed`, `Active`, `Available on Hub`, `Available on Peer`, `Updates`, `Storage`, `Transfer Jobs` and `History`. Filter by host, platform OS/architecture, Core/module/model, signer, exact version, size, license, source and status. Offline/stale/unverified is not silently interpreted as absent or safe.
7. **Explicit controls:** inspect; request download; download missing selected; stage; approve install; activate/deactivate; update; repair; export signed bundle; prefetch; pin; retire cache copy; reverify; quarantine; set quota; request missing dependency; disable Internet; cancel/resume verified transfer. A download never implies install; install never implies launch; promotion never implies permission.

### Illustrative operator view (not currently implemented)

```text
AEGIS > ARTIFACT LIBRARY > INSTALL ON HOST
Host: [locally authenticated host]
Source priority: Local > Your Hub > Enrolled Peer > Internet [OFF]
Bundle: [x] Aegis Platform 1.0 [ ] Core A [ ] Core B [ ] Portainer
Preview:
  Already cached: SDK and Platform release [digest], signature verified
  To download:    none
  To install:     Platform only
  Cores/models/optional modules: NOT INSTALLED
  Canonical Core state and identities: UNTOUCHED
  Impact: reviewed OS service installation on selected host
Review > OWNER APPROVAL > Install > Independent host verification
```

## 3. Topology and data-plane separation

```text
                  [External reviewed publishers] (OPTIONAL)
                                    |
                              approved acquisition
                                    v
                  +-------------------------------+
                  | Artifact Library Hub (server) |
                  | indexed immutable releases    |
                  | cache, ACL, quota, audit       |
                  | signed manifests+license meta |
                  +-------------------------------+
                    ^       ^             ^
         owner-governed   TLS/mTLS     authenticated peer transfer
         catalog APIs      |             |
                    v       v             v
                 Platform A <---------- Platform B
               local cache             local cache
                   |                       |
         one Core or none           another Core or none
         selected modules           selected modules
                   |
             model/asset store: separately consented
```

**Reuse existing facilities, not extra mandatory modules:** Hub mode can be a specially configured Platform release/artifact service backed by PLAT-02 Artifact Registry, PLAT-05 Signed Module Store, PLAT-07 Fleet transport and PLAT-08 release validation. Hosting it on a server with other workloads must not make the server the writer of remote protected Platform/Core state. Any optional GUI is a client; the library works headlessly without a running Core.

**Two distinct storage planes:**

| Data type | Can Hub/peers mirror by default? | Authoritative owner / caveat |
| --- | --- | --- |
| Signed Platform/SDK/Core *runtime* software packages | Yes, if publisher permission, trust and license allow | Immutable bytes keyed by SHA-256; local Platform must independently verify before admission |
| Signed optional modules, manifests, rollback packages | Yes, if distributable and enrolled/authorized | Per-host compatibility, dependency, signature/revocation/STOP, retained rollback history |
| Model weights, tokenizers, optional public AV assets | **Opt-in**, verify digest/license/redistribution rights | Large chunked transfer with resumable fingerprints; model manager owns load/placement |
| Core *definition*, identity, memories, Constitution/personality changes | **NO by default** | Exact Core identity/private state under one canonical writer; encrypted, explicitly authorized backup/export only |
| Platform operational state, installation identity, owner secret, API keys | **NO** | Each Platform owns its own protected local state and trust; hub cannot mint owner approvals |
| Module configuration, integration tokens, environment variables, private household/financial data | **NO** | Remain under owning Platform/owner privacy; authorized encrypted restore/migration is a distinct separately reviewed action |
| Published reusable developer SDK docs/test fixtures | Yes, if intentionally public or allowed scope | Source control or signed documentation artifacts; non-executing examples |

**Master catalog vs protected data:** A manager may update package availability, pins, mirrors and reviewed metadata; it must not edit any remote live Core's durable memory or Platform's authority records. Explicit consented collaboration/backup is a different data service with its own classification, keys, lineage and admission tests.

## 4. Download, verify, install, transfer as different authorities

| Operation | May propose / view | May authorize / execute |
| --- | --- | --- |
| Search/index content, compare compatibility | Any authenticated read-scoped Core/GUI/TUI/Platform | Hub/Platform returns bounded redacted signed metadata; no authority granted |
| Request download/prefetch to hub or local cache | Owner, eligible Platform, DEV Core with proposal scope | Platform-owned job under bandwidth/storage/allowlisted origin policy and owner rule. Untrusted metadata is advice |
| Offer signed artifact to enrolled peer | Hosting Platform after per-peer ACL | Local Platform checks current enrollment and allowed classes; peer accepts only matching planned digest/version |
| Transfer bytes | Approved Hub or peer data plane | mTLS/authenticated endpoint, chunk bounds, quota/rate limit, cancellation and resume receipts; no capabilities executed from transfer data |
| Verify package | Receiving Platform's own verifier | Check exact SHA-256, size, all manifest/artifact digests, trusted signer chain/current revocation, OS/ABI, SDK compatibility and license. **Transport/source reputation never replaces signature** |
| Install, update, remove, activate, change private data | Cores can propose exact operation | Target Platform/SAFE/current owner approval + governed installer/Module Manager. Signed bytes alone do not grant install |
| Delete cached bytes or alter hub availability | Explicit owner / authorized cache manager | Separate catalog revision, reference counts and retention constraints; cannot delete active/staged/rollback dependencies |
| Change private Core state | Related Core may propose within Core policy | The exact identity's authorized single writer and reviewed privacy/data lifecycle; never a package cache operation |

In particular: **a Core cannot persuade the dummy SDK Platform into signing, installing or revoking a live package**. The reference examples remain educational source code.

### Resolver (design, no executable fetcher yet)

```text
Request: host + selected IDs + allowed sources + exact pinned versions
  -> authenticate request and current owner/peer permissions
  -> resolve signed dependency graph and trust state
  -> compute exact compatible digests and sizes
  -> compare current cache against digest/publisher/revocation
  -> offer eligible source options (local/hub/peer/offline/Internet)
  -> show complete plan, disk impact, license and restart requirements
  -> approve scoped acquisition (not install)
  -> transfer into isolated staging with chunk/size/time budgets
  -> verify ALL bytes + signed manifests with independent trusted root
  -> atomic cache import (retain source provenance, audit receipt)
  -> optionally offer separately governed install plan
  -> install/activate only with distinct fresh target-host owner authorization
  -> verify target-host outcome; no invented success on disconnect
```

**Source unavailable:** return `UNAVAILABLE` (or `OFFLINE` / `UNKNOWN` if status uncertain), never silently fall back to Internet when disabled. If no eligible supplier, show exact blocked digest and which dependency needs acquisition. If peer disconnects mid-transfer, reconcile received chunks and resume only verified missing chunks; never run partial archives or blindly replay a potentially effectful install.

**Large artifacts:** Current `sofia.sdk.artifact.ArtifactReference` has a 512 MiB single-file bound and `OfflineArtifactCache` has configurable global size constraints. Large model weights require an explicit signed/chunked high-volume transfer contract; **do not** bypass those bounds by pushing multi-GB blobs into the existing small artifact API.

## 5. Privacy, security and operations

- **Hub/peer threat model:** a compromised Hub may serve stale/tampered/unauthorized files or track which packages a Core requests. Protect per-peer ACLs, signed catalog index, anti-rollback and revocation, least-privilege service identity, outbound allowlist, offline policy, bounded logging and privacy of lookup patterns where practical.
- **No universal trust by LAN:** proximity, hostname, mDNS/Bonjour discovery, Cloudflare tunnel name, IP address or possession of valid package bytes is not owner enrollment. Only independently enrolled, currently trusted Platform peers may advertise usable artifact inventory; discovery alone may not authorize download/execution.
- **Cache versus sign:** the Hub stores/distributes exact bytes. It does **not** become a universal signing root or authority. A malicious Hub cannot turn an unsigned Core/module into a trusted release, even if it owns a server TLS certificate.
- **Protection:** no owner 256-bit permission secret, private signing key, personal Core identity, credentials or security tokens in shared artifacts, model prompts, URLs, logs or mirrors; deny recursive/symlink/junction path escapes; safe atomic staging and post-open verification.
- **Policy:** per-host quotas, global hub capacity, prefetch policy, transfer speed/time windows, pins/retention, lifecycle-aware garbage collection, approved revocation and vulnerability withdrawals. Cached package can stay available for approved rollback, but revoked executable must never be newly activated.
- **Source integrity:** hash alone detects changed bytes, it is not publisher authenticity. Trust comes from an independently trusted publisher signature + current revocation and exact identity binding, not from peer or master-server promises.
- **Offline operations:** a fully verified and locally complete bundle can be staged/installed using the approved offline installer and existing trust root. Internet absence must not disable a healthy Core-free Platform.
- **Provenance:** record target host, Core/module/artifact ID, source kind (not secret URL), publisher/signature, source digest, receiver digest, manifest revision, enrolled peer identity where applicable, download/stage/install/activate receipts separately, time, job and version.
- **Cores' role:** eligible Cores may discover available SDKs/modules, compare versions, propose cache/import, write code in an approved sandbox and use a reference cookbook; they cannot acquire owner credentials or impose network/system-wide download policy.

## 6. Implementation program (no duplicate workstreams)

| Phase | Work | Existing owner | Definition of done |
| --- | --- | --- | --- |
| **A. Platform-only offline boot** | Signed minimal release + offline bundle verification, native Windows/Debian installer, no Core code/assets/model/module install. Independent local cache with digest pinned source. | **Team B** (#244), Team A trust, Team E acceptance #201 | Exact signed installed-host proof on both OSes; no surprise downloads, no `sofia.db` or Core assets |
| **B. Selective catalog** | Read-only catalog including Core/module/model package states, per-host installed inventory, compatibility graph, download/install separation, quota and stale state. | Platform PLAT-05/08 + **Team C** GUI/TUI + D module SDK | One Core/one module chosen; other unselected packages absent; no auto-activation |
| **C. LAN Hub (new functionality)** | Serve immutable approved release bytes and signed versioned catalog from owner-controlled server, verify inbound/outbound ACL, quotas, cache pins and local offline policy. Reuse `OfflineArtifactCache`; avoid second signing authority. | Platform PLAT-02/05/07/08; Team A authentication; B installer; E QA | Hub and client exchange exact digest and signature; revoked/tampered data never accepted |
| **D. Peer-assisted transfer** | Authenticated transfer from enrolled Platform B to A and vice versa; revocation, partial resume, all source/target compatibility and no remote auto-install. | PLAT-07 Fleet, Team A auth, B/A governed jobs | No Internet needed when a permitted peer/hub has complete artifact; mid-transfer disconnect recovered without executable side effects |
| **E. Model/asset package awareness** | Separate licensed model store chunking, on-demand download, location/resource-aware inference; opt-in private assets. | Model Manager/PLAT-06/07 and privacy | Huge models do not flow through 512 MiB small-artifact API or silently pull to GPU-less hosts |
| **F. Multi-platform conformance** | Windows/Debian/air-gapped host installed tests, duplicate digest sources, wrong signatures, revoked peer, corrupted chunk, USB import, missing dependency, crash/restart, quota & garbage collection; exact SHAs. | **Team E** | No assumed success, source-independent verification, preserved canonical writer and truthful UI across network failure |

**Platform 1.0 gate boundary:** Phase A is already part of #201 through AG-D011. The **full LAN Hub and peer-to-peer distribution system is a staged future feature**, not a stealth new mandatory #201 acceptance row. A minimal local/offline cache is already implemented as a source foundation; no installed-host certification for the network library is implied.

## 7. Recommended default policies

| Setting | Recommended default |
| --- | --- |
| Installation | Platform only; opt-in Core(s), optional modules, models, data |
| Artifact catalog | Read-only by default, host-specific version/signature/size status |
| Initial source selection | Local verified cache; owner-selected Hub; enrolled authorized peers; verified removable media if explicitly selected; Internet fallback **OFF until enabled** |
| Automatic downloads | OFF for runtime/install packages; approved prefetch with specific size/origin policy may be enabled |
| Installation/activation | Separate explicit authorized operations; do not conflate with downloaded/verified |
| Remote peer artifact offers | Disabled until both trusted hosts are enrolled and scoped distribution policy exists |
| Private Core/platform/owner state | NEVER in shared artifact mirror by default |
| Rollback copies | Retained according to pin/retention policies, no deleting active dependencies |
| Network interruption | Pause/reconcile/mark uncertain, never silently download from a different origin or auto-install |
| Headless/GUI management | Same governed backend, readable states/receipts, themed TUI/ASCII/no-color fallback |

**Acceptance note:** All of this is an owner-requested **product/design contract**, not an automatic owner approval to execute a live fetch, transfer, install, memory migration, Core activation, external network exposure or production rollout. Those effects require distinct authenticated authorizations and real-host evidence.
