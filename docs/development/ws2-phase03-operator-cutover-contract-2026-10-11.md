# Phase 03 • Canonical Home, privileged cutover and disaster recovery contract

**Workstream:** 2 · **Date:** 2026-10-11 · **Status:** production design and source-backed audit, **not authorized/accepted deployment**. This document supplements, and does not replace, `docs/development/v18-venus-artemis-topology-decision.md`, `docs/development/venus-artemis-runtime-topology-2026-10-11.md`, and `docs/development/phase03-signed-state-home.md`.

## Initial-versus-future cutover decision (owner selected)

**Decision: Option A for the first Venus-to-Artemis migration; Option B only as a separately authorized later upgrade.** The first migration is human-initiated and human-supervised. The operator must review exact source Venus and destination Artemis/Sofia guest identities, sign a fresh operation-scoped authorization, independently verify the old writer is quiesced and cannot restart or write using its prior epoch, confirm a current encrypted complete backup, the protected original identity, and the external signed memory-erasure journal, then approve nonactive guest-local restore, a separately reviewed monotonic epoch transition, and exactly one activated runtime. Each uncertain or interrupted stage stops for review. After the new writer accepts a canonical write, an old Venus copy is never an automatic rollback target.

**Human supervision is not proof of fencing.** An ordinary Sofía service STOP response, SQLite lock, signed pointer, unprivileged Fleet receipt or operator-supplied text cannot certify that Venus is physically fenced. The existing RelocationAuthorization and nonactivating staging/pending-pointer contracts carry reviewed *references*, but do not verify privileged host evidence on their own. Independent trusted host-maintenance proof must be supplied and checked; where it is absent, the system stays nonactive and reports the missing gate. No actual host fencing, cutover or privileged witness has been observed in this workstream.

Option B reuses the same exact host identities, backup and erasure proofs, owner-scoped authorization, monotonic epoch and failure-state contracts with a future independently privileged host-controlled broker. It additionally requires separately designed/executed stale-writer prevention, interruption recovery, authenticated host failure detection and controlled reverse migration/failback. **Autonomous failover and a second writer remain disabled** until separately authorized and verified. This is a reusable architecture direction, not permission to deploy that broker now.

## 1. Non-negotiable state owners and trust boundaries (CA-3701, 5201, 6101, 6804, 6808)

| Item | Current truth | Reviewed target |
| --- | --- | --- |
| Sole writer and live `sofia.db` | Venus, with `CanonicalSQLiteGuard` pinning its existing inode/path | Dedicated Debian 13 VM `Sofia` on Artemis, using guest-local persistent storage **only after** independently fenced cutover |
| Cognitive inference | Venus GPU | Venus as pinned-mTLS, explicitly granted remote inference worker; no fallback/new model if unavailable |
| Original history, memory, LIFE, GOALS, SAFE, ACT | Venus canonical SQLite; external deletion authority and backups remain separate | Same authoritative identity/state after independently verified complete recovery |
| Desktop, Discord and paired devices | Existing authenticated channel principals | Authenticated clients to new single-writer host, re-paired/revoked where necessary, **never** raw SQLite over SMB/NFS |
| Workshop VM | Isolated, synthetic experiment state | Never a production writer or backup/secret holder |
| External signed pointer | `config/state_home_pointer.py` verifies HMAC, host identity and operator-set epoch floor | Location evidence, not writer lease, not a migration permit |
| Cross-host exclusive lease/fencing | **Not established by committed model-facing code** | Independently privileged broker with exact host/VM identifiers, immutable approvals and an old-writer shutdown/fence witness |

**Startup on missing state:** `CanonicalSQLiteGuard`, `RuntimeStorageLayout`, Debian systemd runtime and protected identity `REQUIRE_EXISTING` must refuse silently creating another Sofía. A stale backup/pending pointer cannot promote itself. No automatic writer election, no multi-host SQLite WAL on SMB/NFS, and no LLM text as host-admin authority.

## 2. Privileged operator cutover state machine (CA-3704, 5202, 6105, 6108, 6805, 6809, 6810, 6811, 6812, 6813, 6817)

Only an externally authenticated privileged controller can advance these stages. Each stage requires an immutable operation ID, exact source/destination Fleet and VM identities, principal, operator-signed scope, timestamp/expiry, monotonic epoch and evidence references:

| State | Mandatory evidence before moving forward | Failure/rollback semantics |
| --- | --- | --- |
| OBSERVE | Read-only inventory of canonical identity, source host, local SQLite path/inode, OS service owners, external asset catalog, key owners, destination filesystem and headroom | No mutations or leases; missing trust means unavailable, not a fresh state |
| QUIESCE_REQUESTED | Owner consent to stop consequential actions; ACT outbox disposition; LIFE/RUN/Fleet and Discord workers drained; no unreceipted external effects assumed undone | Fail closed, leave current owner unchanged; outstanding remote actions become UNKNOWN |
| SOURCE_FENCED | Independently observed physical/hypervisor/guest service stop or exclusive lease barrier **from outside both runtimes**; proof old writer cannot resume with the prior epoch | Loss of this witness aborts; a configuration flag or local SQLite lock is insufficient |
| SNAPSHOT_VERIFIED | SQLite online backup, encrypted manifest hashes and protected identity, external erasure-journal exact head, independent backup copy verification and restore-key availability | Candidate remains nonactive; never transfer a live `-wal` file copy as canonical truth |
| STAGED_NONACTIVE | `stage_verified_state_home` checks every manifest asset and current erasure journal; atomic rename only to absent, approved, local destination; unknown/crash durability is `StateHomePublicationUncertain` | Inspect/quarantine visible uncertain candidate; no blind retry or overwrite |
| PENDING_SIGNED | `prepare_pending_state_pointer` revalidates trusted staging paths and independent approval, emits signed `*.pending.json` only | HMAC authenticates bytes, **never** lease/activation; existing pointer remains active |
| COMMIT_AUTHORIZED | Privileged broker revalidates still-fenced old writer, current deletion head, exact staged identity and candidate hash, local durable pointer/key rights, epoch and owner confirmation **after** staging | If witness stale or evidence incomplete, remain fenced/nonactive and escalate |
| ACTIVE_VERIFIED | External broker publishes active signed pointer durably, starts exactly one nonroot Debian runtime, verifies same constitution/identity, canonical SQLite, SAFE/GOALS/ACT/MAIN/Discord receipts and a controlled test write under new epoch | If first write has occurred, do NOT simply roll back by copying an older image: new state could be lost or revoked data resurrected |
| OLD_COPY_RETIRED | Only after independent backup retention/failback plan, privacy audits and client re-pair; old files are guarded read-only, never a dormant auto-resuming service | No automatic deletion of old canonical source; explicit separate high-impact owner authorization required |

**Atomicity boundary:** The offline `BackupEngine.restore` publishes per-file assets and may return `RestorePublicationUncertain`; only the owner-approved staged-home path offers a non-active whole-directory publish. A signed pending pointer and a verified restore are **not** a distributed transaction. A true cutover requires an external fencing/pointer-promotion broker not yet established.

## 3. Failure classification and compensation policy (CA-3702, 3703, 3706, 3708, 3710)

| Example | Saga class | Permitted recovery |
| --- | --- | --- |
| Read-only fleet/docker/HASS inspection | Retryable-idempotent read when fresh session identity is verified | Retry within bounded timeout; report unavailable if no evidence |
| Prepared but unactivated encrypted backup or VM package | Reversible local staging | Remove only verified own temporary files after fresh owner review; no destructive cleanup of unknown directories |
| Git file committed or branch policy updated | Externally committed/compensable, not erased by local snapshot | Verify remote commit/ref, review explicit revert, never replay blindly |
| Discord message sent but receipt lost | Externally irreversible/UNKNOWN | Query authenticated provider receipt; no duplicate send without proven idempotency |
| Home Assistant command possibly applied | UNKNOWN remote effect | Query current device and command receipt, do not auto-toggle/undo |
| JMRI power/turnout command possibly applied | UNKNOWN physical effect | Treat as safety-critical; read hardware and require operator before another state change |
| Hyper-V VM start/stop partly succeeded | Compensable only after confirmed exact VM state and separately authorized action | Do not assume VM snapshot reverses external services or network messages |
| Signed deletion journal append, SQLite replay incomplete | Durable irreversible tombstone; idempotent local projection replay | Reapply all signed entries under journal append lock before queries/restore, never revoke silently |
| New canonical writer has already accepted a write | Irreversible cutover barrier without reverse-migration proof | No failback to stale Venus copy. Fence destination first, then operator-approved verified reverse migration or recover newest epoch |

**Failure-resolution decision tree:** distinguish (a) reproducible source defect, (b) test fixture/configuration, (c) stale editable installation, (d) environment-only Windows file lock, (e) no test coverage, (f) unverifiable deployment. Preserve exception chain and canonical receipts. A green rerun is not proof of original failure resolution. Newer commits or an untested source change are not accepted evidence.

**Graceful degraded modes:** canonical unavailable ⇒ no normal conversation pretending to remember, no model-generated authority, no external actions; inference unavailable ⇒ state-only deterministic status and explicitly allowed non-LLM work, no unapproved model fallback; index unavailable ⇒ authenticated exact-source SQL fallback or explicit unknown; remote command uncertain ⇒ owner-visible pending receipt, no blind replay; optional LIFE/creative job unavailable ⇒ defer with durable explanation, never fake output.

## 4. Encrypted backup, archive and long-term recovery contract (CA-5203–5208, 6102–6110, 6806, 6814–6816)

1. The **canonical hot tier** keeps protected identity, permission/revocation evidence, active transcripts, semantic candidate provenance, goals, schedules and archive catalog under one local SQLite writer. Original source bytes are not silently replaced by rolling summaries.
2. **Warm tier** (design gate): compressed, audience-scoped, verified original segments + rebuildable derived search/vector indices; each segment records schema, UTC sequence/time range, source IDs, source hash, media type, byte count, compression, encryption key ID, audience, retention and erasure epoch.
3. **Cold tier** (design gate): encrypted immutable-by-default content-addressed originals/assets with portable open-format manifests and independent checksums. Archives must not violate signed erasure instructions after restore.
4. **Recovery copies:** operator-selected minimum of **two independently verified encrypted snapshots** for the target protected restore where policy requires, with separate failure domains. A NAS share or second path on Artemis is not automatically an independent failure domain; evidence must include independent power/host/media and recovery-key access.
5. **Keys:** AES-256-GCM payloads and manifest authentication exist in `BackupEngine`; the 32-byte backup key and signed state-home pointer HMAC key must be protected outside the state directory. Key escrow, recovery delegate, offline key copy, rewrap method and key rotation ceremony require an explicit owner policy, not an LLM-generated credential. A ciphertext without a surviving key is not a usable backup.
6. **Restore drills:** clean isolated Windows/Linux host, missing/damaged key, wrong host/epoch, corrupt MAC, WAL crash, wrong identity, missing asset, deleted-memory resurrection, partial bundle, failed fsync, unexpected service start and stale channel credentials. Record RPO/RTO measured in the run, provenance of each restored original, no accidental second writer. No workstream test run claims here.
7. **Retention and capacity:** measure canonical DB size, assets, index rebuild headroom, encryption time, SSD wear and growth; stop automatic pruning/rotation if the newest verified copies, journal, encryption keys or protected identity are at risk. Never claim a human-readable export includes all secret/private state merely because transcript JSONL exports correctly.
8. **Portable export:** reuse `ops/recovery_export.py:export_portable_conversations` as a source-backed JSONL format and `BackupManifest` hashes. A complete independent verifier and all media/archive catalog formats still need implementation and acceptance. Future models and OSes must not be required to inspect owner-approved exports.
9. **Hephaestus lifecycle:** workshop guests use synthetic/sanitized inputs only, with approved immutable gold-image hashes, isolated network, bounded workdir lifetime, patched guest OS, expired cert handling, asset quotas and no raw canonical DB/backup keys. Patching and cleanup are not approved by ordinary creative/simulation requests.

## 5. Source-of-truth operations and evidence

- Existing production primitives: `state/canonical_sqlite.py`, `config/state_home_pointer.py`, `config/layout.py`, `ops/state_mobility.py`, `ops/state_relocation.py`, `ops/state_promotion.py`, `ops/backup.py`, `ops/recovery_export.py`, `memory/deletion_ledger.py`.
- Read-only Windows Settings preview: `ui/settings_sections.py`, using the absent destination helper and `relocation_preflight_text`.
- Protected Debian guest services and remote inference: `run/systemd_runtime.py`, `distributed/inference_client.py`, `cognition/fleet_engine.py`; dormant until approved.
- Latest source fixes: Items 82–90 in `docs/development/v18-workstream-2-phase03-06-report.md`.
- Record an append-only external approval/lease witness containing source old epoch, old host fence proof, proposed new host epoch, exact hardware/VM IDs, signed erasure sequence and HMAC-verified backup manifest digest. **This witness/broker is not yet available as a privileged production service.**

## 6. Acceptance matrix to run only when user authorizes tests (CA-3707, 5204, 6110, 6818)

Synthetic first: 1M+ event archives, 50-year date/time/retention simulation, expired principal grants, corrupt FTS, missing key, symlink/junction and directory replacement, disk full, network partition, clock skew, interrupted VM, stale certificate, duplicate source ID, newer erasure after old backup, source host partially alive, and rollback after first write. Then actual operator-supervised Venus C:→D: mock migration, isolated clean-host recovery and only finally explicit production Venus→Artemis cutover.

All drill outputs must include bounded workload, actual p95 read/recovery costs, expected versus observed hash counts, verified independent media, cryptographic approval identities, manual decision points, typed uncertainty classifications and failed-case evidence. **No such tests were executed in the coding phase.**

## 7. Outstanding operator decisions, not guessable from source

- Which independent privileged system holds **exclusive old-writer fencing and epoch issuance**: an operator-controlled Artemis Hyper-V host broker, a separately enrolled third witness, or a deliberately manual offline controller? A witness located solely inside the to-be-promoted guest is not independent.
- Where the **offline recovery key** and backup FIDO2 key are held and who may recover them when Venus and Artemis are both unavailable. Do not store every secret and every encrypted backup in one failure domain.
- **RPO/RTO are now owner-selected engineering targets:** RPO <= 300 seconds, RTO <= 3,600 seconds (Option B, 2026-10-12). See `docs/development/v18-ca-3103-recovery-objectives-decision-2026-10-12.md`. Neither target is met merely by setting these numbers; protected archive retention beyond the existing two-snapshot-per-destination choice, storage cap, independent/offsite failure domains and recovery-key custody remain unresolved.
- Whether/when an independently approved **owner-initiated active pointer cutover** is allowed; no autonomous cutover is currently approved.

**Current safe next action:** continue source-only Phase 03 implementation, independent broker design and deferred fixture authoring. Do not stage/restore production state, update boot pointers, start the Debian guest as a canonical runtime, rotate keys, prune recovery copies or erase any live data.
