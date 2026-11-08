# AG-D028 | Single primary Artifact Library on Sofía VM, future redundant replicas

**Owner decision:** 2026-11-08. Initially deploy **exactly ONE logical Aegis Artifact Library**, with **ONE primary Hub on the existing Sofía VM**, alongside its separately governed Sofía Core worker. Design and release contracts MUST allow independently hosted redundant replicas later, without a new installer, package signer, Core/owner authority or canonical Core writer.
**Status:** APPROVED DEPLOYMENT TARGET / DESIGN; **NOT INSTALLED, NOT VERIFIED**. [Platform 1.0 release specification](AG_D028_PLATFORM_1_0_RELEASE_SPEC.md), [parent architecture](AG_D028_AEGIS_FEDERATED_ARTIFACT_LIBRARY.md), [16-case QA runbook](AG_D028_ARTIFACT_LIBRARY_QA_RUNBOOK.md), [release blocker #201](https://github.com/Crazysodaman/SofiaAdaLyra/issues/201), [implementation #250](https://github.com/Crazysodaman/SofiaAdaLyra/issues/250). No owner approval for live deployment, host enrollment, data movement, existing Core activation, production signing or main merge.

## 1. The owner's actual topology

```text
Artemis (hypervisor) -- existing Sofía VM (headless Debian, OS/version to verify)
 |
 +-- One Sofía VM: separate process boundaries and protected data roots
      |
      +-- Aegis Platform (current locally approved instance / identity)
      |    +-- SAFE/STOP, authenticated management broker, jobs and audit
      |    +-- Artifact Library HUB: PRIMARY for logical library L
      |         +-- immutable content-addressed signed package cache
      |         +-- catalog snapshots, package source and license metadata
      |         +-- per-client ACL, storage quota, pinned rollback versions
      |         +-- bounded authenticated transfers and recovery receipts
      |
      +-- Sofía Core worker (optional, separately installed and activated)
      |    +-- Core SDK client: may view/propose/library-manage within grants
      |    +-- identity, memory, personality and canonical state: PRIVATE
      |
      +-- Platform-local management CLI/TUI: works if Core is stopped
            +-- GUI may connect remotely through enrolled managed API

Other Platform(s) -- local verified caches -- authenticated LAN fetch from L
Future: Replica(s) of logical library L on other authorized physical hosts
```

**One Library** means exactly one logical catalog/namespace and one active primary writer. Every Platform still has its own **local verified cache** and can transfer allowed immutable packages. A local cache does **not** count as a second independent Library. Replicas later represent more copies/availability of the SAME logical Library, not duplicate Core memories or another master catalog.

Aegis Hub is **Platform infrastructure enabled as a role**. Installing Sofía Core on the same VM is optional and never a library dependency. Both use Platform's authenticated management API, but run in separate supervised processes/workers where permitted. Core updates, crash, shutdown or GPU inference outage MUST NOT stop the Platform/Hub. A failed Hub download MUST NOT stop the Core's already-installed functions. A VM/power/hypervisor failure will take **both** down until a separate physical replica exists; single-VM installation is **not high availability**.

**Canonical writer protection:** Existing migration notes may still designate Venus as Sofía's active single writer; the VM being chosen as a future Core host does not itself authorize a Core writer cutover. Adding Hub role does not rekey a Core, import `sofia.db`, change writer authority or auto-activate Sofía. Keep Platform identity, Hub logical identity and Sofía Core identity distinct.

## 2. Verify VM prerequisites instead of assuming them

The existing VM has previously been described as a headless Debian guest on Artemis with **6 vCPUs and Dynamic Memory (512 MiB minimum / 2 GiB startup)**. Earlier recorded storage had a small root filesystem and a larger `/home` partition; that is **historical**, not a verified current capacity or dedicated library filesystem. Earlier OS notes disagree between Debian **12** and **13.x**. The Platform 1.0 signed installed-host target is Debian **12**: **do not install onto an unverified/unsupported Debian 13 guest** merely because it runs Debian.

Before any real owner-authorized rollout, the installer must read and display:
- guest distro **and precise release**, kernel/ABI, architecture, service manager and support policy;
- CPU/actual available memory and dynamic-memory pressure while the Core is idle and active; current running components, swap, other VMs' resource impact;
- current root/home volumes, free blocks/inodes, mountpoint ownership, expected Core state path and available capacity for library CAS, unpack staging, signed rollback and snapshots;
- local firewall/bind address, actual enrolled peer IDs, cert/trust status, LAN reachability and Internet OFF/ON policy;
- existing Platform/legacy Sofía services and canonical writer state; reject implicit adoption, duplicate writer and unintended Core stop.

**Sizing policy (not a fabricated GB minimum):** Select a dedicated **persistent data volume** where practical, mounted under a restricted neutral Platform-owned path (e.g. *illustrative* `/srv/aegis/library`), not the small root filesystem and never inside `sofia.db`, Sofía Core memory, protected state or a Docker container's transient layer. The owner chooses a bounded quota from observed free space. Reserve space for **selected packages + required pinned rollback versions + the largest permitted concurrent incoming/unpack transfer + filesystem margin**; refuse download when reservations exceed the budget. A 2 GiB startup guest may be insufficient for simultaneous Core and large artifact handling: bound transfer worker memory and concurrency, monitor actual host pressure and propose VM memory/storage changes only after measured telemetry and separate owner review. Do not promise a safe fixed quota absent measurements.

The library's metadata DB, immutable blob CAS, partial chunks and receipts must be owner-private on disk, audited, crash-recoverable and separated from the Core's private writer/database. Use the canonical Platform-local store and sanctioned storage abstractions; no second writable `sofia.db` and no direct Core filesystem writes. An isolated service may access only scoped package storage, not all Core state.

## 3. What is installed by default versus expressly selected

| Component | First Platform install | Sofía VM when owner sets up this plan | Later |
| --- | --- | --- | --- |
| Neutral Platform + SDK + native service | Required; **Core-free and offline-capable** | Install using signed governed OS installer after OS preflight | Updated by same verified installer |
| Local verified artifact cache | Built-in Platform infrastructure | Enabled on Sofía VM, bounded storage | Every other Platform has its own local cache |
| Artifact Library Hub role | **OFF** by default; not a second installer | **ONE primary** Hub, explicitly enabled and approved | Same Library can have read-only replicas |
| Sofía Core runtime and protected private data | NOT downloaded/installed automatically | Separately selected/installed or retained by existing approved Core workflow | Independent update/migration approvals |
| Modules and model weights | NOT downloaded/installed automatically | Only those individually/group selected by owner | Per-host demand; avoid bulk catalog downloads |
| GUI | Optional client | Headless Debian TUI/CLI is enough; Windows GUI client may be remote | Same API contract on all hosts |
| Peer/replica enrollment | OFF by default | Allow only explicitly authorized enrolled clients | Later enroll replicas/peer sources |

**Install order:** (1) signed Platform-only offline bootstrap; (2) verify native service and local identity/SAFE; (3) inspect and select Library persistent root/quota; (4) enable one Hub role with LAN listener disabled until TLS/current enrollment/access policies are configured; (5) seed reviewed signed artifacts from trusted offline media/approved source; (6) enroll specific client Platforms to receive allowed classes; (7) start Library Hub and prove read-only catalog + verified transfer; (8) install/start or reconnect Sofía Core **separately** under existing Core identity/writer rules. These are proposed steps, not executable commands today.

## 4. Initial first-run wizard and daily management

Illustrative owner-facing **Control Center > Artifact Library > Setup** (not existing live UI):

```text
AEGIS ARTIFACT LIBRARY -- FIRST SETUP (Sofía VM)
Host OS              [OBSERVED]       Platform ID [CURRENT VERIFIED]
Library topology     (x) New SINGLE PRIMARY   ( ) Join existing replica
Logical library ID   [GENERATED/APPROVED, not host UUID or Core identity]
Role                 (x) Hub + local cache
Co-located Core      [DETECTED / NOT ASSUMED]  NO Core dependency
Storage mount        [OWNER-SELECTED PERSISTENT VOLUME]
Quota + reservations [CALCULATED FROM ACTUAL FREE SPACE]
LAN endpoints        [DISABLED until enrolled peer trust]
Sources              [LOCAL SIGNED CACHE] [OFFLINE MEDIA]
Internet fallback    OFF
Public listeners     OFF
Auto-install/activate OFF
Backup               [CONFIGURE OFF-VM VERIFIED BACKUP]
Replicas             0 (may enroll additional replicas later)
Actions              [PREVIEW] [TEST ACCESS] [APPROVE] [ENABLE] [CANCEL]
```

**Manage from:** authenticated Aegis Platform GUI or Debian 12 supported headless TUI/CLI using Team A's single management interface. Sofía Core's authorized SDK tools may list inventory, create proposals, compare dependencies, request downloads within owner policy and summarize failures. Core cannot silently modify trust, publish unsigned code, choose primary/replica promotion, change retention or install/activate a package.

**Required screens:** Overview (logical Library ID, primary host, online state, advertised replicas and last-replication times), Catalog, Verified/Quarantined, Download/Transfer Jobs, Storage/Quotas/Pins, Packages by Target Platform, Sources/Peers/Internet policy, Updates and Rollback, Permissions, Backup/Restore, Replicas/Promotion, Health and Audit. Downloaded ≠ installed ≠ activated; replicas may be `SYNCED`, `LAGGING`, `OFFLINE`, `STALE`, `NEEDS_RESEED` or `REVOKED`. TUI and GUI must agree on revision and generation; failed or offline is never shown healthy just because a last-known snapshot exists.

**First-release example actions (names illustrative, not existing commands):**
- `aegis library status`: reports Hub status and actual service/generation, Core-independent.
- `aegis library catalog`: signed-content inventory with source/distributability, no install.
- `aegis library plan --host TARGET --select MODULE`: read-only dependency/size/rights preview.
- `aegis library acquire --plan PLAN`: separately approved artifact transfer only, no module execution.
- `aegis library storage`: quota, pins and safe cleanup preview.
- `aegis library backup verify`: independent manifest and restoration capability, no overwriting Core state.
- `aegis library replicas`: primary+replica status; missing replicas are normal in single-primary mode.

Actual CLI names must be selected by canonical Team A/Team C contract freeze, not implemented by these illustrative examples.

## 5. Identity, replication and redundancy: now one, later N

### Distinguish the identities

1. **Platform installation ID**: unique durable identity of the Sofía VM's Aegis Platform instance; its owner/security keys are not Library-wide publisher signing keys.
2. **Logical Library ID**: stable owner-approved namespace for catalog snapshots and immutable packages, allowing later replica membership and controlled recovery/migration. It is not Sofía Core's identity or a trust token.
3. **Hub membership ID + generation**: this currently enrolled Platform instance's role (`PRIMARY`, `READ_REPLICA`, `OFFLINE`, `REVOKED`) and fresh host-bound session.
4. **Core identity**: entirely independent; one authorized canonical writer/lineage, no artifact-catalog replica ever writes Core memory.
5. **Publisher keys**: external independently trusted signers of software; a Hub transport key or TLS certificate cannot transform an untrusted package into a trusted one.

### Single-primary initial policy

- **Exactly one writer** for the logical Library's **mutable catalog metadata**, retention/pins, allowed source list and replica membership. It is the Platform-owned Hub on Sofía VM. Immutable release bytes are addressed by digest and may exist at many independently verified caches.
- Clients pin the logical Library ID and current approved primary's authenticated Platform identity, published via owner-reviewed endpoint/config. Do not trust LAN discovery, DNS name or last-known IP as enrollment.
- Client caches remain usable during Hub outage for already verified packages, offline-install/rollback when separately authorized, and normal installed workload operation. Unknown availability never triggers Internet or a peer chosen by a model.
- Backup on **another physical storage fault domain** of (a) immutable content digests, (b) versioned scrubbed catalog snapshot, (c) pin/revocation/trust metadata with separately protected encryption/identity and (d) restoration receipts. Backups are **not** a second live Library; if stored only on Artemis, they don't protect from Artemis hardware failure.
- Garbage collection is always fenced by current signed catalog generation/pin set, installed references and backup/replication retention. A replica may not delete a known-required blob merely to catch up to new GC policy.

### Later add replicas without rebuilding the platform

**One logical Library, N nodes:** additional enrolled Platform hosts may run a **read-only Artifact Library Replica** role. Replica joins only after exact owner approval and current host mutual trust; fetches an authenticated primary catalog snapshot plus signed package metadata and exact permitted CAS objects, independently revalidates full hashes/signatures/licensing, then subscribes to bounded revisioned catalog changes.

- **Replica's default capabilities:** serve permitted **immutable verified package bytes** and signed/snapshot-index metadata to enrolled clients if policy allows, report replica lag and current provenance; **no owner approval issuance, no master catalog writes, no package signing, no Core memory copy**.
- **Replica consistency:** revisions and primary epoch monotonically advance; gaps or inconsistent lineage cause `STALE/NEEDS_RESEED`, not apparent sync. Strong read is from current primary; lagged replicas may serve by exact pinned digest only when verified and authorized. A signed package update never silently changes an existing digest.
- **Manual promotion/failover:** before new replica becomes primary, operator verifies old primary is **fenced** (or physically isolated/revoked with proof), latest acceptable committed snapshot/epoch, intact trust and key handling, owner-approved promotion plan, generation advance, authoritative catalog revision and client routing refresh. When old primary returns, it MUST refuse catalog writes until independently reconciled and re-enrolled as replica. **Never allow simultaneous primaries or split-brain writes.**
- **Failure cases:** primary down, replica lagging, network partition, stale snapshot replay, wrong library ID, revoked member, corrupted blob, concurrent promotion, power loss during transfer, no connectivity during manual promotion. Each requires explicit `UNAVAILABLE`/`READ_ONLY`/`NEEDS_RESEED` statuses and preserved evidence, not auto-promotion.
- **Release requirement:** Platform 1.0 must **not** assume a single hard-coded Hub URL/ID in its schema; it must preserve logical Library ID, membership, epoch and replica-aware source metadata, and prove attach/read-only replica/read by exact digest and denied dual-primary promotion in disposable host tests. **Automatic HA failover, quorum consensus and multi-master editing are not required** for Platform 1.0. There is **no owner requirement to deploy a second live Library** now.

### Two different future concepts (do not conflate)

**Replica of one Library**: one logical catalog, read-only mirror, optional owner-governed promotion. This is what the owner wants for redundancy.

**Independent second Library**: a separately owned catalog/namespace with its own governance and federation policy, not a replica, and not automatically merged. **Deferred** unless separately decided.

## 6. Storage, backup and recovery contract

**Local disk design:** distinct immutable package CAS + bounded incoming partials/quarantine + signed catalog projections/Platform-owned retention and source metadata. Protected Platform private state and Core private data remain separate. Set owner-private OS permissions, no world-readable library, no redirect/symlink/junction, enforce quotas while Core shares memory/IO. If storage volume unmounts, Hub must fail closed while Core/Platform service state remains healthy or truthfully degraded, never create a new empty library in a different path.

**Initial one-Library continuity:** an offline verified seed and periodic off-VM verified backup provide recoverability until a replica is enrolled. Backups must be restorable to a **new Platform instance** only after current owner-authorized Library namespace recovery, fresh unique Platform installation identity, updated trust/endpoint binding and no old-primary simultaneous write. Do not clone Sofía Core canonical state as a package cache restore.

**Core-coexistence safety:**
- Hub service/restart cannot restart Core, drop its active Core generation or acquire Core DB writer.
- Core restart/replacement cannot interrupt Hub's already authenticated transfers; if Platform restart is actually required for shared ABI/security changes, show a maintenance plan and reconnect/reconcile outstanding jobs without invented success.
- Worker CPU/RAM/disk/network and transfer concurrency are bounded and adjustable by owner policy; I/O and full-disk threats to Core's protected state are tested under pressure.
- A proposed remote model download is separate from a signed module SDK package, and must obey space/license/host GPU rules; GPU inference from another host is not a Hub dependency.
- Ensure Platform SAFE/STOP and current revocation are rechecked on *every* management action and on resumed transfers, not just when initial UI loads.

## 7. Required controls and SDK compatibility

**Reuse canonical SDK and Platform management API:** no separate Hub login or master permission controller. Current authenticated principals, audience, owner approval, target Platform generation, idempotency, STOP and revocation remain service-side. Access scopes include `library.read`, `library.request`, `library.offer`, `library.manage_sources`, `library.manage_storage`, `library.manage_replicas` (all **illustrative**, to be frozen by Team A). Promotion is a uniquely high-risk operation requiring explicit owner approval and fence evidence. A Core's `library.request` never implies `library.install` or `library.promote_primary`.

**API concepts (illustrative):** `library.status.v1` includes current logical ID, role, primary Platform ID, epoch, revision and freshness; `library.catalog.snapshot.v1` reads signed index; `library.replicas.plan/join/status/promote.v1` require exact expected generation and enrollment/pin; `library.backup.snapshot/verify/restore-plan.v1` never imports personal Core state; `library.storage` includes actual free/used/reserved and Core-visible resource pressure without secrets. HTTP client access outside Aegis API cannot become owner authority. SDK v1 compatibility and API negotiation must reject unsupported states, never downgrade silently.

## 8. Independent exact-SHA GO tests to add within existing LIB-01–16

The design below **extends acceptance scenarios without creating LIB-17 or acceptance row 39**. Keep source matrix 38 entries and all current FAIL/NOT TESTED evidence.

| Map | New minimum scenario | Evidence |
| --- | --- | --- |
| **LIB-02/03** | Debian Core-free Platform Hub can initialize one Library, cold restart and serve signed catalog. With a separately approved synthetic Core worker active on **same test VM**, Hub remains up when Core worker stops/restarts and Core private file tree is absent from Hub CAS. | Real service PIDs/generations, separate identities and storage roots, fresh signed catalog/transfer receipts |
| **LIB-03/15** | One primary, **zero replicas** is healthy and supported. Stop Hub, show remote `OFFLINE` and cached previously verified packages still usable; existing Core/Platform healthy. | Host + client observation, no Internet fallback, independent OS/service health |
| **LIB-10/12** | Core/Hub co-location disk-full, invalid mount, RAM pressure, partial chunk power-loss and backup restore to isolated disposable host; no Core DB damage, silent path replacement, privileged logger leak or state writer duplication. | Disk/memory telemetry, quarantine/rollback refs, off-host backup digest and independent restored index verification |
| **LIB-08/13** | Unknown replica, wrong Library ID, expired enrollment, fake primary, replayed epoch and attempted dual-primary promotion all denied; STOP/revocation fence each step. | Independent negative auth and state receipts, no copied credentials/private Core data |
| **LIB-14/16** | GUI/TUI/CLI Setup explicitly supports `1 primary / 0 replicas`, shows Core independent, resource pressure, backup status and later replica option. Add one read-only replica in disposable topology; independently verify digest, lag and no writes; demonstrate owner-approved **manual** promotion with proven old-primary fence and no split brain. | Same API and UI generations, exact source/host identities, separate signer vs library membership, reviewer report |

**Release interpretation:** Owner will deploy **only one primary** on Sofía VM initially. The release may be evaluated with additional disposable replica hosts to prove future capability, but this does not authorize the owner to install a replica today or require a production quorum. Full live multi-node automated failover remains a future feature if separately requested.

## 9. Implementation handoff

| D028 batch | Work addition | Team |
| --- | --- | --- |
| **00** | Freeze logical Library ID, `PRIMARY/READ_REPLICA`, epoch/revision/freshness, source/authority API and STOP/generation negative fixtures with optional zero replicas | A + D + C + E |
| **01** | Supported-OS preflight, Core-free signed Platform-only installer and owner-selected persistent Hub volume. Coexist with separately installed Core without importing private `sofia.db` | B + A + E |
| **02** | One primary catalog and per-host cache/installed states; no hard-coded single server URL, digest pinning, dependency graphs | A + B + D |
| **03** | Bound Hub role to canonical Platform broker, local private CAS, separate supervised worker, authenticated client serving | A + B |
| **04** | Read-only replica enrollment and sync via enrolled peer transport; manual promotion with fencing only if host acceptance can verify; no auto failover | A + B + D |
| **05** | Off-VM backup/recovery, safe storage pins/GC and quota under Core+Hub contention | B + D |
| **06** | Headless/GUI Setup, sources, single-primary role, replica status, backup health and exact resource controls | C + A |
| **07** | E runs the co-location, zero-replica and extra disposable replica negative cases mapped to LIB-02/03/08/10/12/13/14/15/16 at exact signed installed-host SHA | E |

**No certified host yet:** This deployment profile only defines how to build and test a safe one-Library Sofía VM installation. Do not run illustrative CLI, enable public Hub listener, move Core databases, or claim service/replica acceptance until reviewed source, signed OS support, actual resource preflight, correct owner approval and independent host evidence exist.
