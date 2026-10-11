# V18 Workstream 2: phases 03–06 production source report

Date: 2026-10-11. Repository: Crazysodaman/SofiaAdaLyra. Branch: main only.

## Audit boundary and evidence classification

Original source: `docs/roadmaps/Sofia_Companion_Autonomy_Master_Roadmap_V18_Priority_Phases.md`.
Evidence input: `docs/development/v18-task-evidence.json` (read-only; Chat 1 owns global ledger updates).
Project instructions: `AGENTS.MD`, `ROADMAP.md`.

Assigned original IDs: Phase 03 = 46; Phase 04 = 22; Phase 05 = 41; Phase 06 = 73. Total = 182.
Existing ledger baseline in these phases: 31 partial_wiring, 151 unassessed, zero accepted.
These classifications are **not** counts of uncoded behavior. No full 182-task independent
implementation/entrypoint/source-to-sink proof was completed in this source pass.
The exact number of tasks remaining coding-complete is **unknown**, not 182 and not 151.
Do not mark any CA ID accepted or wholly production coded from this report.

## Source observations (not inferred completion)

- `src/sofia/state/canonical_sqlite.py`: existing `CanonicalSQLiteGuard` pins the canonical SQLite file identity; `connect()` requires the previously pinned file. Authorized first-install bootstrap is separated.
- `src/sofia/state/replication.py`: `SQLiteReplicationWitness` and `ReplicatedStatePlane` implement lease/sequence/ack and promotion primitives. They do **not** prove a physical writer-host election or owner-approved failover.
- `src/sofia/ops/state_mobility.py`: relocation preflight and candidate discovery, not an authorized host cutover.
- `src/sofia/conversation/lifelong.py`: `LifelongThreadStore`, per-thread admission, canonical turn uncertainty, original-message linkage, audited historical import and audience-filtered history/page methods.
- `src/sofia/mobile/pairing.py`: independently issued and hash-verified per-device mobile credentials; operator-only enroll/rotate/revoke, generation and audit records.
- `src/sofia/mobile/server.py`: narrow authenticated HTTPS remote transport with device binding; TLS mandatory on non-loopback; bearer rechecked before and after dispatch.
- `src/sofia/mobile/gateway.py`: canonical mobile dispatch, conversation binding, Main history, notifications and sensor ingress. Further caller-to-effect and client-side tests needed.
- `src/sofia/memory/promoted_retrieval.py`: bounded context projection and principal/audience arguments. These do not establish full across-time correction/forgetting semantics.

## Implemented slice: canonical mobile pairing state identity

Source edit: `src/sofia/mobile/pairing.py`
Commit: `388801e718bbdfb45213874b114772b77645e5ef` (`[skip ci]`).

Before: mobile credential store opened `state_path` anew on every operation
using sqlite mode=rw, so a replaced file at the same path could be adopted
silently by a long-lived credential owner.

After: mobile credential store constructs existing
`sofia.state.canonical_sqlite.CanonicalSQLiteGuard`; every operation connects
through that guard and rejects a missing or replaced canonical file.
Route: MobileCompanionServer Authorization bearer → credentials.authenticate()
→ pinned canonical guard → existing mobile_device_credential tables → device
binding → MobileCompanionGateway.dispatch_authenticated().
Other routes: local operator CLI enroll/rotate/revoke/list → store → same guard.

Regression tests authored in
`test/test_mobile_canonical_identity_fencing.py`.
Commit: `10c2a91d2880b545ab9823b802c46ea1190d6506` (`[skip ci]`).
Scenarios: identity-replacing `os.replace`, disappearing canonical file,
auth/enrollment/device-list/active-generation fail closed.

**Tests and CI deliberately not run.** This slice requires test proof before it
counts as production-accepted. No new database, alternate pairing authority,
live relocation or fleet mutation was introduced.

## Additional production slices: 2026-10-11

### Mobile sensor, notification, and gateway writer identity

Production call routes:
- Android `/v1/mobile/sensors` → `MobileCompanionServer.do_POST` →
  `MobileCompanionGateway.dispatch_authenticated` → `MobileSensorStore.record` →
  canonical enrollment check + `mobile_sensor_latest`; `MobileSensorProvider`
  projects eligible observations to the existing ENVIRONMENT service.
- ACT notification enqueue → `MobileNotificationStore` → HTTP claim/ack →
  canonical `mobile_notification` and opaque delivery handles.
- Android chat → HTTP auth → `MobileCompanionGateway.chat` → canonical
  `mobile_turn_receipt` and device/audience/session binding.

The three previously direct mode=rw store connections now use separate
`CanonicalSQLiteGuard` instances pinned at owner initialization. They do not
follow a replaced database after a runtime starts. Their prior existing
schemas and callers are unchanged; no shadow state was added.

Commits:
- `9f6410acd5e996e8da141048deb5be92253e1563` mobile sensors.
- `2cadf2d1313edebea190a73bc6e22dd62ba13eea` mobile notifications.
- `581d659a6fff6c130f9fc1ba0b716f90d2239cc2` mobile gateway.
- `46a4e1a989a700b78ebabf67d49518ec7b972607` existing sensor regression expectation.
- `8eb25e8f4d4d543ecd3f0c742d1c122bee9dd356` additional independent production route regression tests.

CA relevance: CA-6804 (no competing canonical state), CA-6101 (single owner
design), CA-6306 (safe unavailability), CA-4103/CA-4111 (credential-bound
remote gateway). These are **partial engineering evidence only**; no
entire task is declared completed.

### Backup online snapshot source pinning

Production path: configured backup coordinator/BackupEngine.create →
pin existing `CanonicalSQLiteGuard` → encrypted backup staging →
`_sqlite_snapshot(..., guard=source_guard)` →
`sqlite3.Connection.backup` → SQLite integrity check →
AES-GCM payload encryption and authenticated manifest publication.
This closes the direct default `sqlite3.connect(source)` race that could
create an empty replacement source after removal, or snapshot a different
database after an unexpected file replacement.

Commits:
- `33595ddf3d06c4dde4a26fcca78ba90f298d9077` production.
- `6a53d0be66359a786ff045afe4ba58d982a8854f` deferred race regressions.

CA relevance: CA-5202, CA-6105, CA-6404. These remain only partial
evidence pending whole recovery-epoch, archive, key, and restore validation.

**Unresolved**: a pinned file guard is not a distributed writer lease,
fencing of already-open connections, or failover/backup epoch barrier.
Multi-file restore publication is not globally atomic and needs a separate
operator-approved migration/restore procedure. No host move was made.

### Android proactive-notification durable ACK and audience clearing (Phase 04)

Production route:
`SensorSyncService` → `SofiaApi.claimNotification` →
`SensorSyncService.display` →
`SecureSettings.storeIncoming` Android Keystore-encrypted cache →
Android NotificationManager → `SofiaApi.acknowledgeNotification` →
`MobileCompanionGateway.acknowledge_notification` →
`MobileNotificationStore` canonical acknowledged receipt.

Previously `storeIncoming` asynchronously saved encrypted content with
`SharedPreferences.Editor.apply()`, while the server acknowledgment could
complete first. A crash or power loss could therefore lose the private local
preview after the host permanently recorded completion.
Storage and local consumption now require `.commit()` success, and a failed
local save returns false from the service display path, withholding ACK and
letting the existing server-side claim lease expire/redeliver.
Corrupted existing ciphertext no longer becomes an empty inbox or gets
silently overwritten; the UI catches unreadability and retains ciphertext
for explicit recovery. Privacy/paired-server changes only proceed after
durable inbox clear; credential settings also use durable commit.

Code commits:
- `c2806c7fb5fc0daa5875c965e801aba37c7fb386` secure cache.
- `8e1705f66806cd190f7e5d45914d2d56753c2529` Main UI fail-closed.
- `4ccef7a1daea6193f20c40e6d7889a8c217739a5` service ACK boundary.
- `d4341b3ffa669d8f38eeb3efffe247f80af0c03a` device test cases,
  authored, **not executed**.

CA relevance: CA-6303, CA-6304, CA-6306, CA-4109, CA-5303.
This is a focused production fix, not completion of any whole task ID.
Device/host acceptance and offline stress are still pending.

### Android Main conversation paging by serialized byte budget (Phase 05)

Production route: authenticated Android Main-page request →
`MobileCompanionServer.do_POST` →
`MobileCompanionGateway.dispatch_authenticated` →
`MobileCompanionGateway.main_history` →
`SofiaApplication.main_thread_page` →
`LifelongThreadStore.visible_message_page` →
SQLite audience-filtered keyset history →
bounded JSON response → `SofiaApi.mainPage`.

The canonical pager rejects >256-KiB pages and Android also imposes a
256-KB response reader limit. Fixed-count pages containing many valid large
turns previously errored instead of allowing the owner to page through older
messages. The gateway now halves the requested page width when the canonical
owner reports its known byte-budget error or when JSON serialization exceeds
a 192-KB conservative envelope. It preserves the identical cursor and
audience principal, never truncates an original message, and computes the
`has_more` marker from the effective page width.

Commits:
- `262d3cc5c0ecfa3c7f4e38a681fcb546ddbb38b6` production.
- `66052e3fb288dc7228751492675dc600754cecc7` original-message
  and strict audience isolation regression, authored, not executed.

CA relevance: CA-4107, CA-4109, CA-5303, CA-6306, CA-6312.
This is partial proof of those requirements, **not** whole-task acceptance.

### Promoted-memory candidate store loss/replacement fencing (Phase 06)

Production route: `composition.root` constructs
`DurableMemoryCandidateStore(configuration.state_path)` →
`MemorySystem.recall_relevant` →
`retrieve_promoted` →
`DurableMemoryCandidateStore.list_ids/status/get` →
reviewed `memory_candidate` plus original `memory_candidate_source` →
scoped cognitive context in `runtime.response`.
Operator review, promote, revoke, and source imports use the same store.

The store kept an unguarded, long-lived sqlite3 handle; after OS-level
replacement/deletion the old handle could still access orphaned state,
and `open()` could recreate missing state. The owner now pins
`CanonicalSQLiteGuard` on initialization, validates canonical identity
before every store operation, and reconnects only via guarded SQLite
mode=rw after shutdown. Existing isolated test/import first-creation
behavior is preserved for compatibility; production composition already
supplies a canonical state path. This **does not** replace the broader
physical writer-host lease or finish migration design.

Commits:
- `694f8b56a9c41b4bd7fea85f0d178bb04199523b` production store guard.
- `55b28b6c5850d894a8d8040174dc060e51e8308d` restart/replacement
  regression contracts, Windows-safe test selection, **not executed**.

CA relevance: CA-5201, CA-6101, CA-6306, CA-4204, CA-4206,
CA-5603. These are focused implementation evidence, not whole-task acceptance.
Further policy work must forbid accidental first-create outside the authorized
first-install/import flow.

### Imported ChatGPT transcript-evidence source file identity (Phase 06)

Production route: `composition.root` → `MemorySystem` →
`ChatGPTExportEvidenceStore` → principal-authorized
`recall_historical_evidence` → immutable import batch/message tables →
bounded model context. Explicit import CLI saves evidence only and does not
promote it to approved memory.

The evidence store previously opened `sqlite3.connect(self.path)` for
every subsequent search and could recreate the state file after deletion or
read another database after unexpected replacement. It now pins the existing
canonical SQLite identity before the first connection when present, or after
an explicitly new import/fixture is opened, and all later source reads and
writes use `CanonicalSQLiteGuard.connect` (mode=rw). Existing test/import
first-file creation is preserved; restricting all first-installs to the
configuration bootstrap remains a separate work item.

Commits:
- `fbe63fafb2fe42b50f643137dafcd23f21042d15`: live evidence owner.
- `47d0c84a1046eab9fa132264e567a1cc3f416bf7`: regression tests,
  deferred and unexecuted.

CA relevance: CA-5201, CA-5603, CA-4204, CA-4206, CA-6306. This only
closes a directly observed connection/file-identity failure slice.

### Imported memory originals and operator-reviewed promotion fencing (Phase 06)

Production route: source import CLI → `ChatGPTMemoryImportStore`
(original payload + source IDs) →
`ChatGPTMemoryMigrationService.propose_batch` →
`DurableMemoryCandidateStore` (same sofia.db) →
reviewed `promote/promote_batch` → canonical candidate status →
`MemorySystem.recall_relevant` scoped cognitive projection.

`ChatGPTMemoryImportStore` now pins its originally opened SQLite file
and checks its identity before reading/writing through its long-lived
connection. `ChatGPTMemoryMigrationService` similarly uses a pinned
`CanonicalSQLiteGuard` for its short-lived promotion mapping connections.
Replacement and loss cannot silently transplant a reviewed decision into
a different database after runtime initialization. Initial fixture/import
database creation remains compatible, requiring separate first-install
bootstrap policy consolidation.

Commits:
- `d416be97284bfb8d2cda528b22a39918d64924fc` imported originals owner.
- `e22553b45052de7c233ce4521ee6c8ad010fee2a` reviewed promotion mapping.
- `d48688c4e107a19d9a3f624833ff0e2f5adc9e80` deferred regressions
  including safe Windows lock handling.

CA relevance: CA-5201, CA-5603, CA-4204, CA-1703, CA-6306.
No tests executed, no promoted facts changed, no CA status accepted.

### Imported raw transcript audience egress isolation (Phase 06)

Production route:
`runtime.response.respond_with_runtime_context` →
`MemorySystem.recall_historical_evidence` →
`ChatGPTExportEvidenceStore.search_relevant` →
canonical principal-filtered historical import evidence →
`CognitiveContext`.
The privacy matrix previously gated private versus shared, but all
`AudienceKind.PRIVATE` callers with matching principal could retrieve the
source archive automatically. That included Discord DMs, Android-private
and independently re-paired generation-two mobile audiences even though
those devices had **not** been individually granted access to raw imports.

The memory-system egress gate now permits automatic source-archive
retrieval only for authenticated local `local:text` and
`local:terminal` private audiences. Other private audiences return
no raw historical evidence rather than copying personal archives.
Reviewed, promoted, principal-scoped memory retrieval is unchanged.
No permissions, sessions or source archives were edited.

Commits:
- `c2039bd505ef75699b507c25dfdfa7bd5c9b3b0f` production policy.
- `31f1828cdce45ea59163cc6529aa448acacf143d` exact client-audience
  regression cases; **not executed**.

CA relevance: CA-4107, CA-4111, CA-5304, CA-6303, CA-4204,
CA-4206. Future explicit owner-authorized cross-channel export requires
a separate bounded grant mechanism; this change deliberately does not
invent one.

### Recheck memory principal, audience and revocation before final cognition projection

Production route:
`runtime.response` → `MemorySystem.recall_relevant` →
`retrieve_promoted` → scoped candidate IDs and contextual rerank →
`MemorySystem._recall_promoted` →
last `DurableMemoryCandidateStore.get/status` →
immutable `MemoryRecord` handed to the model assembler.

Initial candidate-ID search already applies principal/audience filters,
and the projector checks status. Final assembly previously rechecked
promotion **before** reading the candidate but did not verify its
principal/audience or status *after* the final get. A scope change or
revocation between the earlier reads could therefore be included in the
current turn despite losing its eligibility. Final assembly now rechecks
principal ID, exact audience or explicitly principal-wide audience,
and promoted status again after retrieving the candidate. This is not
a global transaction over inference: a revoke after the context is
already assembled cannot retract an in-flight model request, and such
unavoidable ordering must be covered in live revocation acceptance.

Commits:
- `641509a50a0be07cd2e7ae6c3f196a422b0532ac` production.
- `04277f08cbee6139c1be674aee17a2db43e66b7f` source-race
  regressions, **not executed**.

CA relevance: CA-4204, CA-4206, CA-1703, CA-5304, CA-6306.
The implementation is a focused hardening slice, not complete acceptance.

### Bounded lifelong promoted memory retrieval, canonical source only (Phase 06)

Production caller:
`runtime.response` → `MemorySystem.recall_relevant` →
`retrieve_promoted` →
`DurableMemoryCandidateStore.iter_promoted_summaries` →
canonical `memory_candidate` keyset pages →
deterministic relevance/context top-k →
`project_promoted_memories` (full provenance only on selected IDs) →
final scoped/candidate-status `MemorySystem` recheck → model context.

The old retrieval used `list_ids`, materializing **all** eligible IDs
and then `store.get` for every one, loading source rows repeatedly and
storing an unbounded ranked list. Long-lived promoted archives could
cause memory amplification and poor latency before the context budget was
even applied. The new owner method streams batches of at most 128 summary
rows by stable `created_at,candidate_id` keyset (configurable max 512),
applying existing principal/audience/status filters in SQL. Canonical
SQLite secondary indexes support ordered scans. Relevance is still the
same lexical overlap followed by evidence-authorized context tie-break
and chronological stable order; `heapq.nsmallest(limit)` keeps only the
top k candidates in Python memory. Selected candidates alone load exact
source provenance, undergo status checks and respect the context budget.

Commit paths:
- `2a31a2297d29217dcb9f7e6272ea36d5cbe4e615`: source store
  paged summary iterator and canonical indexes.
- `74afeb4dc7ec859afad0f5c5262dd8e820ccc4cb`: heap-bounded ranking.
- `525fcb9d5c1931bfb6b1307cafef6470cfffa9fc`: deferred tests of
  audience scope, small keyset batches and a late relevant match across
  500+ source candidates; **not run**.

This bounds Python memory (and source-row loads), not overall linear
CPU cost across an arbitrarily large archive. Full-text indexing,
quality tests and latency targets remain open. No new truth database,
shadow vector store or unreviewed memory promotion was added.

CA relevance: CA-304, CA-306, CA-4206, CA-4207, CA-6312,
CA-5603. These remain partial evidence until full source-to-sink
acceptance and deferred tests run.

### Bounded Android HTTP ingress during offline/reconnect storms (Phase 04/05)

Production route: Android HTTPS request → `MobileCompanionServer`
(`_MobileHTTPServer` admission) → per-connection bounded socket read →
verified device bearer → `MobileCompanionGateway.dispatch_authenticated` →
canonical source receipts/operations. Previously, each accepted TCP
connection created another daemon request thread without a concurrency
limit or read timeout. Slow or malicious clients could consume unlimited
threads without producing authenticated work, starving the companion.

The server now admits at most **16** simultaneous request-handler threads,
maintains a socket accept backlog of 16 and sets a 15-second per-socket
read/write timeout. Over-capacity connections are closed before dispatch;
worker permits are reclaimed even when request handling raises.
No caller changes, database relocation, or host exposure were introduced.

Commits:
- `6628c2cb41cb2b3b7742a288581f7003652ceab3` source.
- `09d6020ebe7e67dad2257fac7a368660494d08cc` deferred
  saturation/permission recovery regression.

CA relevance: CA-6306, CA-6312, CA-4111, CA-5306. Tests and CI
**not run**. TLS handshake accept behavior, connection liveness and
end-to-end load measurement remain separate acceptance work.

## Next coding gates by priority

1. Phase 03: verify each canonical storage writer path uses pinned canonical
   state, and distinguish existing state-plane lease from whole SQLite writer
   fencing; design failover around a pending owner decision, never pick a host.
   Exercise recovery paths in deferred tests.
2. Phase 04: source-trace Android outbox to gateway receipt, uncertainty
   handling, bounded offline queue and reconnect ordering; don't promote
   offline model replies into canonical truth.
3. Phase 05: trace desktop/Discord/mobile entrypoints through
   authentication → audience binding → thread admission → canonical sequence
   → generation → durable outcome → privacy-filtered display.
4. Phase 06: trace eligible promoted memories and canonical evidence through
   retrieval and conversation/LIFE callers, temporal corrections, revocation
   and principal/audience isolation. Measure context budget and abstention.

## Hard boundaries

- Canonical single-writer host **UNDECIDED**. Requires owner's selection.
- No live database move, restore, failover promotion or host cutover without
  explicit operator approval.
- Mobile devices require distinct independently authenticated credentials.
- No direct remote client access to SQLite, no concurrent writable replicas.
- Shared bootstrap/application/memory files and the global 700-ID ledger
  are reserved for coordinated non-conflicting integration.
- Avoid calling any task complete without entrypoint → composition → execution
  → effect/receipt → durable persistence trace and appropriate test evidence.
