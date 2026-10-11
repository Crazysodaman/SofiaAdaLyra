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

### Exact authenticated HTTP request framing (Phase 04/05)

Production route: `MobileCompanionServer.Handler.do_POST` →
authenticated per-device bearer →
`Handler._json` bounded body admission →
`MobileCompanionGateway.dispatch_authenticated` →
canonical mobile chat, history, sensors or notification operations.

The parser previously accepted arbitrary `int(Content-Length)` and read
up to that amount; it did not reject duplicate/conflicting
`Content-Length` headers, unsupported `Transfer-Encoding`, or
short reads that happened to decode to a complete JSON object.
The production server now requires exactly one decimal Content-Length,
refuses transfer-encoded bodies, enforces the existing 64-KiB ceiling,
and verifies exact bytes received before JSON parsing or gateway dispatch.
Malformed requests become HTTP 400 and cannot produce canonical actions.

Commits:
- `82b06c8ef47de8b2c4bd5a529fe8a627ce88f6f2` source.
- `473e382f646e307295388bd837a6e123051c0414` deferred HTTP
  duplicate/truncation/recovery regressions; **not executed**.

CA relevance: CA-6302, CA-6304, CA-6306, CA-4111 and CA-6312.
No host deployment or CA acceptance is claimed.

### Durable device-scoped Main read cursors (Phase 04/05)

Production path: `MainActivity.loadMainHistory` displays canonical
newest-first page in chronological UI order → `SofiaApi.acknowledgeMainSeen`
→ narrow authenticated `POST /v1/mobile/main/seen` →
`MobileCompanionServer` per-device bearer verification →
`MobileCompanionGateway.dispatch_authenticated` second auth and
audience/generation binding → `MobileMainSeenStore.acknowledge` →
canonical `lifelong_thread_event` + `conversation_messages` +
`social_session_principal` original source-audience validation →
atomic monotonic SQLite `mobile_main_seen` cursor in the **same** sofia.db.
Response `/v1/mobile/main/page` now includes `last_seen` for the exact
device, private/standard mode, and pairing generation; older page replays
do not regress the cursor. A revoked or re-paired device cannot inherit
prior bearer generation's read status or mark another audience's messages.
Client clock is not used for order. Legacy history without a canonical
sequence is never asserted as read. No source message content is copied.

Committed:
- `d440b3db33c04b99d21cce04d41c7aa5759b71f9` canonical read receipt owner.
- `6a703192a23260c8b4332746c94e9bbc6fd25f75` gateway production composition.
- `0d0e72c467052f7a910a0b6516f183c28f6b2bdf` Android API.
- `3e22ed697979734a160136d9242583f613f3bd8d` Android UI after display.
- `7edee6397bc92e7c82a73aaf626ccb0d43288a4f` deferred regression cases.

CA relevance: CA-4109, CA-6302, CA-6304, CA-5303,
CA-5304 and CA-4111. Still partial per-ID evidence until
device/server tests and concurrency acceptance are run. Project-thread
read cursors and non-Android clients remain outstanding.

### Atomic provenance-preserving reviewed memory corrections (Phase 06)

Production route: an authenticated owner conversation persists source message
→ `ConversationLearningCoordinator` or
`MemoryReviewService.propose` creates `PROPOSED` candidate with original
source provenance → tray Memory panel identifies proposed replacement
and promoted original → owner reads both and explicitly chooses
`Link correction` → `DurableMemoryCandidateStore.link_correction`
records same-scope lineage in canonical
`memory_candidate_correction` table without changing either fact →
owner separately selects `Promote` →
`DurableMemoryCandidateStore.promote` executes `BEGIN IMMEDIATE` and
atomically revokes original plus promotes replacement; originals and exact
source IDs are retained. Other cognitive callers use the existing status
gate and see only the newly promoted candidate. A correction cannot silently
join different principal or audience scopes, and conflicting/competing
replacement links fail closed. The `MemoryReviewService` also exposes
owner-authenticated staged correction linking for non-UI integrations.

Production commits:
- `cbaa51e8a29a4da12d85ced0a200edfee290b4fc`: SQLite canonical
  correction lineage and atomic transition.
- `6989bc5c084f5eccf56b2f30078b58a19c963cfd`: authenticated
  application review owner.
- `eeafacb86acd2c2ed40fdc84e82918f88d27e3a3`: actual tray review UI.
- `29fdde6027b0a9e52dd0f1c83599ddc85ce003cd`: original-evidence
  restart, conflict, scope and rollback regressions, **not executed**.

CA relevance: CA-1703, CA-310, CA-4204, CA-4206, CA-4803,
CA-5802. This is an actual coherent production correction path, though
memory conflict *detection*, external preference/connecome invalidation,
operator accessibility and temporal validity chronology need separate work.
No existing facts were changed in the running system.

### Production composition refuses missing/redirected canonical state (Phase 03)

Before the change `compose(configuration)` entered `create_state_plane` →
`SQLiteStatePlane` initialization, which can create a missing SQLite
database through ordinary connection setup. On a production host configured
with `IdentityBootstrapMode.REQUIRE_EXISTING`, a lost canonical
`sofia.db` could therefore be replaced with a new empty authority before
memory, identity and other owners had a chance to reject it.

The production composition now calls `CanonicalSQLiteGuard(state_path)`
before `create_state_plane` or any other store if identity bootstrap mode
is `REQUIRE_EXISTING`. This refuses missing files, symlink redirection
and an invalid file type. Explicit `FIRST_BOOTSTRAP` creation retains
its existing path for development/first installation only. No host ID,
writer candidate or relocation was selected.

Commits:
- `173c8e6732ec5660b502266759ad41d9e5514740` actual application
  composition entrypoint.
- `faeec5ea19a788db84cab235c0e31d68c00f6041` deferred production
  no-resurrection and symlink tests, **not executed**.

CA relevance: CA-5201, CA-6101, CA-6804, CA-6306 and CA-6404.
This is a concrete safety gate, not complete operator-fenced failover or
migrated whole-bundle restore.

### Portable encrypted backup manifest paths (Phase 03)

Production route: `BackupEngine.create` packs canonical SQLite, protected
identity/constitution, runtime personality/avatar and release pointer →
`BackupEntry.__post_init__` validates logical archive names and AES-GCM
payload basenames → HMAC-authenticated `BackupManifest` publication.
Restore/load follows `BackupManifest.from_bytes` through the **same**
validation before any target files are written.

Previously relative-path checks relied on host-native `pathlib.Path`.
A manifest accepted on Unix could contain Windows backslash traversal,
drive-relative/absolute names, or Windows reserved payload basenames,
leading to cross-platform recovery ambiguity. Entries now use both
`PurePosixPath` and `PureWindowsPath` semantics, requiring a canonical
relative POSIX logical name and single portable payload basename. They
refuse backslash, NUL, Windows drive/UNC, traversal, dot normalization,
reserved Windows names and invalid platform filename metacharacters.
The existing canonical bundle paths remain valid.

Commits:
- `3da1c9875a98f237cc9d150ea31e92267b9084f2` initial portable source.
- `1812f56c5ee880ce5904790393e788953f6526e5` raw separator and
  invalid filename hardening.
- `c02d8e1950022daa76bae546ecbf7b4539e0fd49` deferred regression
  cases covering hostile cross-OS paths and legitimate canonical entries.

CA relevance: CA-5202, CA-5206, CA-6404, CA-6805.
Existing backups were **not** modified, no restore was executed, and
tests are still deferred. Atomic whole-bundle restoration and Windows ACL
recovery remain separate acceptance gaps.

### Correction semantic verification and pinned recovery read (Phase 03/06)

Production route: recovery `SemanticIntegrityVerifier.verify` →
`CanonicalSQLiteGuard.connect` (refuses deleted/replaced state file) →
SQLite integrity check → existing memory/source/social/ChatGPT/fleet/audit
validators → new `_memory_correction_findings` over the canonical
`memory_candidate_correction` lineage → existing read-only findings
report. The verifier flags missing correction candidate rows, cross-principal
or cross-audience links, and a correction promoted without revoking its
superseded original. A manually revoked original with still-proposed
replacement is explicitly a warning rather than silently successful
promotion. Old databases lacking the optional correction table remain
supported without making up replacement evidence.

Production commits:
- `6aad02ae34605d59bc2a1279685069cac22469d1` verifier source.
- `fc4667b2d242f8fb6d499c66283ed0494a4a1c16` deferred
  tampering/cross-audience/replacement tests.

CA relevance: CA-5202, CA-5206, CA-6803, CA-1703,
CA-4803 and CA-5802. **Tests not run.** This proves no recovery by
silent database creation in this reader, not full restoration acceptance.

### Android protected offline Main history, read-only on disconnect (Phase 04/05)

Production path: authenticated HTTPS `/v1/mobile/main/page` →
`MobileCompanionGateway.main_history` audience-filtered
`LifelongThreadStore.visible_message_page` →
`SofiaApi.mainPage` → `MainViewModel.loadMainHistory` →
`SecureSettings.saveMainCache` AndroidKeystore AES-GCM plus durable
SharedPreferences commit (up to 50, 180 KB) →
subsequent verified network IOException (not host HTTP 401/403/etc) →
`SecureSettings.cachedMainPage` exact hostname, bearer fingerprint,
privacy mode and audience-kind match →
explicit `OFFLINE / read-only` Main display.
No offline reply generation, memory promotion, queued actions or canonical
effect claims occur from this cache. An authenticated host denial **never**
falls back to old content. Changing the paired server/token or privacy mode
must durably clear the encrypted Main cache first, and a dedicated
`Clear offline Main` UI action supports owner disposal. Corrupt ciphertext
fails closed rather than pretending there are no messages.

Commits:
- `6db55d8e6833527194ddb75d687e2463d963ced7` encrypted bounded Android cache.
- `c36e3a48396efb3d9305620f6584a5ca3c144912` actual Android
  UI/load/reconnect/privacy re-pair path.
- `28235885be58ca654970f0a7f2a57644a345a405` Android instrumented
  Keystore/restart/host/mode/corruption regression cases, not executed.

CA relevance: CA-6301, CA-6303, CA-6304, CA-6306, CA-4107,
CA-4109 and CA-5304. The user still needs actual Android device tests
and host/network outage acceptance. The cache is local and cannot prove
current host state or override later host revocation while disconnected.

### Current coding integration checkpoint: SQLite open, Android offline grants, portable backup paths, memory corrections

The current source workstream has four additional production routes:

1. `CanonicalSQLiteGuard.connect`: identity pinned at owner construction,
   verified before `sqlite3.connect`, **reverified after** the actual OS
   SQLite open, newly acquired handle closed on replacement before returning.
   Commits: `98d8f1349ef6593652612d2107636de9e667c004`,
   `66b49eef10a62e95f2e77a314ca284c60b831b31` (deferred test).
2. `MainViewModel.loadMainHistory`: network-only failure classifier
   permits an encrypted, pairing-bound, read-only cached Main page solely for
   DNS/connectivity/timeouts; HTTP 401/403, TLS trust failures, malformed and
   oversized replies fail closed rather than revealing a cached transcript.
   Commits: `bb36b63fbf3714969ac224aa4e335fb975087551`,
   `c7f5b9efe0dac8f617091f9a1d0907d8c1904e85`.
3. `BackupEntry` and `BackupManifest`: portable archive names reject
   Windows trailing dot/space aliases, control characters, and casefolded
   collisions across otherwise distinct source filenames. Restore and
   create use these same model validators. Commits:
   `d7c69fd763ae71d6b1fd9a867a5f0137f260f875`,
   `154688663aaf749a8a9bdad419e07f24c7a6d6b5`.
4. `ConversationService` persisted user source → existing
   `ConversationLearningCoordinator` now identifies bounded, explicit
   first-person corrections → `MemoryReviewService.propose` (PROPOSED only)
   → tray `Memory` correction linkage → separate owner-reviewed promotion
   → one SQLite transaction revokes old fact and promotes replacement. Neither
   conversational suggestions nor repeated source events self-promote.
   Commits: `7df3777afe764028de20fa37027b4a4d2537753a`,
   `681d3275e298bd2a28e47cbc616f0add2e5ef6e7`.

**Source-only.** All regression tests are authored but deliberately
**unexecuted**; no CI, Android build, live host deployment or database
migration has been performed. These are focused implementation slices, not
full task-ID or phase acceptance. Owner choice of physical canonical
writer and future live restore/failback remains intentionally unresolved.

### Deferred test-contract reconciliation

Two previously authored behavior contracts were audited and repaired without
executing the test suite:

- A newly paired Android generation correctly begins with **no inherited**
  Main read cursor but may acknowledge a visible message under its own valid
  credential. The superseded bearer is rejected. Test contract:
  `8a08af09d2160114d53e5843126278a58c9840dd`.
- Unlinked memory `promote` still differentiates nonexistent candidate
  (`LookupError`) from an existing non-proposed candidate (`ValueError`)
  while preserving transactional promotion and correction supersession.
  Source: `e7b8214ebf714c86100352943c88d49d02a883ca`;
  regression: `6e5fb155be207b652ed33b6e495c9c3af91b2e0b`.

**No tests, CI, release or live runtime were run.** The original task
acceptance ledger is not revised by this focused workstream, and no
uninspected requirement is marked coding-complete.

### Additional source-verified integration: conversation authority and mobile pairing rotation (2026-10-11)

**SocialSessionStore, Phase 03/05:** all existing bind/get operations now use
`CanonicalSQLiteGuard` to pin the configured `sofia.db` identity.
Previously its raw `sqlite3.connect(str(path))` would open a replacement
database or implicitly create a missing one, potentially losing original
conversation principal/audience bindings. Production
`ConversationService` and mobile `MobileCompanionGateway` already call
the same SocialSessionStore, so their existing real paths are protected.
Test setup that intentionally creates a new empty state now explicitly calls
`bootstrap_canonical_sqlite`. This change neither selects a writer host
nor migrates any live state.

- `2cbba7b5358cdfdecae7e84df44e1bb17f16240d` social owner production.
- `ad8ca7f5c53ff66cf4a43c156ab6676f99b47ee1` social state-loss and
  replacement regression, no execution.
- `6aad136aa2aad110400d241eabcea1f13fe7fc80` mobile Main fixture
  authorized first bootstrapping.
- `d602907e2325ba79afcc20ef87a5e0c0d6f20298` lifelong historical
  import fixture authorized first bootstrapping.

**MobileMainSeenStore, Phase 04/05:** on authenticated
`MobileCompanionGateway.dispatch_authenticated` read-receipt requests,
the gateway now passes the digest of the *actual* verified bearer into
`MobileMainSeenStore.acknowledge`. The same canonical SQLite
`BEGIN IMMEDIATE` transaction that updates the generation-specific
`mobile_main_seen` row now checks
`mobile_device_credential(device_id,generation,token_sha256,status)`.
A bearer revoked/rotated after its first admission cannot write an
acknowledgment into a different generation. Original audience/message
visibility joins and monotonic cursor constraints remain in that same
transaction. No bearer is saved into Main history or a model prompt.

- `1fa866b4b85e99e69a0eeecbb9a68c440dfd9b17` transaction guard.
- `9afb6f3462b42806e68d01da543fa15b1cbd1dfd` gateway bearer wiring.
- `f9f98af5ec0a5cbba25bf8c22ecf52eeb57dcf89` revoked/rotated
  in-flight read receipt tests; authored, not executed.

**Coding status:** these are source-verified focused repairs only.
Original Phase 03–06 has **182 task IDs**, and the separately
maintained shared V18 task ledger remains the only per-ID audit record.
Neither source presence nor authored tests are automatic acceptance.
All tests, CI, Android builds, and host cutovers remain deferred by
operator request.

### Full-text conversation search enforces original audience binding (Phase 05/06)

Production trace: the active `ConversationService._build_request` chooses
`HistoryPolicy.RETRIEVE_SPECIFIC` for the latest saved user message →
reads its current `SocialSessionStore` binding →
`ConversationFullTextSearch.keyword_search` now **requires**
`PrincipalContext` → SQL checks exact
`social_session_principal(session_id,principal_id,audience_id,audience_kind)`
and joins source `conversation_messages` with that same binding before
returning any matched original source. The optional FTS index remains inside
the canonical `sofia.db`, built only by its already-authorized explicit
offline maintenance operation. Unbound sessions do not use FTS; existing
bounded current-session source search remains the fallback.

Previously the FTS public method accepted any arbitrary known session ID
and relied on external callers to enforce identity, while the SQL queried
the index by session alone. A future caller could inadvertently reveal a
foreign audience's transcript. That missing source-boundary check is now
implemented instead of trusting the caller's comment.

Production commits: `fa9b3df2e1d4bf2a333f47a7d588b75a1e59dba2`,
`5b5c0b112d3456c238cdebbd67e54520c9478a5c`.
Deferred original-source/mismatched-audience/unknown-session tests:
`593f47dd42261ffa4c23eb715d6afa237fe6de63`. **Not executed.**
CA relevance: CA-4105, CA-4107, CA-4206, CA-5304, CA-6303.
No live index rebuild, source rewrite, grant or host change.

### Phase 05 authenticated Android project-thread browsing, no shadow transcripts

Production route: `MainActivity` Projects →
`MainViewModel.listVisibleProjects` →
`SofiaApi.visibleThreads` →
authenticated `MobileCompanionServer` narrow route →
`MobileCompanionGateway.dispatch_authenticated` exact per-device bearer →
`visible_thread_headers` →
existing `LifelongThreadStore.list_threads` plus
`visible_events` principal/audience/original binding filter →
only visible existing project titles and Main.
Selecting a project calls `SofiaApi.projectThreadPage` →
`MobileCompanionGateway.project_thread_history` →
`LifelongThreadStore.thread_for` owner check →
`visible_events` exact source visibility authorization →
`visible_message_page` existing canonical keyset/source joins →
shared `_canonical_history_page` byte budget and cursor validation →
read-only Android history display. Project pagination has a separate
client-side selected ID and falls back to an empty final page rather than a
spurious authorization denial. Android cannot create project histories,
modify original source events, send to a project, or mirror another channel.

The API intentionally does **not** transfer private desktop or Discord
projects into a phone simply because they have the same principal ID.
The project title is hidden until at least one original source event is
visible under this phone's exact authenticated audience.
Offline Main caching is still Main-only; no project content is cached.
No new database, shadow thread store, or cloned transcript was created.
Project editing/routing and opt-in cross-device history grants remain
additional requirements and design questions, not implied by this feature.

Commits: `9acd7d0589bcb6f96638c5636f0a88208ae24a33` gateway first route;
`61c4773ab9c64f9040d11e6fecc32754653035d3` exact owned canonical
thread lookup; `575f861d6859a78326d36c85dc6242efb1fb40aa` source-visibility
hardening; `e41ad91232ee112c57bb87ced790cc27b806f988` deferred
source/audience and keyset-paging regression;
`3fbdf51d58d3d93b6c27ba1493afb13cd7b8b1a9` Android API;
`4f8f89049d0f89ade4bb6cb723a3bf2a05b145a8` Android UI.
**Tests and builds deliberately unexecuted.** Original CA evidence remains
partial until regression and privacy acceptance. CA relevance: CA-4102,
CA-4104, CA-4107, CA-4109, CA-4113, CA-5301, CA-5304, CA-5307, CA-6304.

### Restore destination cannot be a redirected local path (Phase 03)

Production route: `BackupEngine.restore` authenticates manifest
and AES-GCM payloads → validates `target_state_path` and every logical
entry's final destination via `_reject_redirected_restore_path` **before**
creating the staging directory or any target file → existing staged SQLite
integrity/schema, Constitution and identity verification →
rechecks each destination and parent after creating the directory and
before `os.replace`. The guard refuses symbolic links and Windows
junctions in any destination ancestor, including `protected/`,
`release-runtime/`, the canonical DB file and the target root itself.
A signed archive alone can no longer redirect protected identity bytes
into an unrelated location through a preexisting directory junction.

Commits: `10fe7d35fe9c65863c7f300b8857a0eeecc5e215` production,
`81837f7d254d300131f47274341e6040638861d4` regression contracts
for symlinked protected path, canonical DB and parent, **unexecuted**.

This is filesystem path preflight/recheck, **not** complete physical
anti-TOCTOU directory-handle enforcement, whole-bundle atomic replacement,
independent operator cutover authorization, or a claim that live restoration
is currently safe. CA relevance: CA-3704, CA-5202, CA-5204, CA-5206,
CA-6105, CA-6404. No backup, host or live canonical DB was touched.

### Phase 04/05: Last-seen markers retract from presentation when source access ends

Actual read path: authenticated Android Main page →
`MobileCompanionGateway._canonical_history_page` →
`MobileMainSeenStore.current(principal=...)` →
canonical `mobile_main_seen` receipt **joined to current**
`lifelong_thread_event`, source `conversation_messages`,
`lifelong_thread` owner, and `social_session_principal` exact principal,
source audience and kind. Deleted source-event links, changed audiences or
absent original messages cause `last_seen=None` on subsequent reads,
not exposure of obsolete original-message IDs. The durable read receipt
is **not deleted**, preserving recovery/reconciliation evidence.

Source commits: `8bc25ecfa048c989a89d3e1c3c5b23e2dd851577` +
`59137b5835f1a1d79652a0440e245d7554274064`.
Deferred source-erasure/revocation regression:
`547079e3c1563b557c04ae6b60ac203f4b752bc9`. Not executed.
CA relevance: CA-4107, CA-4109, CA-4208, CA-5303, CA-5304, CA-6304.
No change to physical writer election, host deployment or original sources.

### Phase 06 reviewed time-bounded memory validity

Production: `DurableMemoryCandidateStore` adds canonical
`memory_candidate_validity` plus append-only `memory_candidate_validity_event`,
with the owner's approved expiry in timezone-aware UTC. Reviewer selection is
exposed in the real tray Memory panel with explicit fact/source display,
timezone input, required review reason, and an independent confirmation.
`MemoryReviewService.set_expiration` is available for authenticated
non-tray operator surfaces and requires owner review.

On recall, the bounded source-scope SQL candidate iterator excludes approved
past deadlines. `project_promoted_memories` and
`MemorySystem._recall_promoted` also recheck current canonical
`is_recall_eligible` at their final projection boundaries, so a newly
expired fact cannot slip through a previously assembled shortlist.
No inferred expiration, autonomous deletion, removal of original sources,
status alteration or unapproved memory promotion occurs. Reviewer-cleared
expiration preserves the full prior review event history.

Commits: `81321dbb085bbb9138b443e5b024ed644be8d905` canonical store,
`c5fdcd779d87d5f275029cf8af25f6e6665eeb4f` shortlist,
`e027da878e180ff2afb191cacd87661d293e4f47` final context,
`67bc7afaa860a0ff99db76d774205a311ff7ad6d` application owner,
`b9caa5141ad3f4288418a156994fc0ca036b2ef8` actual tray UI,
`94aa990c5d83ed12ab0897c34701ffb906d24d8c` deferred regression
contracts. **No tests or live host changes**. Other temporal requirements,
including conflict arbitration and future scheduling, remain separate CA
acceptance slices.

### Phase 03/04 future Artemis-runtime, Venus-inference fail-closed composition

The owner has selected **Venus as the active single writer today** and
**Artemis as the future single writer**, subject to a separately approved,
verified migration. Remote GPU inference remains on Venus. No code in this
workstream moves the existing database or authorizes an active writer switch.

Production configuration path: explicitly operator-provisioned
`SOFIA_SPLIT_INFERENCE_ROLE=artemis_runtime` plus exact observed runtime
and worker Fleet host IDs →
`selected_split_deployment` →
`validate_split_inference_runtime` at
`create_model_lifecycle` **before local model initialization** and
`create_cognitive_engine` **before model routing** →
existing `FleetPlacedCognitiveEngine` with the exact Venus allowlist,
GPU requirement, `local_fallback=False`, `auto_provision_models=False`
and no alternate-model fallback →
concrete `ConfiguredRemoteInferenceClient` →
already pinned-mTLS Fleet inference transport and exact worker operation
grants. An unavailable or denied Venus worker produces a cognitive error,
not local/generated output. Artemis's canonical state and unrelated
non-LLM services remain independent of GPU inference readiness.
Absent explicit role variables, the current Venus path is unchanged.

Source commits: `0ad327e0cc1d6374acc1b517425c36a96d3062ed` role parser;
`e86a2be44361f1c2cee35622b7f1571d1baa94bb` pre-lifecycle gate;
`268ab2f307f87c74a223d665e082b9839928a98a` engine wiring;
`3d6cd477752ee1d452f1b147fa25444698912db8` pinned transport/GPU
restrictions. Regression contracts:
`5a7b1ac262635424cdae674ecd437486b5968503`,
`7c79dc9fa067f45e1cdbbac40131d4062bc5ed30`.
Full decision and future operator configuration:
`docs/development/v18-venus-artemis-topology-decision.md`.
All tests, host startup, model requests, worker enrollment, recovery
cutover and deployment remain deferred. The role gate **does not** supply
cross-host writer fencing or complete whole-bundle failback by itself.

### Phase 03 staged migration distinguishes source and target host

Owner decision: source/current canonical writer Venus, future destination
Artemis after explicit externally verified cutover. Previously
`RelocationAuthorization.writer_host_id` was passed both to
`BackupEngine.create(source_host_id=...)` and to the future signed
destination writer pointer, misattributing a Venus-origin backup to
Artemis. The existing privileged stage now explicitly requires a separate
`source_writer_host_id` (Venus) and proposed `writer_host_id` (Artemis).
It stamps source backup provenance with Venus and verifies the signed
manifest agrees before applying any staged restore; destination ownership
remains Artemis with a separately approved next writer epoch.

Source commit: `99d427d828d4d00b600a7cb724f900ddb0c810e2`.
Deferred isolated/negative regression source/target, bad backup manifest and
fencing refusal: `581dc3cc87e5023d5c0042a0bd9e49195ca99fa4`.
Decision document `d69bf464d49599bb46d8bb9a15dc9fe2dfa5516a`.
No staging, restoration, live DB migration or host promotion performed.
Independent physical writer fencing and accepted failback are still open.

### Phase 03 independent replication witness loss/replacement refusal

Source trace: opt-in `create_state_plane` →
`ReplicatedStatePlane` →
`SQLiteReplicationWitness` outside canonical data targets →
writer lease/epoch journal, replica prepare/acks and promotion operations.
Previously the witness constructor unconditionally made its parent directory
and `sqlite3.connect` could create a missing independent witness,
potentially restarting a split-brain fence at epoch 1. Now runtime uses
`CanonicalSQLiteGuard` and mode=rw pinned file identity on **every**
witness operation, refuses a missing witness or an existing file without
the installed witness tables, and cannot silently replace a lost witness.
First witness initialization is explicit via
`SQLiteReplicationWitness(path,allow_first_bootstrap=True)` for a trusted
offline provisioning/fixture path; normal `state.factory` has no such
first-create authority. Existing isolated tests explicitly opt in.
This witness still fences **only the replicated StatePlane records**, not
every legacy table in full `sofia.db`. Independent witness hosting and
hardware-fenced startup remain unverified.

Source: `cf5062bfc665c6d501beb8833960d6d76b856ac2`.
Fixture: `8a6d8ab741045fadf1b1aa38dd985971dec232e2`.
Deferred loss/replacement/schema/epoch regression cases:
`faa15c29e78a72eb5823060d51c711142b0b5e86`.
No independent witness file was created on a live host, and no
replication/failover was executed.

### Phase 03 replicated startup checks witness before touching data planes

When `SOFIA_STATE_REPLICATION_ENABLED=true`, the production
`create_state_plane` entrypoint now pins the **existing canonical primary**
through `CanonicalSQLiteGuard`, validates the configured replica/witness
paths without resolving away symlink authority, constructs the independent
existing `SQLiteReplicationWitness` **before** any
`SQLiteStatePlane` (and before an optional replica seed), and checks
the primary's file identity before and after explicitly enabled replica
seeding. Missing/uninitialized/replaced witness control-plane state fails
closed instead of initiating new data-plane initialization or secretly
minting an epoch-one writer. Nonreplicated explicit first-install
behavior is deliberately unchanged. This still does not constitute
whole-database cross-host fencing or approve any deployment.

Production commits: `b8f177c83cc9d5f98b69d8a34beed3bc0b3ac23e`,
`04d9d6a0f4d74d54965754708b9343765c30c1ee`. Deferred regression
contracts: `ca5610d597a2c820cd8e78348315a8e10ec8ce90`.
No CI/test run, no witness bootstrap outside fixtures, no live host changes.

### Phase 03 optional replica seed refuses redirected targets and orphaned sources

Production path: explicit `SOFIA_STATE_REPLICATION_AUTO_SEED=true` →
`create_state_plane` existing canonical/witness preflight →
`_seed_sqlite` pins the current primary `CanonicalSQLiteGuard` file
identity, refuses any symlink/junction ancestor of a prospective replica
destination *before* mkdir, verifies the source still matches during and
after an SQLite backup read, validates the staged SQLite integrity, and
rechecks source identity and redirected ancestors immediately before
create-if-absent hard-link publication. The destination is never
overwritten; a replaced original cannot authorize a new standby copy.
Automatic seeding remains disabled by default and is **not** whole-file
failover, witness promotion or Artemis deployment.

Source: `778c6e6920ee9a5d02c3255a94673de7a98fd37c`.
Deferred redirected ancestor/source-swap regressions:
`b63602e74ef6d661c723cf9ccf594b943c7a7e68`.
No replica was seeded on live machines.

### New host-independent source closure: backup inputs, truth in model outages, state home pointer

**Item 31 (Phase 03 CA-5204/5205/6105/6404):** existing
`BackupEngine.create` now preflights the original canonical and protected
asset path ancestors, checks each selected source immediately before file
read, and refuses symlink/junction paths for personality, avatar and release
pointer. `BackupEngine.verify` refuses redirected archive root, signed
manifest/MAC and encrypted payload entries; `restore` repeats payload-path
checks before the second decrypt read. Prevents ordinary accidental/
malicious redirected file sources from silently entering a signed state
bundle, but does **not** establish operating-system atomic openat/O_NOFOLLOW
protection against a hostile same-user process changing paths during a read.
Production `113e132e558732d01ac0dd8b37b76ece4b29f8f4`; deferred regression
`f39de409d1e67bc59f92c238d3aa86538e8a5a93`.

**Item 32 (Phase 04 CA-6306/6307/6311):** real
`FleetPlacedCognitiveEngine.respond` clears prior placement attribution
before each new request. It records `last_host_id` only *after* the
provider actually returns. If previously successful Venus GPU inference
fails while Artemis local fallback is disabled, it raises
`CognitiveEngineError`, does not call the local engine, and does not keep
stale `last_remote=True` / previous host ID. This is execution evidence
truth, not permission to change provider/model policies. Production
`617d84e85da23c487c4cc8674effb05e1fc41577`; deferred regression
`0de67433df44f57d432c8602cedd1d15a7cf5d04`.

**Item 33 (Phase 03 CA-3701/3704/5201 and Phase 04 CA-6311):**
`read_verified_state_home` continues to verify the signed pointer,
exact host ID, epoch and state home. It now also rejects
symlink/junction **ancestor components** for external trust files, state
home, canonical `sofia.db`, and protected identity. The signed state
root cannot be a redirected parent with a plain final filename.
Production `b4c573b834fa26d04bc061490d17d7ecab44c062`; synthetic
signed-pointer regressions `2bf591192b7785a8a218ee9f1fcde2e74b251afd`.

All regression tests are authored only, **never executed**. No live
backup, signed state pointer, witness, network inference host, DB cutover,
VM or permissions were modified. The operator's decision remains **Venus
current writer; Artemis Sofia VM future writer, subject to explicit
independently fenced and approved migration; remote-only approved GPU
inference supplied by Venus**. The 182-ID original task ledger is still
not a verified coding-completion measure.

### Source-only backup archive size bounds (Phase 03 CA-5205/5207/6105/6404)

Existing production `BackupEngine.create` rejects manifests larger than
16 MiB instead of publishing an archive that verification will later reject.
`BackupEngine.verify` checks manifest file size and uses a hard-capped
read before JSON parsing, limits the manifest authentication/MAC record
to 256 bytes, then checks each encrypted payload's on-disk byte size
against the signed `BackupEntry.size + 16` AES-GCM tag before reading
or decrypting. Reads have a final one-byte excess check to detect a
concurrent file growth. `restore` enforces the identical ciphertext
size condition on its second read even after a successful `verify`.
The previous signed manifest, original asset hashes, authenticated AAD,
candidate metadata and user-visible recovery claims remain unchanged.

Production commits:
`0988af6bbecb7a2e461d59219d797937437155e6`,
`c1984077fbdc5a47f26ef64e8d149437023d3c6d`.
Deferred corruption/oversize/re-read and valid-archive regression tests:
`ad2718f4c156ce16da84b0439791190a627cda04`.

The backup format still encrypts one whole file at a time; multi-gigabyte
payload **streaming** and atomic group-level cutover remain unresolved.
Neither source-only code nor authored tests is acceptance evidence.
No live backup/archive or data-plane writer was touched.

### Phase 04/05: Mobile reconnection resolves canonical send receipts without replay

**Original scope:** CA-6302, CA-6304, CA-4109, CA-4110, CA-5303, CA-5306.
This is a real production path rather than a client-only draft helper.

Authenticated existing HTTPS POST
`/v1/mobile/delivery/status` → `MobileCompanionServer` exact
Bearer/device binding and post-dispatch credential recheck →
`MobileCompanionGateway.dispatch_authenticated` exact request schema →
`delivery_status` current canonical credential SHA-256, device,
pairing epoch, original request ID, presentation mode and message SHA-256
→ existing `mobile_turn_receipt` row. No new table, model call,
conversation append, background retry or external side effect.

A current paired device sees **completed** only with a persisted
original `response_json` whose canonical delivery receipt matches
request/device/mode/generation and completed status; malformed/oversized
historical receipts remain **uncertain**. Unknown IDs/old pairing epochs
return `not_found` without disclosing old device data. An exact-ID
different-content attempt is a conflict, not acceptance. Processing,
uncertain and absent rows **cannot** authorize an automatic resend.

Android `SofiaApi.deliveryStatus(PendingMobileTurn)` supplies the
original encrypted-outbox request ID and SHA-256 digest over its
original message and independently verifies the returned signed-scope
logical receipt. `MainViewModel.reconcileUnconfirmed` is an explicit
**check original delivery receipt (no resend)** UI operation. When
authoritatively completed, it durably clears only that exact pending
request and displays the original recorded response; otherwise the
encrypted pending send is kept for owner review with accurate status.
It does not borrow approval, reuse a stale audience or infer that
`not_found` means the host never executed the request.

Production: `0d1bd24471548597989969be324aff0dc09a4a71` gateway;
`c7193760b77a51a3da43650610fe3afb4b0c4c3f` Android API;
`70d13b1299df0a721ecd4d998c53417d063186ef` Android UI.
Deferred scoped privacy, rotation, no-replay, uncertain and field
validation regressions:
`f270dc344d94620dcb93610ba644da697c2a4b3c`.
**Not executed or accepted.** A failed host receipt still requires
human review; no unilateral request resubmission, DB writer cutover,
enrollment or live host change was performed.

### Phase 05: Audience filtering occurs before bounded project-header pagination

The Android `/v1/mobile/threads` route now consumes
`LifelongThreadStore.list_visible_threads(owner,limit)`, which
performs one canonical SQLite `EXISTS` source-visibility query **before**
applying `LIMIT`. The predicate checks the original
`conversation_messages` row, `lifelong_thread_event` source audience,
visibility mode and *current* `social_session_principal` principal,
audience and kind; unreviewed owner ID alone is not source consent.

Previously `list_threads(limit)` was invoked first and filtered by
audience afterwards in Python. 65 unrelated private/newer projects
could bury one older legitimately visible project and falsely suggest
it did not exist. The fix removes that N+1 scan and keeps names hidden
as soon as original audience evidence is withdrawn. It does not create
copies, reveal hidden project titles, merge authorities, or widen the
read-only Android project scope.

Production commits: `25556108fa82ddd753b5b7adbcab07864af215f9`
(canonical source SQL); `6b169364a22cfff9fcee762516ee8d882aa9527e`
(authenticated mobile gateway); deferred limit/erasure regressions
`6b66d2b5462e168f9e2e2591b1680f268154d48a`.
No tests/CI executed, no archive/live host action. Relevance:
CA-4107, CA-4109, CA-5304, CA-6304.

### Phase 04/05: Mobile chat admission and settlement fenced to original bearer epoch

The real HTTPS route `/v1/mobile/chat` supplies the **original bearer**
through `MobileCompanionGateway.dispatch_authenticated` into its existing
durable `chat` source path. The same canonical `BEGIN IMMEDIATE`
transaction that reserves an at-most-once
`mobile_turn_receipt` now verifies
`mobile_device_credential(device_id, token_sha256, generation, active)`.
A token rotated after the gateway's first check but before admission
cannot start a new turn under the new credential epoch. The same check
runs during the final receipt settlement. If the bearer rotated while
a possibly externally effective LLM request was already in flight, its
original receipt is left **uncertain** (durably), and no successful
response is delivered through the now-stale pairing.

This cannot abort effects already committed before mid-inference
revocation. The worker must still support separate cancellation/
compensation where appropriate, and HTTP performs its own final bearer
check. Direct trusted in-process `gateway.chat` compatibility remains;
all externally exposed HTTP dispatches require actual bearer fencing.

Production source:
`ade3330ea44e311bf84e2ecc586f5896e463cbe7`,
`93e9796716bd69b56b946e758ed2cd657082eaa6`.
Deferred pre-claim and mid-cognition rotation regressions:
`61e4b9222a5b2a7868c2c6aec13de92bc55f6a8a`.
Original CA relevance: CA-4103, CA-4104, CA-4110, CA-5304,
CA-5306, CA-6302 and CA-6311. No tests run or live host changed.

### Phase 05: App-level project header egress respects original audience

`SofiaApplication.lifelong_threads_for(principal)` is the real
desktop/Discord-facing thread discovery entrypoint. It previously called
`LifelongThreadStore.list_threads(owner=...)`, which checks only the shared
owner principal. Consequently, a Discord or desktop channel could receive
the **title** of a source-private project that belongs to the same user but
was created under another conversation audience. The production call
now uses the existing `list_visible_threads(owner,limit)` canonical
SQL source-binding predicate rather than introducing a new store or
duplicating original event text. Message retrieval remains scoped through
`visible_messages`; this closes the *metadata* disclosure and correctly
limits after filtering.

Production commit: `075e000f56af5ecd8cae79a7a4f3fa2f273b98f5`.
Deferred real-store application entrypoint regression:
`ce06cb46aaff39cc128ca56dacfeb799935c9a6b`.
No tests/CI run; no channel messages emitted, grants updated or host
modified. CA relevance: CA-4103, CA-4105, CA-4107, CA-4109, CA-5304,
CA-6304, CA-6310.

### Phase 03: Destructive backup retention cannot follow redirected roots

`rotate_backups(root, keep=N)` is a production deletion path called by
backup CLI/topology, separate from archive verification. Previously it
enumerated a caller-supplied root with `Path.iterdir()` and
`shutil.rmtree` without rejecting a symlink/junction *root*, so a
filesystem redirect could cause archive rotation to delete backup-looking
directories outside the operator-selected root. It also lacked a
pre-deletion check for symlinks/junctions within expired archives.

Rotation now refuses redirected ancestors of the selected backup root,
refuses redirected candidate archive directories/manifest paths,
preflights every nested path in **all selected expired backup
directories before the first delete**, and rechecks a candidate before
`rmtree`. A suspicious path fails closed instead of deleting a partial
backup generation. Normal, unredirected archive rotation retains its
explicit `keep` contract and descending name order. This is not an
atomic OS directory-handle fence against a malicious process swapping
a path at nanosecond intervals, and it does not authenticate archive
ciphertext without keys.

Production: `341edcc66b5c0587f499751a8f3de14cd96cf181`.
Deferred redirected root/candidate/nested-source and normal retention
regressions: `af2c69b5a349688e8e72dba000ec41fe2bc0d136`.
No retention command or test was executed; no real backup deleted.
Original CA relevance: CA-5204, CA-5207, CA-6105, CA-6404.

### Phase 04/05: Completed old mobile responses cannot bypass revoked private presentation

The existing canonical completed `mobile_turn_receipt.response_json`
is an immutable **historical execution record**, not a standing grant
to resurface a once-authorized private/adult presentation.
`MobileCompanionGateway._authorize_completed_presentation` now runs
for both exact-ID chat completion replay and the new read-only
`/v1/mobile/delivery/status` recovery endpoint. It checks saved
private-mode scope and whether historic `adult_chat_enabled` and
`adult_avatar_enabled` actually had host approval. If either true
grant has since been revoked, replay is denied. Existing original receipt
and underlying transcript are **not** changed. Standard-audience recovery
does not inherit or require an unrelated adult grant.

Production commit: `4d802ed64363b28dee2116ce00dd652acb05ec3e`.
Deferred end-to-end status/replay revocation and restoration regressions:
`2c0006ee98577714cf3cf0959a26891fc0536536`.
No model call, replay execution, tests, CI or host change performed.
CA relevance: CA-4107, CA-4108, CA-5304, CA-6304, CA-6310.

### Phase 03 item 41: Staged whole-state candidate publishes only after verified restore

Production relocation path: `stage_verified_state_home` first performs
existing operator/fencing approval callback, read-only source/destination
preflight, encrypted online backup and full authenticated manifest/source
inventory checks. Previously it restored each `sofia.db`, protected
identity file and companion state directly to the eventual destination.
An interrupted file loop could leave a **partially reconstructed yet
apparently valid** candidate home there.

The stage now requires a *fresh absent* target directory, creates a random
sibling staging directory on the approved local filesystem, runs
`BackupEngine.restore` with the entire verified SQLite/protected bundle
inside it, checks the returned archive ID and required canonical
`sofia.db` and protected `identity.json` presence, rechecks target
existence/redirection/local filesystem, and then publishes the whole
candidate directory with `os.rename`. Failed stage attempts remove only
the temporary candidate and **never** delete or overwrite the caller's
selected destination. Existing empty homes now require explicit
operator cleanup or a distinct proposed destination, rather than
being silently populated.

This is a safer **candidate staging** step, not automatic migration,
failover, active pointer publication, whole-database cross-host writer
fencing, adversarial filesystem atomic no-replace protection or a durable
rollback. The live Venus sole writer is unchanged. A privileged fencing
broker must still independently gate any actual Artemis activation.

Production: `dd4d525ba4ee00fa72b5d8eac5d40b22ed6a7c99`.
Deferred fixture contract updates:
`e14aa15ae431a2ce5d10c2d1dd81854a2fbd3d9d`,
`a3b3650ebac486af3752dbbef75cefad60b3793a`.
CA task relevance: CA-3704, CA-5202, CA-5204, CA-6101,
CA-6311 (cross-writer handoff intent), CA-6404. Tests/CI unrun.

### Phase 03 item 42: Model-independent, authenticated-backup portable conversation export

**Scope:** CA-5205, CA-5208, CA-6104, CA-6401, CA-6402, CA-6307,
CA-5503, CA-5603. This delivers working source code for ONE portable
conversation/original-source artifact, not a full runtime archive or clean
bare-metal restoration.

Real invocation: `python -m sofia.ops.backup_cli export-jsonl`
requires absolute new output path, 32-byte authenticated backup key,
approved encrypted archive and affirmative
`--approve-sensitive-plaintext` flag →
`BackupEngine.restore` authenticates and verifies a complete offline
temporary SQLite snapshot, never a live WAL filesystem copy →
`export_portable_conversations` opens that snapshot in read-only SQLite,
refuses symlink/junction and unverified remote plaintext destinations and
creates a new `0600` file via exclusive creation →
streams original `conversation_messages` with current
`social_session_principal` binding labels in keyset batches, then
`lifelong_thread` Main/project catalog metadata and separately
`lifelong_thread_event` original source links. Every link is explicitly
reference-only, with available/missing and current audience match flags;
no stale link recreates a source or a cross-channel grant. Footer records
counts and SHA-256 of all preceding exact UTF-8 JSONL bytes.

The stand-alone `tools/verify_sofia_portable_jsonl.py` is **stdlib-only**
(no Sofía runtime, model provider, CUDA, cryptography or network required).
It checks schema, bounded line integrity, source record structure, original
counts and SHA-256 footer. This unkeyed digest cannot authenticate a
maliciously rewritten plaintext export; the original backup's MAC and
AES-GCM verification remain the cryptographic origin gate.
`docs/recovery/portable-conversation-export-v1.md` explains the explicit
operator command, private-data hazard, offline verification and missing
coverage (protected identity/assets, memory tombstones, goals, model/voice
content, writer witness etc.).

Code commits: `a4ab8f8306946d7d4df8212b354f5a764f7e96ea`
(export), `86c564e2b7d295776527689a380098e83709a400`
(CLI), `10c7405b26cfa0e9579c0b4d590754ddd2ef4380`
(stand-alone verifier). Deferred regressions:
`6b9c03cca5869c56013c6c74cf148a53bf1b0c96`,
`e3c27a34cc1c4be0b3d90ba834b891ca12908df0`.
Human runbook: `e0242ec7185fcb11ce21bd4712e02c3d1d02d66e`.

No plaintext export, live backup, test/CI, database move, runtime
startup, certificate or host setting was created/changed. Implementation
awaits cold-restore acceptance on clean Windows/Debian, authenticated
privacy review and full estate-integrity contracts.

### Phase 06 item 43: Application-reviewed memory promotion rechecks current original and local UI scope

The actual Settings memory review panel was using
`DurableMemoryCandidateStore.list_ids(principal_id=...)` with no audience.
This store intentionally interprets an absent audience as
`audience_id IS NULL`, so locally scoped `local:text` proposals created
by normal `ConversationLearningCoordinator → MemoryReviewService.propose`
were **not listed** at all. The panel now lists owner-global plus
`local:text` candidates only; it does not surface another Discord or
mobile audience's private proposals. Local UI promotion is now routed
through `MemoryReviewService.promote` instead of calling low-level
`store.promote` directly. Rejection/revocation and correction ownership
remain store-managed, and pending expired memories remain auditable.

At the application review boundary `MemoryReviewService.promote` now
requires authenticated **private** owner, matching principal and
exact current review audience, then re-reads the original source session's
`SocialSessionStore` binding and
`ConversationOriginalRetriever` exact source messages. An erased,
missing, re-bound, tampered or differently ordered source is rejected
before the existing atomic candidate promotion/correction lifecycle is
called. Historical snapshots inside `memory_candidate_source` remain
evidence but cannot substitute for the current original during the
application review action.

Production: `f1b9a19c1b05fbcecd397a4e850838ee5743cc3b` application,
`1465b973729c293fbce1583fb67c116185304d4a` desktop Settings.
Deferred actual SQLite, binding and source-erasure regressions:
`5bf46f07dd2b2f4ccc233562b3d110b8cd5c9d22`.
Source IDs CA-5603, CA-5803, CA-5808, CA-5901, CA-5904,
CA-5906, and CA-5304.

**Remaining:** a low-level authorized writer could still call
`DurableMemoryCandidateStore.promote` directly, bypassing the
application-level review recheck; full atomic evidence validation across
all store callers, retrospective source revocation at every cognition
projection, source hash/tombstone epochs and end-to-end acceptance
remain open. No test/CI run, operator review action or live
conversation/memory modified.

### Phase 03 item 44: Atomic absence-only publication for Debian Sofia VM staging

The item-41 whole-home staging flow has an additional final filesystem
race gate: `_publish_new_home_without_replacing`. On planned Linux
Debian runtime, it invokes the real kernel `renameat2` with
`RENAME_NOREPLACE` (and handles `EEXIST` as a firm failure), rather
than calling plain `os.rename` that can replace a concurrently created
empty destination directory on Unix. On Windows, native `os.rename`
refuses existing destination folders. Unrecognized platforms or Linux
libcs without the required operation **fail closed** rather than
downgrading to replacement semantics. Both the staged source and
destination ancestry reject symlink/junction redirection immediately
before publication.

This still does not authorize activating Artemis or prove external writer
fencing, witness epoch and signed bootstrap pointer continuity. The
trusted host broker, old-writer shutdown and separate cutover approval
remain requirements. The directory name is no-replace atomic only on
supported platforms, not protected against a hostile process with
permission to mutate the content of the temporary directory before
publication.

Production commits:
`5def6b6052aa328cc1bbb5995d913baf01ae9820`,
`230cf4c04b542bee915c824090a47b73ec728738`.
Deferred Linux race-error, empty/existing target and valid publication
contracts: `b654f739ac878e9a3f88b136b7b918ba982bebd9`.
Original task relevance CA-3704, CA-5202, CA-5204, CA-6101,
CA-6311, CA-6404. No tests/CI or host operation.

### Phase 06 item 45: Reviewed memory remains source-bound at future retrieval

Completes the source check from item 43 for newly application-reviewed
memories, including after restarts and source erasure. The existing canonical
`DurableMemoryCandidateStore` creates
`memory_candidate_source_review` with the **exact original session,
principal, audience, audience kind and review time** only after
`MemoryReviewService.promote` rereads and compares the exact source
message tuple and current authenticated `SocialSessionStore` binding.
The marker persists independently of any model selection; it is a
*stricter recall condition*, never permission to promote by itself.

On future `MemorySystem.recall_relevant` and
`project_promoted_memories`, `is_recall_eligible` now checks the candidate
lifecycle, reviewed expiry and (for marked candidates) every original
source row's continued presence, exact content, role, timezone-aware UTC
timestamp and current social principal/audience/kind. A deleted original,
tampered original, missing source table or changed audience immediately
stops the reviewed candidate entering a cognitive model request. The
candidate and immutable source snapshot remain available for owner audit,
with the original promotion status unchanged. The keyset summary scan
also removes invalidated reviewed candidates **before lexical ranking**
through indexed `NOT EXISTS` current-source checks, so stale records
do not crowd out other eligible memories.

Older low-level/unattested candidate records are preserved rather than
retroactively erased or falsely described as independently verified.
A separate offline owner audit/attestation migration is still needed
for those. The boundary is authority review → canonical source guard →
promoted eligibility → context projection, not an LLM-generated claim.
The source guard does not alter source conversation bytes, bind a
different device, or change original audience grants.

Production commits:
`720203c2b46abb545ab14496f4cbfaf5f1a4d4f5` durable marker and
projection checks; `4dbd4caba0109b969424ca62f3538f27c41b5269`
application integration; `e98fc6bddfa2b6297b78607e3c24ef6cee7a8f8a`
pre-ranking source filtering; `dccd04eccc2999151d58575a9c1e51a5d915f6ab`
timezone proof. Deferred actual canonical SQLite,
source-deletion, audience-rebinding and legacy preservation tests:
`a58d6c0def8898d494f5cf60fc55a5ccf4d72e10`.

**Not tested, CI/deployment deferred.** Original CA relevance:
CA-5603, CA-5803, CA-5808, CA-5901, CA-5904,
CA-5906, CA-5909. Low-level manually promoted legacy facts
need separate human-reviewed adoption; no live user memory modified.

### Phase 03 item 46: Debian persistent-home filesystem positively classified

The real read-only relocation preflight `_filesystem_kind` previously
categorized **every Linux filesystem not explicitly identified as
network-backed as `local`**, including `tmpfs`, RAM disks, ephemeral
container overlay mounts and unknown FUSE/storage layers. A state-home
candidate on such media could appear eligible even though its canonical
SQLite bytes disappear on reboot or storage provenance is unverified.

Linux mountinfo detection now reports `local` **only** for recognized
persistent host-local filesystem families such as ext4, xfs, btrfs,
f2fs and zfs; known SMB/NFS/SSHFS still report `remote`, memory/overlay
and read-only image layers report `volatile`, and unknown/unapproved
drivers report `unknown`. Both the existing
`inspect_state_relocation` and plaintext-recovery export local-output
boundary require the affirmative `local` classification.
The real physical disk, Hyper-V VHDX/checkpoint chain, encryption,
UPS and host storage durability still require privileged operator review;
a filesystem type cannot *prove* persistent hardware.

Production: `df188d617c702483700984f1a4c677a8b1733e0f`.
Deferred Linux synthetic mount-table and state preflight regressions:
`26c404dbb0a1d138a31a9a0122f459454972dde1`.
Portable-export synthetic fixtures explicitly model local approved disks
under Docker/CI's inherently untrusted overlay scratch volume:
`65a1b231528a53cb2f15367bba94289553a4aa98` and
`229206f11fe8e64582224ded6f2ec24084432b15`.
CA relevance: CA-3701, CA-3704, CA-5201, CA-5204, CA-6101,
CA-6401, CA-6807. Tests/CI unexecuted. No disk/VM/host configuration
or live database was altered.

### Phase 04/05: One-snapshot credential and canonical delivery receipt lookup

The existing authenticated `/v1/mobile/delivery/status` recovery
route first establishes an explicit SQLite `BEGIN` read transaction
before checking `mobile_device_credential` and the matching
`mobile_turn_receipt`. SQLite autocommit SELECTs on the same connection
were previously independent snapshots; an operator pairing rotation
between the two statements could have mixed generations. The pinned
snapshot makes the two authorization/source reads consistent, without
holding a write lock for a mobile status request. The existing HTTP
post-dispatch bearer recheck remains an additional denial gate against
a revocation that occurs after the response was generated.

Production `17899509081e13af07902f28af9a0d4cfcec2543`.
Deferred real-gateway SQL transaction-trace regression
`267a56f1bf9bc9e10ce56e97d77849fc58e042f0`.
Source-only change; no tests or live pairing rotation executed.
CA relevance: CA-4103, CA-4104, CA-5304, CA-6302, CA-6311.



### Phase 03 item 47: Durable Linux staged-home publication across crash boundaries

Audited the existing real operator-gated relocation route:
`stage_verified_state_home` → `BackupEngine.restore` authenticated
whole-home candidate and erasure replay → `_publish_new_home_without_replacing`
Linux `renameat2(RENAME_NOREPLACE)` → non-active verified destination.
The restore's file-by-file copies and successful no-replace rename did not
provide explicit Linux file and directory durability barriers. After a
machine crash, an operator could encounter a missing or stale directory
entry despite having been handed a successful staged-publication result.

`src/sofia/ops/state_relocation.py` now fsyncs **every restored regular
file and nested directory**, refusing symlink/special-file substitutions and
traversal or sync errors before Linux publication, then fsyncs the staging
parent. Only after this pre-publication barrier does the existing kernel
atomic no-replace rename occur. Its destination directory entry is then
fsynced (and the source parent too if distinct). If that post-rename
barrier fails, a typed `StateHomePublicationUncertain` exception prevents a
verified-success receipt: the destination is **left untouched for operator
inspection**, never overwritten or automatically activated. No unverified
fallback publication occurs. Windows retains its existing absence-only
rename behavior; no cross-platform power-loss durability claim is made.

Production commit `77176dee094b6799e212b7b5242f5df75a42c3e5`
(`[skip ci]`). Deferred Linux fsync ordering, failure-before-rename,
failure-after-rename and internal-symlink rejection regressions in
`test/test_state_relocation_atomic_publish.py`, commit
`0e58168414f7cf1458c20b4e6dbbf299f1ce2b5e` (`[skip ci]`).

Original CA relevance: CA-3704, CA-5202, CA-5204, CA-6101, CA-6311,
CA-6404. This is source-level crash-durability hardening **only**,
not a whole original task completion or accepted host cutover. The missing
independently privileged cross-host writer-fencing broker, witness freshness,
old-writer hard stop, external journal continuity, rollback procedure and
supervised acceptance are unchanged. No tests, CI or live host/filesystem
operation performed.



### Phase 03 item 48: Reconfirm independent writer fence after recovery staging

Actual Phase 03 `stage_verified_state_home` was checking the privileged
`independently_verify_authorization` callback **once before** the potentially
long backup, encrypted verification, whole-home restore and Linux fsync pass.
A legitimate externally revoked authorization during those operations could
still be followed by successful publication of a stale candidate. The
existing helper now accepts a final authorization callback used by the real
staging entrypoint, and checks it immediately before invoking Linux kernel
`renameat2(RENAME_NOREPLACE)` or the Windows no-replace directory rename.
An unavailable, denied, withdrawn or exceptional late check aborts the
publication and removes only the operator-owned temporary staging directory.
Old state and pre-existing destinations remain untouched.

Production `src/sofia/ops/state_relocation.py`:
`0df0ea680225da6e422aacb4d229732cadd8fcc9` (`[skip ci]`).
Deferred regression `test/test_venus_artemis_relocation_evidence.py`:
`77deed7d9e20775a66aa2305db4388c55d837bf1` (`[skip ci]`),
using revocation after the first approval to prove no candidate publication.

Original CA relevance: CA-3704, CA-5202, CA-6101, CA-6311.
This is a secondary recheck of an **existing independent privileged
verifier**, not an implemented privileged fencing broker. It cannot
atomically bind a remote host shutdown to a local rename or guarantee
the absence of reactivation after the final check. The old writer remains
Venus, no promotion or pointer activation is allowed, and the original
tasks remain only partially coded. Tests/CI **not run**, no live hosts or
runtime/database/credentials changed.



### Phase 03 item 49: Recheck external memory-erasure instructions before recovery publish

Option B deletion authority deliberately lives outside the backed-up home.
The existing `BackupEngine.restore` authenticates and replays erasures,
but the operator-guided `stage_verified_state_home` previously had a
window **after** restoration, through inventory/fsync/publication, in
which a new authenticated erasure could be appended while an older
candidate continued toward publication.

The actual restoration path now creates the existing
`MemoryDeletionLedger` with the operator-held backup cipher and external
journal; before final staging it verifies every **currently authenticated**
candidate deletion against the restored SQLite via the existing read-only
`verify_applied`. It requires the same authenticated journal sequence
before and after this verification. The final privileged-fence check
(item 48) now **also** re-reads the external journal after all Linux
file/directory fsync operations and immediately before atomic
no-replace publication. Any newly appended instruction or inaccessible,
unauthenticated journal fails closed, preserving the source and not
publishing the stale candidate. No journal is created or erased here.

Production `src/sofia/ops/state_relocation.py`:
`a1187fb56ae31fa8ef834c68a398f23db8850782` (`[skip ci]`).
Deferred source-synthetic relocation regressions:
`test/test_venus_artemis_relocation_evidence.py`, commit
`6e498c3036ffdbe225897f2a25fc785942986cac` (`[skip ci]`),
covering candidate with unapplied signed deletion and authenticated
journal advancing after candidate verification.

Original task relevance: CA-5202, CA-5204, CA-6105, CA-6311, CA-6404.
This reduces a late-deletion resurrection window but does **not** prove
the external journal's globally newest generation, provide a cross-host
atomic lock between a journal append and the kernel rename, or enforce
independently privileged writer-host shutdown. A published *candidate*
still has no activation authority. No tests/CI, deletion, migration,
backup pruning or live host operation performed. Task statuses unchanged.



### Phase 04 item 50: Android chat and recovery reuse original paired configuration

Audited the complete phone outgoing route:
`MainViewModel.send` → Android Keystore-encrypted
`SecureSettings.reserveOutbound` (original message/request ID/privacy mode,
HTTPS origin and pairing-token fingerprint) → `SofiaApi.chat` →
authenticated `/v1/mobile/chat` → durable canonical delivery receipt →
`SecureSettings.confirmOutbound`.

Previously `SofiaApi.chat(message,requestId)` received independent
unsaved arguments and reloaded the current phone pairing, rather than
accepting the authenticated, durable `PendingMobileTurn`. The HTTP helper
also independently reloaded the pairing after `chat` or
`deliveryStatus` had already inspected it. Configuration changes between
those calls could silently change the token or privacy audience governing
a previously queued request/recovery lookup.

`SofiaApi.chat` now accepts the **exact persisted pending turn**, matches
its credential fingerprint, HTTPS origin and private mode against one
loaded configuration snapshot before any HTTP operation, and uses its
original message/request ID/privacy mode for request and receipt proof.
The shared `post` helper accepts that same configuration snapshot,
and `deliveryStatus` also uses the snapshot already matched against the
pending turn. `MainViewModel.send` passes the actual result of
`reserveOutbound` to the API, not a reconstituted argument pair.
A changed pairing, origin or mode fails without dispatch; the existing
encrypted pending record remains unresolved and owner recovery is
still explicit. The canonical server remains responsible for independently
validating the bearer at reception.

Production:
- `mobile/android/app/src/main/java/ai/sofia/mobile/SofiaApi.kt`
  `3ec6ceb1092c99e3fedfad2785b867faf5641060` (`[skip ci]`).
- `mobile/android/app/src/main/java/ai/sofia/mobile/MainActivity.kt`
  `4935db28ff4b86a814dd1997cc51153980a5876e` (`[skip ci]`).
Deferred Android instrumented source:
- `mobile/android/app/src/androidTest/java/ai/sofia/mobile/PendingOutboundInstrumentedTest.kt`
  `1a5268bafd4f70be8dd2a401db580cd8aaacd641` (`[skip ci]`);
  rotated token, changed privacy audience and changed origin all refuse
  request dispatch while preserving the original pending turn.

Original CA relevance: CA-4103, CA-4104, CA-5304, CA-6302, CA-6303,
CA-6311. This is a closed **local client credential-snapshot gap**,
not proof that all original Phase 04 tasks are production complete.
No HTTP request, tests, CI, Android build, pairing change or live
runtime change was made during this coding slice.



### Phase 04 item 51: Preserve original admitted mobile credential generation during cognition

Original source: `src/sofia/mobile/gateway.py`. Actual authenticated
`POST /v1/mobile/chat` → `MobileCompanionGateway.chat` writes a
`mobile_turn_receipt` at the currently authenticated credential epoch
under canonical `BEGIN IMMEDIATE`; then the expensive conversation
selection/model path runs outside that writer transaction. Previously,
`_conversation` and `_principal` independently queried
`active_generation`. A rotation during the gap could select the **new
generation's** conversation/memory audience for the **old epoch's**
admitted request, even though final result settlement subsequently failed
because the bearer was revoked.

Production `efb6355c18d507f1c07cdede758342eaba696224`
(`[skip ci]`) threads the original admitted positive generation through
`_conversation` and `_principal` for the entire canonical turn,
including the session binding and cognition principal. A second direct
SQLite original token + device + epoch check immediately before
`conversation.respond` refuses model execution if rotation already
occurred during session selection. Existing post-cognition generation
recheck remains in effect; mid-model rotation preserves an uncertain
old-generation receipt instead of exposing it to the new bearer.
Trusted local callers can continue using current/default generation.

Deferred regression update `test/test_mobile_chat_epoch_fencing.py`:
`e0bb0ce74adb9ef5ae6a7437075894c659744db9` (`[skip ci]`);
it observes a credential rotation after durable admission and before
conversation to require **zero model calls**, an old generation only
session binding and uncertain old request; existing mid-generation test
also asserts old-audience provenance.

Original CA relevance: CA-4103, CA-4104, CA-5304, CA-6302,
CA-6303, CA-6311. **Source hardening only**, not independently
accepted task completion or a physical writer fence. No tests/CI,
pairing, mobile request or host action executed.



### Phase 03 item 52: Serialize signed deletion append against restored-home publication

Previously, `stage_verified_state_home` verified the current authenticated
external `MemoryDeletionLedger` both after restore and immediately before
`RENAME_NOREPLACE`, but a separate operator-authorized deletion could append
a signed record between the final check and the candidate directory rename.
The deletion owner's canonical `MemoryDeletionLedger.request` already uses
`_exclusive()` OS file locking across append and fsync.

Production `src/sofia/ops/state_relocation.py` now takes **that exact
existing journal append lock** around the final privileged-fence + erasure
recheck AND non-activated directory publication. Thus cooperating local
erasure writers cannot add an instruction after the final freshness check
and before the new candidate becomes visible. No second journal, grant,
new erasure authority, or alternate state owner was added.

- Production `576ac9c9f46a5ea0b0a93856ca74f9d289e6ef5a` (`[skip ci]`).
- Deferred fixture lock-root preparation
  `1910cc6cabe6fd002c2d811061242b93ad36233a` (`[skip ci]`).
- Deferred original `MemoryDeletionLedger._exclusive` lock-observation
  regression `test/test_ws2_state_relocation_erasure_lock.py`:
  `01da7dffa5ac6f238184ea879cc6d72c6159ba81` (`[skip ci]`).

Original CA relevance: CA-5202, CA-5204, CA-6105, CA-6311, CA-6404.
This is **cooperating OS-local** journal serialization, NOT independent
remote-host fencing, global journal freshness proof or a writer cutover.
Published candidate remains inactive. Original CA tasks not marked complete.
Tests/CI deliberately unrun; no actual deletion, restore, migration, host
state, certificate or network changed.



### Phase 03 item 53: Crash-durable and unredirected signed pending pointer

The real offline `prepare_pending_state_pointer` artifact previously
fsynced the new `*.pending.json` bytes but not the containing directory.
On Linux, a crash can lose a newly created pathname despite an apparently
successful file fsync. The pending artifact also resolved its parent before
enforcing unredirected original path spelling; a symlink or Windows junction
could redirect the operator-owned pointer output location.

Production `src/sofia/ops/state_promotion.py` now reuses the existing
state-home pointer path guard to reject redirected pending path/ancestors
before exclusive publication. On Linux it fsyncs the parent directory only
after the signed file is durably closed. A post-write parent fsync failure
raises typed `PendingHomePointerUncertain`, leaving the existing signed
bytes intact for independent operator inspection and never attempting
an overwrite. The code still **does not activate** a pointer, promote a
writer epoch or move canonical `sofia.db`.

Production `002eaab8a4746eef73f39f6c6b90a2fe196a0c4e`
(`[skip ci]`); deferred no-live-host regression coverage
`test/test_ws2_pending_home_pointer_durability.py` at
`0807dd8a220d8a478d2138426fa5bc8d2efc5be8` (`[skip ci]`),
including successful parent sync, uncertain post-write failure retained
for owner reconciliation and redirected trust parent refusal.

Original CA relevance: CA-3704, CA-5202, CA-5204, CA-6101,
CA-6311, CA-6807. This is one **operator handoff artifact** slice,
not global writer fencing or original-task completion. Tests/CI unrun;
no actual host, service, migration, key or active pointer changed.



### Phase 05 item 54: Completed canonical Main replay needs current originals

The real `ConversationService.respond`, owner-tool-result and guarded
special-response routes all use `LifelongThreadStore.admit_turn` before
dispatching another model/tool action. Previously an exact duplicate
`event_id` with `canonical_conversation_turn.status='completed'`
returned `response_json` based on its durable digest and current session
binding alone, even after the original user/assistant message or its
`lifelong_thread_event` Main audience link had been erased or withdrawn.
A stored receipt is important audit evidence but cannot itself restore
deleted source content or revoke a subsequent deletion.

Production `src/sofia/conversation/lifelong.py` now verifies the two
original source message IDs, their user/assistant roles, exact source
session, current Main thread owner, exact audience visibility, durable
canonical sequence and turn position **inside the same canonical
`BEGIN IMMEDIATE` snapshot used for duplicate turn admission**.
It also compares the original assistant text to the settled response and
rejects unreadable serialized response data as uncertain. Missing or
changed source/links raise `CanonicalTurnUncertain` without replaying
the model, returning deleted text or altering original completion
evidence. A valid existing completion still returns the original
response and sequence. Owner-tool-result calls are also supported:
their user message is an action description while the admission digest
binds an additional result hash, so the replay guard does not incorrectly
require literal equality of those different legitimate strings.

Production `22e953989cf276fc384468beecdf5d0b7d9aeb73`
(`[skip ci]`). Deferred synthetic canonical SQLite regression coverage in
`test/test_ws2_completed_main_replay_source.py`,
`554aaedf441633d25e6e1c93f294139bfe017436` (`[skip ci]`):
source deletion, assistant deletion, withdrawn Main link, modified
assistant original, and intact original replay.

Original CA relevance: CA-4107, CA-5302, CA-5304, CA-5306,
CA-5503, CA-5505, CA-5603, CA-6306.
No source restoration or accepted task status implied. No tests/CI
executed, no live messages, database or grants modified.



### Phase 03 item 55: Flush restored file and path durability before recovery success

The real offline `BackupEngine.restore` verifies the AES-GCM/MAC
archive, authenticates and replays the current external memory-deletion
journal in a private temporary directory, validates recovered SQLite
and protected components, then copies each restored file into an
operator-selected target via `shutil.copy2` plus `os.replace`.
Previously it could return `RestoreVerification.succeeded=True`
without explicitly fsyncing those newly copied bytes or restored
directory entries. A successful rename alone does not prove recovery
survived a sudden power loss.

Production `src/sofia/ops/backup.py` now **fsyncs each copied
temporary file before replacing its target**, then on Linux fsyncs
all touched destination-parent directories and ancestors deepest-first,
refusing redirected or special-file directory entries. A failed
post-rename directory flush raises typed
`RestorePublicationUncertain`: restored files might already exist,
but callers cannot report verified successful publication or silently
assume rollback. Existing external erasure replay, authenticated manifest,
and restore source guards remain intact. Other platforms still perform
the file-content fsync, but **do not** gain an unsupported claim of
durable parent-directory publication. This remains a **file-by-file**
offline restore, not an atomic live state-home cutover. Item 47's
whole-home publication barrier still protects a separately staged
candidate.

Production `f03ab4e6fe33990724c184902f7d2ea6c3e422ae`
(`[skip ci]`). Deferred real encrypted-archive restore regressions in
`test/test_ws2_backup_restore_durability.py`:
`f9b6d2b4c599c08030839bf239e2cb37bcb643b7` (`[skip ci]`).
Coverage: temp bytes flush before each rename, parent directory flush
after publication, pre-rename fsync abort, post-rename fsync unknown.
No tests/CI or live restore executed.

Original CA relevance: CA-5202, CA-5204, CA-6105, CA-6401, CA-6404,
CA-6807. Original statuses remain partial/unassessed pending exact
source-to-sink reconciliation and final acceptance.



### Phase 03 item 56: Reject predictable temporary-restore symlink escapes

Follow-on source audit of item 55 exposed a genuine write-through-path
risk in the real `BackupEngine.restore` execution route: the original
`shutil.copy2(source, destination.with_name("." + name + ".restore"))`
wrote through a **predictable** pathname before performing the final
destination-path checks. A preexisting symlink at that internal filename
could redirect authenticated plaintext restore bytes to an unrelated
host file outside the owner-selected offline recovery target.

Production `src/sofia/ops/backup.py` no longer opens that alias.
Each restored output uses `tempfile.mkstemp` inside the checked
destination parent, with an unpredictable `*.restore-*.tmp` pathname,
exclusive creation and a held file descriptor. The verified staging
source is copied into that new file, flushed and fsynced **before** a
final-path recheck and `os.replace`. Cleanup removes only this exact
randomly created temporary file; a preexisting predictable symlink
cannot receive any copied bytes. No restore destination is created
from model output or linked to a live runtime.

Production `06f90bc761cd75bbfa33c258b32b456ba1e80c9a`
(`[skip ci]`). Deferred durability ordering regression updated for
exclusive random temporary names in
`test/test_ws2_backup_restore_durability.py`,
`6dc7beb191ea61d30d2074f4494c2712387552e7` (`[skip ci]`).
Additional synthetic hostile preexisting `.sofia.db.restore` symlink
regression `test/test_ws2_backup_restore_temp_symlink.py`,
`d9096d7024302c6d75120fb583e7de2c1336d6ff` (`[skip ci]`),
verifies an unrelated outside file stays byte-for-byte unchanged while
the real archive restores inside its selected local root.

Original CA relevance: CA-5202, CA-5204, CA-6105, CA-6404, CA-6807.
This closes the **predictable temp alias** in the actual offline
restore route, not the broader adversarial host-privileged directory
replacement problem (which still requires dirfd-based filesystem trust,
offline operator fencing and real host acceptance). No tests/CI or live
backup, migration, restore or deletion executed.



### Phase 06 item 57: External signed-erasure lock and append resist redirected files

A live-path audit of `MemoryDeletionLedger.request` found that its
cross-process append lock opened a predictable `.jsonl.lock` path and its
journal append reopened the signed `.jsonl` path using ordinary pathname
operations. Checking `is_symlink()` only before opening leaves a
check-to-open substitution opportunity. On Linux an attacker with file
replacement authority could redirect append/lock operations to another
local file or cause two writers to lock different inodes.

Production `src/sofia/memory/deletion_ledger.py` now validates
symlink/junction ancestry and on supporting platforms uses
`O_NOFOLLOW` with `O_CLOEXEC` to open the lock and append file.
After open, it verifies a regular file and exact inode/device identity
against the named path before trusting the lock or writing signed bytes.
The encrypted/AC-authenticated append format, exclusive lock, signed
sequence, scope checks and fsync semantics remain intact. This is a
local-filesystem guard, **not** an independent privilege boundary against
an OS administrator, a malicious parent-directory rename, a stale
journal swapped with another authentically signed copy or cross-host
writer fencing. Windows reparse trust still needs a privileged service.

Production commit: `e4107714f6214fb6b00e2319c41e6f3e31ec4c0f`
(`[skip ci]`). Deferred synthetic no-follow and original-HMAC-chain
regressions: `test/test_ws2_deletion_journal_nofollow.py`,
`a9ef8f8f387b14b36aa9b7f2c11bb58dcb44f0bb` (`[skip ci]`).

Original requirement relevance: CA-5202, CA-5204, CA-6105,
CA-6108, CA-6404, CA-6807. No live erasure, host changes,
automatic migration, tests or CI. The original task IDs are not
marked accepted by this focused coding slice.



### Phase 03 item 58: Hold external memory-erasure append lock across offline restore publication

Audited the actual `BackupEngine.restore` path (distinct from the
operator-staged relocation wrapper hardened in item 52).
It replayed and verified the independently authenticated memory-deletion
journal against its temporary SQLite candidate, then checked the external
journal once more **before** a potentially long file-by-file copy into
the selected offline recovery target. A fresh signed deletion could
be appended just after that check and before the backup's old data
finished publishing. This was a real local deleted-memory resurrection
window when an authorized deletion writer and offline restore shared
the journal's local failure domain.

Production `src/sofia/ops/backup.py` now takes
`MemoryDeletionLedger._exclusive()` around the final authenticated
journal comparison **and** the complete offline restore publication,
including file replacement and Linux parent-directory fsync. It reuses
the existing lock taken by the real `MemoryDeletionLedger.request`
append path, so cooperating local writers cannot advance the deletion
chain during publication. Restore still fails closed on journal
changes, missing authenticated records, broken replay or durability
errors; failed restores do not authorize runtime activation or erase
the journal. It is intentionally a lock that may delay a local
deletion while a large offline restore finishes, not a claim that
SQLite and all archives have acquired distributed transactional atomicity.

- Production `5231e2de88a288e8e9f32a7b94a27a3bfbc37981` (`[skip ci]`).
- Deferred encrypted-archive fixture `test/test_ws2_restore_erasure_lock.py`,
  `75e25ead859ca18f2c0bc45dea87e2e757c59eb3` (`[skip ci]`).
- Original relevance: CA-5202, CA-5204, CA-6105,
  CA-6108, CA-6404, CA-6810.

No distributed fencing, independent globally current journal head,
host/VM migration, tests, CI or live change is claimed.
Original V18 task statuses remain unchanged.



### Phase 03 item 59: Default offline restore never replaces existing bundle assets

The original `BackupEngine.restore(replace_existing=False)` guarded
only the canonical SQLite target: if `sofia.db` was missing in an
otherwise populated recovery directory, the engine could silently
overwrite `protected/identity.json`, Constitution, personality and
other restored files using `os.replace` while still claiming no
existing state was replaced.

The **real production restore path** now preflights every authenticated
manifest destination for preexisting files before decompression or
copy publication. In default no-replace mode, it uses filesystem
create-if-absent **hard-link publication** for each already fsynced
randomly staged temporary file: a file appearing between the preflight
and that individual publish fails closed without overwriting the
intervening owner's bytes. Explicit `replace_existing=True` retains
the existing reviewed replacement operation, which is still a
file-by-file offline restore, **not** a whole-home atomic cutover or
permission to overwrite the active state home. Unsupported filesystem
hard-link behavior fails closed rather than downgrading to an
overwriting rename.

Production: `src/sofia/ops/backup.py`
`da0d43f0aaa1696bbd526782a42da0cda01ad553` (`[skip ci]`).
Deferred regressions:
- `test/test_ws2_restore_whole_bundle_no_replace.py`
  `5df7cbb06fe05a643c8edfedf130a1678c3c01f6`:
  protect an existing identity even when SQLite is absent, reject
  another writer creating a target during publication, and preserve
  explicit reviewed replacement support.
- `test/test_ws2_backup_restore_durability.py`
  `52a17d470da5656a95aab467a3bbe0246abc1bb7`;
  `test/test_ws2_restore_erasure_lock.py`
  `7a611df286e194deaea48c2335612c20cd48f68e`:
  deferred durability/lock assertions now inspect the actual
  absence-only publication primitive rather than old `os.replace`.

Original CA relevance: CA-5202, CA-5204, CA-6105,
CA-6404, CA-6807, CA-6810. No tests, CI, active host restore,
database move, backup replacement or activation performed. No
original V18 task formally accepted.



### Phase 04 item 60: Mobile read requests cannot migrate between credential epochs

The owner-authenticated `MobileCompanionGateway.dispatch_authenticated`
gateway originally authenticated a phone bearer first, then each
independent read handler (`state`, Main page, project-thread metadata
and history, last-seen, notification flow, etc.) could query the
current device generation later. An operator could rotate a pairing
while a request was queued or reading Main. The old caller could
resolve the **new** credential generation's audience or obtain a
private response after its own token was revoked. The earlier item 51
covered chat cognition but not these normal authenticated read paths.

Production `src/sofia/mobile/gateway.py` now takes an atomic
`mobile_device_credential` row observation matching the **actual
bearer digest, device and active generation** at request entry.
A per-request `ContextVar` pins that exact generation for session,
principal, chat admission, Main paging cursors and Main read receipts;
direct trusted host calls outside the HTTP dispatcher preserve their
existing current-generation contract. The entire real route dispatch
runs in this scope. Before returning ANY result, it rechecks that the
exact original bearer and generation are still active and fails
closed on a rotation or revocation. The existing `MobileMainSeenStore`
still independently verifies credential hash and epoch in the same
canonical write transaction as acknowledgment.

Production: `23480791f9b59fc95d4f580ee21e383b0565b09a`
(`[skip ci]`). Deferred canonical SQLite regression:
`test/test_ws2_mobile_read_epoch_pin.py`,
`1418acc7bc89f1742416a0a59ac2b9044775d73e`
(`[skip ci]`). Covers mid-query rotation (old bearer denied
and old audience pinned) and stable original-bearer Main replay.

Original CA relevance: CA-4103, CA-4104, CA-4107, CA-4109,
CA-5303, CA-5304, CA-6304, CA-6310, CA-6311.
This is request-level authentication and presentation hardening, not
an atomic HTTP byte-send plus credential-revocation transaction,
revocation of already rendered content or an accepted full Phase 04.
Tests/CI and live phone/host pairing or database operations unrun.



### Phase 04 item 61: Exact original bearer epoch fences mobile notice claim and ACK

Audited the actual owner-authenticated Android notification route:
`/v1/mobile/notifications/claim` → `MobileCompanionGateway` →
`MobileNotificationStore.claim_next` (durably marks claimed) and
`/v1/mobile/notifications/ack` →
`MobileNotificationStore.acknowledge` (marks displayed and can
complete an ACT outreach receipt). The dispatch-level bearer check
and item-60 final recheck were not sufficient for a state-changing
operation, because an operator could revoke/rotate the paired bearer
just before the notification's SQLite transaction yet the old
request could still durably claim/ack a notice.

Production `src/sofia/mobile/notifications.py` now accepts an
exact, optional original authenticated `generation` +
`credential_sha256` pair, and validates both against the live
`mobile_device_credential` row **inside the same `BEGIN IMMEDIATE`
transaction** that claims or acknowledges the notification.
Incomplete/incorrect credential-epoch pairs fail closed; trusted
in-process callers that pass neither retain their previously
separate host authority. The real authenticated gateway now passes
the original request-scoped epoch and fingerprint directly from
item 60's verified context to both live notification operations.
An invalid old bearer cannot commit a newly claimed or displayed
state or falsely settle the associated ACT recipient receipt.
Existing duplicate-ACK and redacted-preview behavior is retained.

- Production transaction gate:
  `f039aa3132bc356e9203ff9cb152b7a62ebc2252` (`[skip ci]`).
- Real gateway composition:
  `4db268c39368d44f8458c52718536a3ade1ec013` (`[skip ci]`).
- Deferred synthetic canonical database regressions:
  `test/test_ws2_mobile_notification_epoch_fence.py`,
  `b78f059b2175a88228cc9820bccec4ddc89bb176`
  (`[skip ci]`): rotation before claim, rotation before ACK,
  and original-bearer success.

Original CA relevance: CA-4103, CA-4104, CA-4109,
CA-5303, CA-5304, CA-6302, CA-6304, CA-6311.
This is a credential-fenced delivery transaction, **not**
cross-host failover or a guarantee that previously displayed phone
content can be retracted after revocation. Tests and CI unrun;
no actual notification, mobile pairing or live host changed.



### Phase 04 item 62: Notification ACKs cannot inherit a prior pairing claim

The exact-bearer transaction guard from item 61 was necessary but
insufficient for newly re-paired phones: `mobile_notification` retained
only a hashed device ID for the outstanding claim. A later bearer
generation for the same device could acknowledge an older claim,
producing a durable `displayed` state and potentially an ACT delivery
receipt without having reclaimed that notice after re-pairing.

Production `src/sofia/mobile/notifications.py` now migrates existing
canonical `mobile_notification` tables with a nullable
`claimed_generation` column, and records the authenticated generation
in the same transaction as a claim. A remote ACK requires **both** a
currently active original bearer/generation (item 61) **and** that the
notice's persisted claim generation matches it. Previously claimed
legacy/null rows cannot be ACKed remotely without first expiring
and being legitimately reclaimed; expiry clears the old device and
generation together. Previously direct trusted host callers retain
their separate local authority. The durable original notification ID,
at-least-once queue and opaque delivery handle survive this migration.

Production: `def47f49932e48ddff73be8256cd64eb7497e718`
(`[skip ci]`). Deferred synthetic re-pair/old-claim/lease-reclaim
regression source in `test/test_ws2_mobile_notification_epoch_fence.py`,
`c494b5290ceea4cda9f0a01b61985d5d6a202efe`
(`[skip ci]`). The additional regression has not been run, and
its future-time claim simulation should be reconciled with
monotonic mock-clock fixtures in the final test campaign.

Original relevance: CA-4104, CA-4109, CA-5303,
CA-5304, CA-6304, CA-6309, CA-6311.
No live pairing, delivery, host cutover or test execution performed.



### Phase 06 item 64: Privacy-first automatic memory candidate admission

Source audit of the real `ConversationLearningCoordinator.observe_user_message`
path found that `_is_learnable()` accepted exact user phrases matching
`remember that` or `my ... is` without rejecting passwords, PINs,
one-time login codes, recovery codes, API keys, private keys, access
tokens, client secrets, bank-account numbers, or government identity
numbers. The coordinator wrote a second durable `PROPOSED` memory
candidate containing the original message bytes, even though final
promotion still required authenticated private owner review.

The existing coordinator now applies a bounded conservative
sensitivity filter **before** auto-proposing a source-linked candidate.
It declines automatic candidate creation for high-risk credential,
authentication and identity strings while leaving the original
authenticated conversation record in its existing retention/audience
store. It neither deletes that record nor incorrectly claims to
sanitize arbitrary messages or prevent an explicitly authorized
manual review workflow. Ordinary first-person preferences and
reviewable corrections still use the original existing coordinator.
No new memory schema, independent memory owner, or model classifier
was created.

- Production `src/sofia/application/conversation_learning.py`
  commits `0e80de8c952e8b57495f0c7b41d44097de2d9772` and
  `7254eb6716bd7a727acffdee0400e0a23ce6ea4e` (`[skip ci]`).
- Deferred source + synthetic canonical end-to-end regressions
  `test/test_ws2_memory_private_admission.py`:
  `d7844f34787559808b3470efd3e3a88a9dceeb5b` (`[skip ci]`).

Original CA relevance: CA-5803, CA-5804, CA-4806, CA-4204.
Sensitive third-party and medical material, already-written historical
candidates, device-local caches, offline archives, file logs and
generic PII classifiers still require separate scoped audit and
acceptance. No tests/CI, live messages or user data changed.
The original requirements are **not** accepted.



### Phase 06 item 63: Bounded normal-turn wardrobe history

Live `ConversationService._respond_once` had an unconditional
`ConversationStore.list_messages(session_id)` after every source user
turn, independent of the already bounded `_build_request` LLM
window. The result was scanned only for earlier user/assistant
utterances used by wardrobe generation and clothing resolution,
so it needlessly materialized an entire potentially multi-decade
session for ordinary conversation. Production replaced that hot-path
read with `recent_messages(session_id, limit=64)`, reusing indexed,
audience-preserving canonical SQLite storage without deleting,
summarizing or replacing original messages.

Production `03ff01b5d9103322ff91246cb368b357c1f54b76`
(`[skip ci]`); deferred long-session regression source
`test/test_ws2_bounded_wardrobe_context.py`
`02d191832272a514a7a822f4fa663d484920428e`
(`[skip ci]`). The synthetic fixture asserts no hot
`list_messages` call and the unchanged prior-user follow-up.
Original relevance: CA-4201, CA-4207, CA-5001, CA-5601, CA-5603.
No tests/CI or live conversation was executed. Explicit full
transcript exports remain separate owner-directed behavior.

### Phase 06 requirement-level audit: 16 inspected, 15 newly partially assessed

The Phase 06 task ledger now has fresh source evidence for
CA-301, CA-302, CA-303, CA-304, CA-305, CA-307, CA-310,
CA-4201, CA-4204, CA-4207, CA-5001, CA-5002, CA-5603,
CA-5604, CA-5803 and CA-5805. Of these 16 original IDs,
15 were previously unassessed and now have **partial_wiring**
evidence, while CA-5603 was already partial and received the
new hot-path fix. The verified code and explicit missing gates
are detailed in:

- `docs/development/ws2-phase06-requirement-audit-2026-10-11.md`
  (`52667896b70110978e656eaeccd404f705eca57c`);
- `docs/development/ws2-phase06-episodes-source-audit-batch2-2026-10-11.md`
  (`f8808d5d07402bb8760e287bdc938b2aec001dbe`);
- ledger update commits `dcd372c61ee59a08919bee5a3644f3ab750f64e6`,
  `474130216b413e898a22affbdeb50c0e07030bc0` and
  `f3f2744e67a843314a4cc6810009206018dad610`.

Neither a source audit nor the two Phase 06 production changes
make these complete or accepted original V18 tasks. Remaining
Phase 06 tasks must each be traced to runtime composition and
effect/receipt/persistence before the user-led test campaign.



### Phase 06 item 65: Exact current-audience SQL recall fallback

Audited the actual `ConversationService._build_request()` path for
`HistoryPolicy.RETRIEVE_SPECIFIC`: an existing, optional FTS5 index
already rechecked the source's `social_session_principal` binding,
but an absent/unready index or no FTS matches fell through to
`ConversationStore.search_messages(session_id,...)`. That SQL fallback
had only a supplied session ID as an authority marker, even if the
current social binding had been removed or changed while a delayed
turn was running.

Production `src/sofia/conversation/store.py` now requires an actual
typed `authorized_principal` and joins the canonical original
`social_session_principal` record with `conversation_messages`
**in the same SQL statement** before returning any matching source
text. SQL compares original `principal_id`, exact `audience_id`
and `audience_kind`, together with the original session ID.
The live `ConversationService` now obtains the current binding
once for both the optional FTS lookup and SQL fallback and declines
unbound historical recall rather than silently downgrading to a
session-ID-only search. Ordinary bounded recent-context behavior
and original conversation retention are unchanged.

- Production store guard `65e801fa556df6e072e6cb7dcfc404a2911688c7`
  (`[skip ci]`).
- Live cognition fallback composition
  `d71df32f637f832d94c71a1175040dac9cfe51e4`
  (`[skip ci]`).
- Deferred exact-original SQLite regressions
  `test/test_ws2_memory_scoped_recall_fallback.py`
  `854e0a9cf31963e1169a051689ec105edec37e95`
  (`[skip ci]`).

Original CA relevance: CA-4206, CA-5001, CA-5002,
CA-5006, CA-5603, CA-5604, CA-5803.
This is audience-safe retrieval fallback, **not** a guarantee
of full cross-thread/autobiographical recall or semantic
truth from historical conversation excerpts. Tests/CI unrun,
no production conversations or host changes.



### Phase 06 item 66: Canonical UTC ordering for newly written conversation sources

Original source audit of `ConversationStore.save`,
`list_messages_page`, `recent_messages` and
`exact_originals` found that new source timestamps were saved as
arbitrary `datetime.isoformat()` text. Lexicographic SQLite
`ORDER BY created_at,id` and keyset comparisons can misorder
different timezone offsets for the same chronological history.
The previous `conversation_sessions.updated_at < ?` text
comparison had the same vulnerability.

Production `src/sofia/conversation/store.py` now stores new
timezone-aware source timestamps in canonical UTC format, compares
session-activity instants using SQLite `julianday()`, and normalizes
offset-aware keyset cursors to UTC. Re-saving the same immutable
message ID using a different valid timezone representation of
the same instant remains idempotent; an actual changed instant
is rejected. The preserved original user/assistant content,
session, role and ID contract is unchanged. Historical rows
already recorded in differing offsets are **not silently rewritten**;
their order may still need a separately approved, backed-up
offline normalization/migration with independent authority and
source-attribution audit. Legacy naive datetime records are
retained for compatibility, not newly certified as UTC.

- Source/chronological write repair
  `f35040afd44f790215793e131af45a977d480ef8` (`[skip ci]`).
- Keyset cursor normalization
  `5e7cd961dbe6dc670e631f969c699a57ddfa85d8` (`[skip ci]`).
- Deferred mixed-offset SQLite regression and cursor coverage
  `test/test_ws2_conversation_utc_ordering.py`,
  `8b8ceb82d476e6d6585df172bceaf5ec20b71242`,
  `5b73d82329f533f5c694531acf53e171ae4a14ca`
  (`[skip ci]`).

Original CA relevance: CA-4207, CA-4803, CA-5001,
CA-5603, CA-5901, CA-5903.
No tests/CI, live database rewrite, on-host index rebuild or
cross-host cutover performed. Original requirements remain partial
until end-to-end temporal correctness and acceptance evidence exist.



### Phase 06 item 67: Explicit fiction cannot become automatic autobiography

Production `ConversationLearningCoordinator._is_learnable` previously
treated text matching an explicit `remember that...` or stable
`I like/prefer...` prefix as eligible for an additional durable
`PROPOSED` personal memory candidate without checking whether
the user had explicitly identified a fictional/roleplay/hypothetical
context. Private review would still gate promotion, but the
candidate's very creation could misleadingly label a roleplay
claim as a user autobiographical fact and impose correction burden.

Production `src/sofia/application/conversation_learning.py`
now declines **automatic** candidate generation on clear
`in this roleplay`, `as my character`,
`pretend`, `hypothetically` and explicit story/game
framing. This is a narrow conservative **source admission**
filter, NOT a universal fact/fiction classifier or a mechanism
to delete actual source messages. Original conversation
evidence remains in its original audience with the existing
retention controls, and a deliberate authorized human
memory-review path is unaffected. User statements about
ordinary real-world gaming interests not framed as fiction
retain the normal proposed-candidate path.

- Production filter `7d841ae8c4619b46713b97c190037a54800c3a13`,
  corrected regex escaping `342fd21a85ef507840eaef70f89674fc94c34c5c`
  (`[skip ci]`).
- Deferred source-classification regression
  `test/test_ws2_memory_private_admission.py` at
  `c1e08d36b77e7c32ed1d7a772af5ff0692d4c10a`
  (`[skip ci]`).

Original relevance: CA-302, CA-305, CA-5803, CA-5804.
There is still no complete observed-versus-inferred semantic
ontology, reviewed subjective interpretation pipeline,
independent end-to-end fiction-label propagation or run
acceptance. Tests/CI and live memory stores untouched.



### Phase 06 item 68: Review lifecycle writes retain original audience ownership

`MemoryReviewService.promote` already verified the candidate's
original authenticated reviewer principal/audience **before**
promoting source-backed personal memory, but sibling owner-facing
lifecycle methods `reject`, `revoke`, `set_expiration`
and `link_correction` previously checked only that the caller
was a private Sparks reviewer. A candidate UUID in one private
audience could therefore authorize a state change to a candidate
belonging to another separately protected private Android,
Discord or local audience.

The **real application review service** now reuses one private
owner + exact candidate source-scope guard for all operations,
including promote. Both original and replacement candidate
are checked before staged correction linkage. This preserves
existing same-audience review behavior and accepted legacy
principal-owned unscoped candidates, but does not silently
broaden shared/private memories or interpret a candidate ID
as access authority. The lower-level canonical
`DurableMemoryCandidateStore` remains the transaction owner
and handles atomic promotion/correction, lifecycle idempotency,
and source evidence without a competing memory database.

- Production `src/sofia/application/memory_review.py`
  `5010ea99910f1a1e08443c17c91fbafa5cfd00fe`
  (`[skip ci]`).
- Deferred synthetic application/store regressions
  `test/test_ws2_memory_review_audience_mutations.py`
  `aca9a2fd5f98223c915c25e509a6fc94b7418b0c`
  (`[skip ci]`): foreign rejection, expiration, revocation
  and mixed-audience correction are denied without mutation;
  matching original reviewer retains normal authority.

Original CA relevance: CA-4204, CA-4806, CA-5604,
CA-5803, CA-5805, CA-5908. Not a general cross-channel
memory-management privilege grant, nor end-to-end erasure of
all caches, mobile copies or external providers.
No tests/CI executed and no live candidate altered.



### Phase 06 source-to-sink audit batch 3: Four additional partial requirements

Audited original CA-4206, CA-5006, CA-4806 and CA-5903 against
real `ConversationService`, canonical FTS/source fallback,
`MemoryReviewService`, `ConversationLearningCoordinator` and
`DurableMemoryCandidateStore`. All four were previously
`unassessed` and now have source-grounded `partial_wiring`
classifications. Real missing gates: cross-class retrieval,
explicit no-evidence/archive permission, complete owner control
over offline copies, and bitemporal correction invalidation
beyond the existing atomic reviewed candidate supersession.

- Exact route/gap analysis:
  `docs/development/ws2-phase06-review-retrieval-audit-batch3-2026-10-11.md`
  commit `2d6c648563559aaebc97ad47cfdfcd14ebc9ae10`.
- Original 700-task evidence ledger update
  `77c2cc13c47e17c2a8cc5eefc7b7af3a642c9862`
  (`[skip ci]`), no task marked complete/accepted.
- Source fixes from items 65–68 are separately documented above.

No tests/CI executed and no live state, client, host
or permissions changed.



### Phase 05 item 69: Canonical uncertainty updates match immutable admitted turn identity

The production `LifelongThreadStore.mark_turn_uncertain` previously
transitioned a durable Main receipt using only `event_id` and
`status='processing'`. A stale runtime could therefore settle an
incorrect claim if another operation reused its apparent event ID.
The real code now requires a typed original
`CanonicalTurnAdmission`, checks a timezone-aware settlement time
and updates only the exact immutable tuple
`(event_id,canonical_sequence,user_message_id,assistant_message_id)`
inside `BEGIN IMMEDIATE`. A mismatched admission fails closed
without changing the original receipt. An already completed,
interrupted or uncertain receipt is retained and cannot be demoted
by a late exception from the prior process.

- Production `src/sofia/conversation/lifelong.py`
  `4a772feaf1d9f70fc09890340c22c4f470371b7e` (`[skip ci]`).
- Deferred canonical SQLite regressions
  `test/test_ws2_canonical_uncertainty_fence.py`
  `c260837c8f0ec323ef317c3a8b31ac862b5a4953`
  (`[skip ci]`).

Original CA relevance: CA-4106, CA-4110, CA-5302,
CA-5304, CA-5505. This is source-level receipt hardening,
not production test evidence or a full Main acceptance.
No CI/test execution, live messages or host changes.



### Phase 05 item 70: Page all original historical-import preview batches

The real `LifelongThreadStore.preview_historical_import` advertised
that an operator could review an old original conversation in
multiple bounded batches, yet it always selected the **first**
up to 128 original messages and did not expose an `after` cursor.
Thus an old session containing hundreds or millions of messages
could not actually preview or independently approve later history
through that production method without ad-hoc direct SQL.

Production `src/sofia/conversation/lifelong.py` now supports
an optional bounded original `(created_at,message_id)` keyset
cursor and returns `HistoricalImportPreview.next_cursor`
only when at least one more original message exists. It
retrieves only `limit+1` rows, checks the **current**
`social_session_principal` owner and audience anew before
each page, uses the original stored timestamp for pagination
without mutating any source data and preserves the existing
one-batch preview response contract for shorter sessions.
No preview action ever inserts or imports Main links: a
separate independently approved `apply_historical_import`
request is still required for each selected set of original IDs.

- Production commit `6292828ec3fdcd7838e25a0853dcd5d0f4675542`
  (`[skip ci]`).
- Deferred regression `test/test_ws2_historical_preview_pagination.py`
  `6a59382a94bc88d5a1952e44488d1e066bb579a8`
  (`[skip ci]`), covering 163 original messages, duplicate-free
  second page, source-only preview with no mutation, and
  current-audience checks on continued paging.

Original CA relevance: CA-4107, CA-5502, CA-5503,
CA-5506, CA-5603, CA-6306. Old source rows with
mixed timezone-offset text retain their original ordering
and need a reviewed offline normalization strategy;
this feature neither rewrites old timestamps nor
claims authoritative import acceptance.
No tests, CI, live import or host operations executed.



### Phase 05 item 71: Fresh independent operator approval before Main import or rollback

The real `LifelongThreadStore.apply_historical_import` and
`rollback_historical_import` already required an external
independent owner review over an exact digest of source/session,
audience, requested message IDs and decision. However each method
verified it **only before** opening its SQLite write transaction.
An approval could be revoked during source enumeration or between
the review and the actual history-link insertion/deletion.

The canonical writer now makes one final independent review check
**inside the same `BEGIN IMMEDIATE` transaction** after current
original audience/source verification and before creating the
new import receipt, new Main links or rolling back selected links.
A stale/revoked review raises `PermissionError` and rolls back
without source deletion or partial Main publication. Repeated
identical already-decided imports keep their existing
idempotent receipt contract. No new review authority is minted
from a model message.

- Production `src/sofia/conversation/lifelong.py`
  `3102d60c5760c6d49735d8d434571df6dbbd1149`
  (`[skip ci]`).
- Deferred revoked-mid-operation approval coverage
  `test/test_ws2_historical_review_revocation.py`,
  `7657c9da9fc6ceb8414915977b22f1b0edf9a690`
  (`[skip ci]`).

Original CA relevance: CA-5502, CA-5503, CA-5505,
CA-5506, CA-6306, CA-6311.
The independent external verifier remains the authority source;
this does not introduce a privileged host fencing broker,
license live host migration or certify one-use grant behavior.
No tests/CI, import, rollback or live owner approval performed.



### Phase 05 item 72: Protect independently adopted canonical turn links from import rollback

`LifelongThreadStore.rollback_historical_import` correctly
allows operator-reviewed reversal only for Main links originally
introduced by that exact import review ID. However, it previously
deleted a matching `lifelong_thread_event` solely by original
`(thread,source_message,session,audience)` even if the link had
since acquired separate `canonical_sequence` or
`turn_position` metadata representing a canonical Main turn.
The historical import approval does not own later independently
admitted canonical turns.

The actual rollback loop now inspects the canonical ordering fields
under its existing `BEGIN IMMEDIATE` transaction and **fails
closed** if an import-owned source link has become an independently
ordered canonical turn. The physical deletion statement also
requires both ordering fields remain `NULL`. Pure historical
import links retain their approved rollback behavior; no original
`conversation_messages` row is ever erased.

- Production `src/sofia/conversation/lifelong.py`
  `9b12131a88228c4e3a4c681863a02053c87ef083`
  (`[skip ci]`).
- Deferred regression `test/test_ws2_historical_import_adopted_canonical.py`
  `0cf40c354d58f7c1b6c13c2ac3d982fba821257b`
  (`[skip ci]`): adopted canonical link persists, pure historical
  links still roll back, original source remains unchanged.

Original CA relevance: CA-5502, CA-5505, CA-5506,
CA-6306. A full historical batch/source deletion and separate
canonical turn migration strategy still need independent policy
and acceptance. No tests/CI/live rollback executed.



### Phase 05 topology source audit: Five additional partially wired original tasks

The actual `ConversationStore`, `ConversationService.start`,
`SocialSessionStore` and `LifelongThreadStore` source paths
were checked against original CA-4101, CA-4102, CA-4112,
CA-5301 and CA-5501. The source proves an existing canonical
session store, explicit session resumption, one independent
principal-owned logical Main ID with optional project IDs,
immutable original audience/session links and an independently
reviewed historical import/rollback interface. It does **not**
prove the complete user-facing cross-device, thread lifecycle
or privilege separation acceptance requirements.

- Original source-to-sink and missing-gates audit:
  `docs/development/ws2-phase05-topology-audit-batch1-2026-10-11.md`
  commit `a3f344abd1bfc53985353f753b3dc70b770f9838`
  (`[skip ci]`).
- Evidence ledger moves **five** original IDs from
  `unassessed` to `partial_wiring`, retaining
  `accepted=false`, commit
  `d4d4f249d42a9a2cbe02a01de065cbcd69e16ddb`
  (`[skip ci]`).

This is not five newly completed original requirements.
Items 69–72 are the distinct code changes documented above.
No tests/CI, approved imports, server processes, network,
clients, source messages or live host state changed.



### Phase 06 item 73: FTS5 source-count metadata remains current after live source edits

The canonical `ConversationFullTextSearch.rebuild_offline` creates
a host-authorized external-content SQLite FTS5 index over original
`conversation_messages` and stores `indexed_source_count` in
`conversation_fts_meta`. Source index triggers already mirrored
new, deleted and modified text into FTS, but the reported count
was calculated only during the original rebuild. Long-lived
conversations therefore reported an obsolete indexed-source count
after every subsequent message insertion or deletion.

Production `src/sofia/conversation/fulltext_search.py` now
transactionally upgrades the three canonical FTS triggers **only
inside the existing independently approved offline rebuild**.
An insert adds one source to the metadata count, a deletion
subtracts one, and content changes update search terms without
increasing the count. The optional FTS text index continues
to index original canonical rows and never becomes a second
source-of-truth or permission boundary. Existing pre-count
triggers are replaced within the verified rebuild transaction;
there is no unauthorized eager index creation on chat startup.

- Production `0bf71f7fd590d709f8093639c5a029bfbc5750e8`
  (`[skip ci]`).
- Deferred fixture `test/test_ws2_fts_count_triggers.py`
  `d609abda05479aefd52dc3ce4e321e4a840e81d4`
  (`[skip ci]`), covering add, edit, delete, search
  results and replacement of an old countless insert trigger
  during an independently authorized synthetic offline rebuild.

Original CA relevance: CA-5002, CA-5603, CA-5604,
CA-5608. This is **index metadata maintenance**, not a
repair of preexisting corrupt FTS blocks or proof of
10-million-event query cost. No real rebuild, test, CI,
database mutation or live model invocation executed.



### Phase 06 item 74: Reject stale source timestamps before ranking promoted memory

Canonical `DurableMemoryCandidateStore.is_recall_eligible` already
rechecked the exact original source's role, content, audience
and real event timestamp after retrieval. However its earlier
`iter_promoted_summaries` keyset source guard checked only
session, content, role and source audience. A promoted candidate
whose original timestamp was altered could therefore consume
a limited relevance-ranking slot before failing the later
validation, crowding out other eligible memories.

Production `src/sofia/memory/provenance_store.py` now
excludes a source-reviewed candidate from the **SQL keyset
summary scan** if its stored source timestamp or original
source timestamp cannot be parsed by SQLite or if their
UTC-normalized Julian instants differ. This retains the
existing final Python `datetime`-precision check for
sub-millisecond differences, and does not turn timestamps
or unreviewed summary text into authentication grants.
No historical source timestamp or durable candidate is
silently rewritten; stale review remains available for
operator diagnosis, not automatically promoted.

- Production `b3ec125b257e4949f9617faaa508bd7402d02d12`
  (`[skip ci]`).
- Deferred canonical SQLite regression
  `test/test_ws2_memory_original_timestamp_prefilter.py`,
  `c2560b64fa4d71e4bf73d78b9341c5edffb139d7`
  (`[skip ci]`).

Original CA relevance: CA-4204, CA-5001, CA-5604,
CA-5805, CA-5901, CA-5907. Original task statuses
remain unaccepted. This is preliminary candidate filtering,
not full bitemporal claim truth or an alternative memory store.
No tests/CI, live source rewrites or model invocations.



### Phase 06 item 75: Revoked privilege aborts offline FTS rebuild commit

The real optional `ConversationFullTextSearch.rebuild_offline`
revalidates a typed independently fenced owner approval at
admission, then runs a potentially long FTS5 source backfill,
trigger upgrade and metadata update inside canonical SQLite
`BEGIN IMMEDIATE`. Previously it could commit all index and
schema effects even if the external owner approval was revoked
during that long maintenance operation.

Production `src/sofia/conversation/fulltext_search.py`
now performs a second independent approval verification
**after the full FTS5 backfill and readiness count** but
**before `db.commit()`**. A revoked approval raises
`PermissionError` and rolls back this one transaction,
including temporary FTS DDL/trigger work. If an earlier
approved index already exists, the denied update must leave
its preexisting transactionally committed state intact.
No model text or in-process boolean self-authorizes an
index rebuild.

- Production `a664b3ab0b8542001a0b0950e16aacb3d2108b0c`
  (`[skip ci]`).
- Deferred synthetic SQLite approval-revocation regression
  `test/test_ws2_fts_rebuild_revocation.py`,
  `64ea019c88dbfa55f318611c299a59a2bdc9b735`
  (`[skip ci]`).

Original CA relevance: CA-5002, CA-5603,
CA-5608, CA-6311. Actual privileged host fencing
and first-owner authorization issuance remain external
and must be independently verified during final acceptance.
No real index rebuild, tests, CI, backup or host
actions executed.



### Phase 06 item 76: FTS readiness requires canonical index and trigger structure

The existing `ConversationFullTextSearch.status()` returned
`ready=True` solely from the persistent
`conversation_fts_meta.is_ready` marker, even when a
later DDL failure, partial external maintenance or manual
index deletion removed the `conversation_messages_fts`
virtual table or one of its source-sync triggers.
An unusable/degrading optional index should never be
advertised as healthy and then be treated as authoritative
historical source coverage.

The production status reader now verifies that all four
canonical SQLite objects exist with their expected kinds:
one FTS5 virtual table plus the `INSERT`, `DELETE`,
`UPDATE` source-maintenance triggers. If any is absent,
it reports not ready; `keyword_search` refuses to search
the unusable index, while the real conversation path uses
the **current-audience checked canonical SQL original
fallback** established in Item 65. The stored source
count remains diagnostic only, not permission or semantic
trust. An independent privileged offline rebuild is still
required for repair, including Item 75's final approval
check before commit.

- Production `54757f9c4090ab6ff4a1923fa331ffabcf3abea2`
  (`[skip ci]`).
- Deferred synthetic SQLite degraded-structure tests
  `test/test_ws2_fts_readiness_structure.py`,
  `1f2d9850dced2554cee475b5aaf90f766ca34ce8`
  (`[skip ci]`).

Original CA relevance: CA-5002, CA-5006,
CA-5604, CA-5608. A structurally present but internally
corrupt FTS5 index still requires a privileged content
integrity/rebuild campaign; these status checks do not
prove completeness or correct matches. No tests/CI,
live index mutation or deployment occurred.



### Phase 05 item 77: Owner-audience project rename and reversible archive

The actual `LifelongThreadStore` owned one canonical logical Main and
optional named project threads, but had no source-authorized rename or
archive/restore lifecycle: projects could be created/read/linked, yet
the owner could not revise a title or hide a completed project
without replacing/deleting source history.

Production `src/sofia/conversation/lifelong.py` now stores nullable
`archived_at` in its **existing canonical thread table**, with an
additive old-schema migration and explicit column lists for all
legacy Main/project INSERT routes. `LifelongThread` projects now
retain their archive state. New `rename_project` and
`set_project_archived` methods operate in `BEGIN IMMEDIATE`
and require exact owner principal PLUS a currently visible
original project message with matching audience and audience kind.
Source-free titles lack audience proof and fail closed until linked.
Main cannot be renamed/archived as a project. Name collisions fail,
and source messages/event links are never rewritten or deleted.

Default `list_threads` and `list_visible_threads` hide archived
projects. Explicit `include_archived=True` enables archive discovery
for later restoration, maintaining the same source-audience admission
before SQL LIMIT. Existing Android thread selection continues to
list unarchived visible headers by default; no cross-channel copying
or project-event write route was added.

- Canonical archive schema/default listing:
  `fc45a510e966cc558e8b40bce8f7adc5d59f51ef`.
- Real project owner/audience mutation methods:
  `a49b75446d430d2698487f7d19337e25ad49a4aa`.
- Reversible archived-thread discovery:
  `06e9584249099d6ed29350b4fb1501551b536a79`.
- Deferred canonical SQLite regressions
  `test/test_ws2_project_thread_lifecycle.py`
  `72209fd350183e8ecd8aad2e7eea1a63ae8d6c40`
  and assertion correction `649d8ab491b1e94eab5dfbcdca7e7f8d7e2adbe6`,
  all `[skip ci]`.

Original relevance: CA-4113, CA-5301, CA-5506, CA-5706,
CA-6306. **Still partial**: the desktop/mobile controls for
authenticated project rename/archive, owner-selected active
project routing, topic continuity and complete archival search/export
need independent production wiring and final acceptance.
No tests/CI, schema migration of a live installation, deployment,
host change or original-source mutation has been performed.



### Phase 05 item 78: Bind project names and new source links to their originating audience

Follow-up audit of Item 77 found a broader cross-channel gap:
`LifelongThreadStore.get_or_create(owner,kind='project',name)`
previously deduplicated names only by principal ID. A different
authenticated audience for the same principal could resolve the
same private project name and obtain its canonical `thread_id`,
then `link_message` allowed that other audience's original
message to be appended to this shared project. This was
**implicit cross-audience association**, even though no outbound
message relay was intentionally performed.

Production `src/sofia/conversation/lifelong.py` now persists
`project_audience_id` and `project_audience_kind` at initial
project creation in the **same canonical thread table**, with a
non-destructive additive legacy schema migration. Project lookups
require that original creation audience; other same-owner
audiences receive a denial, not a project ID. All new project
source links enforce this audience as well as the original source
session's current principal/audience/kind binding. The Main logical
thread remains cross-device, but original Main events retain
their separate per-event visibility and are not mirrored.

Preexisting project rows lacking a creation-audience stamp are
reusable **only when all their existing original links agree**
on one currently authenticated source audience. Mixed-audience
and source-free ambiguous legacy projects fail closed pending
independently reviewed owner migration, instead of guessing which
audience is allowed to claim them. Rename and archive now use
the same project-scope guard. This does not remove or rewrite
legacy source events; approved cross-channel project linking
would require a separate explicit owner-approved operation.

- Project creation and legacy source-scope validation:
  `bb4f1be5ac5c94063faba95d264ce8f7cec1d797`
  (`[skip ci]`).
- Original event linking and project metadata guards:
  `655079bdb9186a19d726db1c04d4661c366fc326`
  (`[skip ci]`).
- Deferred canonical SQLite cross-audience/legacy
  regressions: `test/test_ws2_project_thread_creation_scope.py`,
  `817f8daec909f6b37bc85f75d115ca2d14d3cd89`
  (`[skip ci]`).

Original relevance: CA-4102, CA-4104, CA-4105,
CA-4107, CA-5506, CA-5507, CA-5706.
This is source-level project isolation, NOT the completed
project-thread UI, independent review for legacy mixed
projects, or global approved cross-channel metadata transfer.
No tests/CI, automatic live migrations, remote clients,
host movement or original source edits were performed.



### Phase 05 item 79: Source-free projects visible only to their creation audience

Review of Items 77–78 showed that a newly created project now
has an authenticated `project_audience_id` and
`project_audience_kind`, but the default
`list_visible_threads` and mutation admission still
required an existing linked source event. Consequently
the creator could create a **source-free project** but
could not see, rename, archive or restore it until
adding a message. Simply relaxing the owner ID check
would leak old cross-channel project titles.

The canonical `LifelongThreadStore` now recognizes a
**source-free, creation-audience-bound project** as
visible/editable only to the exact authenticated
originating audience and audience kind. Once any
original source is linked, the existing source-message
and CURRENT social-session binding guards still apply;
a revoked/rebound source cannot be bypassed by the
old creation-audience stamp. Legacy source-free
projects without an origin stamp remain denied until
a separately owner-reviewed migration. Archive
hides from default lists but supports explicit
scoped `include_archived=True` discovery and restore.
Main metadata is never editable as a project.

- Production visibility and edit route
  `70e0487812ca95af49d0297c457ddcfc60705b42`
  and SQL grouping correction
  `96d2664c4f915348cbbdc58694af80029dc7e66e`
  (`[skip ci]`).
- Deferred source-free project and legacy-unbound
  fixture update `test/test_ws2_project_thread_lifecycle.py`,
  `d00ba75b12ad37e95345884b24db4f0d301abd3b`
  (`[skip ci]`).

Original relevance: CA-4113, CA-5301, CA-5506.
Remaining **full** requirements include authenticated
desktop/mobile editing UX, active-project turn routing,
cross-project source attribution, pin/export/search
and final live acceptance. This is source-level coding,
not a migrated live schema or a successful test.



### Phase 04 item 80: Android read-only archived projects with withdrawn-source provenance

Item 77 introduced owner-scoped reversible archived-project
metadata and Item 79 made newly created **never-linked**
projects visible to their exact creation audience. The
Android application already browsed authenticated project
headers and read-only original-source pages, but had no
way to request archived projects. It also required
source events for every project page, incorrectly
denying a brand-new empty project.

The real pairing-authenticated
`MobileCompanionGateway.dispatch_authenticated`
`/v1/mobile/threads` route now accepts strictly typed
optional `include_archived`, defaults to the old
unarchived behavior and uses
`LifelongThreadStore.list_visible_threads` to
filter original source-audience visibility **before**
pagination. It includes a grounded `archived` boolean
for each header. Android's `SofiaApi.visibleThreads`,
`MainViewModel` and Compose UI now have an explicit
read-only "Include archived / Hide archived" toggle,
refresh the authenticated header set and identify
archived project choices without enabling remote
rename, archive, sharing or tool execution.

**Withdrawal guard:** A previously linked project must
never become a "new empty project" when its final
source link is deleted. Production therefore adds
durable `lifelong_thread.has_linked_source` evidence:
legacy rows default to **ever linked** (fail closed)
and new creation-audience-bound projects start at
`0`. A successful original source link sets the bit
to `1` transactionally; deletion of all links does
not reset it. Only `has_linked_source=0` plus no
current events and exact creation-audience proof can
show an empty title or return an empty authenticated
project-history page. Old projects with withdrawn or
rebound original sources stay inaccessible.

- Authenticated read-only gateway archive projection:
  `1517b29fa1859a0e2482a3c523b4dc62859b1ea0`
  (`[skip ci]`).
- Android API `c769a8253efd1a72130382eb2bfd5b43331f114b`
  and UI `ce7f3d45d4dc6647300ced663226715ff209684a`
  (`[skip ci]`).
- Durable ever-linked source provenance:
  `9b1ad5498eaa9194f5bccb1c00fcec98567598bc`
  (`[skip ci]`).
- Source-free current-audience page admission:
  `b4bf7f607ca22c7c81954ca23cdddd531f0c14d9`,
  gateway `43963835665c71725a62027dc0c93cebb637f687`
  (`[skip ci]`).
- Deferred synthetic gateway/privacy/withdrawal fixtures:
  `test/test_ws2_mobile_archived_project_headers.py`
  `0536eab81d646eeddbcca8ab266063893bc254a7`
  and `e0bd4a77263a977cced81a662206768ca11bbb0d`
  (`[skip ci]`).

Original CA relevance: CA-4107, CA-4109, CA-5303,
CA-5307, CA-5503, CA-5506.
This is authenticated **read-only** project browsing and
source-withdrawal safety, not project-creation UI,
phone-side editing permission, cross-channel mirroring,
full Android instrumentation acceptance or tests/CI.
No running Android device, live schema, database,
service or host was changed.



### Phase 06 item 81: Recheck reviewed memory originals inside atomic promotion

The actual `MemoryReviewService.promote` authorizes the
private source audience, rereads exact original messages,
checks their bytes/roles/timestamps and creates durable
`memory_candidate_source_review` provenance before
calling `DurableMemoryCandidateStore.promote`. A
source deletion, content change, audience rebind or
original timestamp edit could occur **after**
application review but **before** the store's
independent SQLite promotion transaction. The existing
recall guard would eventually suppress stale promoted
memory, but the stale candidate still gained an
incorrect promoted status.

Production `src/sofia/memory/provenance_store.py`
now rechecks every **reviewed** candidate's exact
current source message, source role, text, UTC instant
and `social_session_principal` inside the same
`BEGIN IMMEDIATE` transaction as promotion.
The guard executes **before** either ordinary
`PROPOSED → PROMOTED` or a reviewed correction's
atomic old-fact revocation/new-fact promotion.
If original evidence changed, no candidate status
is mutated, and the former correction target
remains promoted until independently reviewed
replacement evidence really exists.
Historic low-level unattested candidates retain
their separate compatibility policy, not an
unjustified new source-review signature.

- Production `3af195fbaf303bde7cb9083e425f022839f3db59`
  (`[skip ci]`).
- Deferred synthetic original delete/content/time/
  audience-change and correction atomicity coverage
  `test/test_ws2_atomic_reviewed_memory_promotion.py`,
  `fb63731ca1bc891ccecf9463fdc264ee7784f0f5`
  (`[skip ci]`).

Original CA relevance: CA-4204, CA-5803, CA-5805,
CA-5903, CA-5907, CA-5908.
This closes one promotion race, **not** complete
bitemporal semantics, derived-cache invalidation,
cross-channel owner grants or physical deletion.
No tests/CI, live memory, consent grant or
database migration executed.



### Phase 03 item 82: Preserve post-rename publication uncertainty through staging cleanup

Source audit of `stage_verified_state_home` found a
high-risk exception-masking path during a privileged
offline recovery stage. Linux
`_publish_new_home_without_replacing` correctly
raises `StateHomePublicationUncertain` if the atomic
directory rename has already succeeded but the
subsequent parent-directory `fsync` fails.
At that point the staging directory no longer
exists, yet the outer `finally` unconditionally
attempted `shutil.rmtree(staging)` whenever
`published=False`. That could raise
`FileNotFoundError`, hide the crucial uncertainty
classification and encourage unsafe repeat
publication or accidental activation.

Production `src/sofia/ops/state_relocation.py`
now cleans up only when its own randomly named
staging directory **still exists and is not a
symbolic link**. A candidate already renamed
to the owner-selected destination remains intact
for independent inspection. This change
does NOT assert Linux directory-entry durability,
issue writer-fence authority or convert uncertainty
into a success receipt; existing strict operator
authorization and erasure checks remain.

- Production `8a72fb269e8a8a142e7b9e7bc543fba61f02e316`
  (`[skip ci]`).
- Deferred integrated synthetic staging contract
  `test/test_ws2_relocation_postrename_cleanup.py`,
  `25395ae1a0f22f0d60cfabef9fbc15a3ac7eecfd`
  (`[skip ci]`). Verifies typed uncertainty survives
  after simulated directory rename while the destination
  candidate and original source both remain; pre-rename
  denial still discards only staging.

Original CA relevance: CA-5202, CA-5204,
CA-6105, CA-6311, CA-6404.
No test/CI execution, real host fencing,
backup restore, state-home mutation,
database relocation or service activation.



### Phase 03 item 83: Pending pointer requires unchanged staged paths and current privileged handoff

The operator-only `prepare_pending_state_pointer`
already produced a signed `*.pending.json` outside
the state home and refused a redirected **output**
path, but checked the candidate SQLite database
and protected identity with `is_file()`, which
follows symlinks. It also checked the independent
cutover witness only at the start; external
approval could have been withdrawn during
filesystem verification or signing preparations.

Production `src/sofia/ops/state_promotion.py`
now rejects symlink/junction redirection in the
**original spelling** of the staged canonical
database, protected identity and their ancestry
before signing. Immediately before `O_EXCL`
pending-file creation, it rechecks the
independently privileged handoff approval and
those trust paths. An expired approval fails
closed with no new pending artifact. A healthy
approval still creates a signed, **nonactive**
file and never changes the current bootstrap
pointer or grants the new host writer authority.

- Production `4b583eee6b45fca6c083a4e26fadd96b0afc0ed1`
  (`[skip ci]`).
- Deferred synthetic approval-revocation and
  redirected-canonical-database/identity regression
  `test/test_ws2_pending_pointer_handoff_recheck.py`,
  `d006827a13da5139872a5beb7511bf451afe4398`
  (`[skip ci]`).

Original CA relevance: CA-5202, CA-5204, CA-6101,
CA-6105, CA-6311, CA-6807.
This does not prove a cross-host atomic lease,
an active pointer transition, Windows directory-entry
crash durability or a hardware-backed remote witness.
No tests/CI, live VM, host control, restore or cutover
has been performed.



### Phase 05 item 84: Project read APIs reject mixed or rebound original audiences

Follow-on audit of Items 78–80 found an inconsistent
read-side authorization boundary. Tagged projects
validated their creation audience during mutations,
but `_project_scope_allowed` returned early for the
tag without checking whether **all** subsequently
linked original messages and current source session
bindings still agreed with the tag. Meanwhile
`list_visible_threads` used a mere
`EXISTS(one visible original)`, and
`visible_events`, `visible_messages` and
`visible_message_page` did not inspect the
project's immutable creation scope at all.
A corrupted or imported mixed-audience project
could therefore leak its title through another
authenticated channel or expose one subset of
its source history without full project authority.

Production `src/sofia/conversation/lifelong.py`
now requires every project original and its
**CURRENT** `social_session_principal` binding
to match the requesting principal, audience and
kind, even for an origin-tagged project. Empty
projects still require a present creator-audience
stamp plus `has_linked_source=0`. Default
header projection enforces this against **all**
linked originals in SQL **before LIMIT** and
also validates the original creation stamp.
Direct event/message readers and canonical pagers
apply the same full project-scope check before
fetching source text. Main's independent
per-source audience policy is unchanged;
historical mixed projects are neither erased nor
silently relabeled, but remain blocked until
approved remediation.

- Full-project authority helper:
  `00f7ddd47e75569e00ed93921a40ff8007066f86`
  (`[skip ci]`).
- SQL-first title filter:
  `0e5d08414b9b447a90dc061ae63d500bf742747b`
  (`[skip ci]`).
- Canonical event, message and page read gates:
  `7d061fdeb65d67f28cb71249d0163da783f84de4`
  (`[skip ci]`).
- Deferred source corruption, mixed legacy and
  healthy project regression coverage:
  `test/test_ws2_project_read_scope_integrity.py`
  `070e895b34e9eb393064b9b0b4f119c6517a1d3a`
  (`[skip ci]`).

Original CA relevance: CA-4104, CA-4107, CA-5301,
CA-5506, CA-5706, CA-6306. The source integrity
upgrade is NOT final proof of cross-device privacy
or remediation of already disclosed historical
messages. Tests, CI, Android builds and live
data repair remain deferred.



### Phase 06 item 85: Fresh owner consent at the signed erasure journal append

The existing external `MemoryDeletionLedger.request`
checked independently authorized user consent
**before** acquiring its cross-process journal
lock, then scanned the entire authenticated
HMAC chain and computed the next signed record.
If approval expired while waiting for a lock
or preparing a tombstone, that earlier check
could still result in a durable new erasure
record without current consent.

Production `src/sofia/memory/deletion_ledger.py`
now invokes the **same independent approval
witness again under the external journal lock**
after scanning and payload preparation, immediately
before opening the journal for append.
A withdrawn approval raises `PermissionError`;
no new signed tombstone is written by that
request. Current signed request IDs, journal
sequence/HMAC, per-candidate idempotency and
SQLite anti-resurrection remain the same.
A duplicate already-journaled approved erasure
still returns its original no-op receipt.

- Production `6a01ecc4b64cbbe36bfd6e5f0a2d63c08d5d1281`
  (`[skip ci]`).
- Deferred synthetic approve-then-revoke and
  still-approved single append proof:
  `test/test_ws2_erasure_final_approval.py`,
  `4135c1586eba49409716e4f27b5ffe646816132a`
  (`[skip ci]`).

Original CA relevance: CA-4806, CA-5202,
CA-5803, CA-5908, CA-6108, CA-6311.
External journal replication/fencing, exact
current approval lifetime, storage durability
and complete deletion of all cached source
representations remain separate gates.
No tests/CI, live deletes, restore, database
movement or secret key changes occurred.



### Phase 03 source audit: Eleven original recovery tasks, nine newly partial

Audited actual `CanonicalSQLiteGuard`, encrypted
`BackupEngine`, `MemoryDeletionLedger`,
`inspect_state_relocation`,
`stage_verified_state_home`,
`prepare_pending_state_pointer`, portable
recovery export and verified bootstrap pointer
against original CA-3704, CA-3707, CA-5202,
CA-5204, CA-5205, CA-6101, CA-6105,
CA-6108, CA-6803, CA-6805 and CA-6807.
Production sources prove recoverable partial
implementation for each; **nine** were previously
unassessed, while CA-6101 and CA-6807 were
already partial. No claim of successful clean
host restore, complete archival epochs or
actual cross-host writer fencing is made.

- Requirement-by-requirement source/remaining-gate
  audit:
  `docs/development/ws2-phase03-source-trace-batch-2026-10-11.md`,
  `70b1fe36cd97dadf3e56cacd1de7be93c2fef6b6`
  (`[skip ci]`).
- Original V18 700-task evidence ledger:
  `e69aaf3d2d708b972149bc6a65c267ba9f038cca`
  (`[skip ci]`), exactly 11 checked,
  nine `unassessed → partial_wiring`,
  zero `accepted`.
- Distinct recovery/erasure code changes from
  Items 82, 83 and 85 are documented above.

**Critical external gate still missing:**
privileged old-writer fence, one immutable
owner lease/epoch and independently
approved activation protocol for the
Venus → Artemis Debian VM migration.
Source-only staging/pointers do not grant
permission to promote or write canonical
SQLite from both hosts. No CI/tests, live
restores or host operations were performed.



### Phase 06 item 86: Deletion replay and journal append share one external lock

The real `MemoryDeletionLedger.apply_to_sqlite`
replayed the signed external erasure journal into
canonical SQLite under `BEGIN IMMEDIATE`, but
read the journal entries **before** obtaining that
SQLite lock and without holding the journal's
cross-process append lock. Another authorized
process could append a new tombstone after the
read but before local deletion commit, leaving
that freshly requested erasure unapplied in a
runtime that believed its startup replay was
complete.

Production `src/sofia/memory/deletion_ledger.py`
now holds the existing same
`MemoryDeletionLedger._exclusive()` file lock
for the **entire** signed-journal read and
SQLite erasure replay/commit. The existing
journal `request` path uses that lock to
append new signed tombstones, so cooperating
local appenders cannot advance the journal
mid-replay. Signed sequence, external HMAC,
candidate scope, idempotency, anti-resurrection
and SQLite secure-delete behavior are
unchanged. This is **not** a distributed
cross-host writer fence or proof that an
external journal replica is globally newest.

- Production `d8620683fd078dc55f4b4d68709125315f5b2b1f`
  (`[skip ci]`).
- Deferred synthetic canonical SQLite and
  lock ownership regressions
  `test/test_ws2_erasure_replay_lock.py`,
  `416a30c369978074d588a5b7e6bb9eb483e13905`
  (`[skip ci]`).

Original CA relevance: CA-4806, CA-5202,
CA-5908, CA-6105, CA-6108, CA-6311.
A concurrent append **after replay and
after lock release** still requires live
runtime invalidation/replay coordination
before the new deletion is observable
everywhere. Complete external authority
and deletion across all storage layers
remain unaccepted. No tests/CI, live
deletes, restore or host changes performed.



### Phase 03 item 87: Partial offline bundle restore is publication-uncertain

The actual `BackupEngine.restore` publishes an authenticated,
erasure-replayed **multi-file bundle** using separate durable
per-file names, with no atomic whole-bundle rename at that level.
Previously an I/O failure, path collision or permission denial
on the *second or later* asset could propagate as an ordinary
`OSError` or `BackupError` even though earlier protected
assets were already visible. This misclassified an incomplete
published candidate as an operation that never published data.

Production `src/sofia/ops/backup.py` now tracks the first
successful file publication inside the existing externally
serialized deletion-journal lock. If a later asset fails,
it emits the typed `RestorePublicationUncertain` with the
original failure preserved as its exception cause.
No automatic retry, rollback, partial directory deletion or
activation occurs. Errors **before any destination file**
becomes visible remain ordinary failures; Linux
post-publication fsync failures retain their existing
typed durability-uncertain classification. A true
atomic directory candidate remains the caller-owned
`stage_verified_state_home` protocol, not this
file-by-file restore.

- Production `11385df88b83f4da10a6cc27d589e99fe9084181`
  (`[skip ci]`).
- Deferred previous collision contract update
  `test/test_ws2_restore_whole_bundle_no_replace.py`
  `5397b72371bab537578ecd19644ac357a63dd039`
  (`[skip ci]`).
- New deferred before/after-first-asset coverage
  `test/test_ws2_partial_bundle_restore_uncertainty.py`
  `a1b2a7596f6d2e318be84306e569887737b186fe`
  (`[skip ci]`).

Original CA relevance: CA-3702, CA-5202, CA-5204,
CA-6105, CA-6108, CA-6812. It does NOT prove a
distributed privileged fencing broker, partial-repair
strategy or successful clean-machine restore.
No tests/CI, data migrations, filesystem restores
or live host operations executed.



### Phase 03 item 88: Relocation preflight agrees with atomic absent-destination stage

The real `inspect_state_relocation` preflight
previously allowed an **existing empty**
destination directory, classifying it as
eligible for operator review. Yet the
`stage_verified_state_home` production
publisher intentionally rejects **any**
already existing destination, including
empty operator-owned directories, to
preserve atomic `RENAME_NOREPLACE`
and avoid clobbering another home.
That inconsistency could mislead the
storage-location UI or an operator
attempting an approved migration.

Production `src/sofia/ops/state_mobility.py`
now reports
`destination_must_be_absent_for_atomic_stage`
whenever the target already exists
or is a symlink. An absent and otherwise
eligible path is still **review-only**:
the privileged host fence, authenticated
backup and external owner approval
remain mandatory. No destination
is removed, created, renamed or
activated by the preflight.

- Production `d4965e8e968e0e15faa65e5877b6cf7b8c697af2`
  (`[skip ci]`).
- Deferred pre-existing empty/occupied
  directory and file regressions
  `test/test_state_relocation_local_preflight.py`
  `2f40bfc2b7e2c54e6a82442e20977598b235b4e5`
  (`[skip ci]`).

Original CA relevance: CA-6807,
CA-6810, CA-6812. This does not
grant host writer authority, assert
a successful relocation or trigger
a real filesystem operation.
No tests/CI executed.



### Phase 03 item 89: Encrypted backup creation uses durable absence-only directory publication

Production `BackupEngine.create` staged encrypted
payloads and authenticated manifest bytes under a
temporary directory but previously published the
final backup with `os.replace(staging, final)`.
A previous `final.exists()` check alone cannot
stop a concurrent empty owner directory appearing
between inspection and replace, and closed files
plus an atomic rename do not prove encrypted
payloads and directory entries survive power loss.
Returning a verified backup receipt under these
circumstances could overstate recovery durability.

The existing backup owner now refuses redirected
selected backup-root ancestry, flushes **every
encrypted payload and manifest file** and the
nested directory entries on Linux before
publication, and publishes only using Linux
`renameat2(RENAME_NOREPLACE)`, or Windows'
nonreplacing directory rename. Unknown platforms
or missing atomic filesystem primitives fail
closed. Linux then fsyncs the published archive's
parent directory; if that fails *after* the name
is visible, the new typed
`BackupPublicationUncertain` preserves that
uncertainty and never returns a verified success.
Existing archive bytes are never overwritten,
and no retention rotation is authorized by
a failed backup create attempt.

- Production `src/sofia/ops/backup.py`
  `9d2393fe3dd6c90fd8b4c315b37ef9b4a4ae70e1`
  (`[skip ci]`).
- Deferred synthetic backup creation,
  power-loss barrier, kernel no-replace
  collision, parent sync failure and early
  payload sync failure tests:
  `test/test_ws2_backup_archive_publication.py`,
  `f4a9d88da350e37d41a243e38f370c1960bc436d`
  (`[skip ci]`).

Original CA relevance: CA-3702, CA-5202,
CA-5204, CA-5207, CA-6105, CA-6107,
CA-6810, CA-6812. This is no proof of
failure-domain independence, two independently
verified encrypted copies, recovery key escrow
or full clean-machine restore acceptance.
No tests/CI, live backup, host change or
active writer migration was executed.



### Phase 03 item 90: Storage preview proposes an absent child, never an existing folder

The existing Windows Tray Settings → Advanced
`preview_relocation` used a directory picker to
select the destination directory itself.
Native directory pickers typically return
**existing** paths, whereas the production
`stage_verified_state_home` and repaired
preflight (Item 88) require a strictly
**absent** final destination for nonreplacing
atomic publication. The UI consequently
guided owners toward a path it must reject.

The real Settings preview now selects an
**existing parent** and asks the operator
for a new child folder name. Production
`proposed_state_home_from_parent` centralizes
platform-safe bounded component validation,
rejects `..`, path separators, Windows
device-name aliases, redirected ancestry
and any already-existing/symlinked destination,
and performs **zero** filesystem mutation.
The Settings control invokes that shared
validator and displays the normal
`relocation_preflight_text` evidence
for the proposed absent path. Neither
a model nor a UI button can stage,
approve, activate, switch writer authority
or make a new canonical identity
through this read-only preview.

- UI picker correction
  `ab6efc80ba2c91027b716a53efbd66782b6eeba2`
  (`[skip ci]`).
- Reusable approved-name and path builder
  `src/sofia/ops/state_mobility.py`
  `f11a052ae89c5fd1c5f509496c47f56befbf88da`
  (`[skip ci]`).
- Shared UI composition
  `842495ed95f2a2e8bca9480d53b791a2999b0f84`
  (`[skip ci]`).
- Deferred pure destination rules
  `test/test_ws2_state_home_destination_builder.py`
  `c99cad359f56c803572677fa06380f3cdedc3b8c`
  (`[skip ci]`).

Original CA relevance: CA-6802, CA-6807,
CA-6812, CA-6817. This is a complete
read-only path proposal/inspection slice,
not the full owner-reviewed Move Sofía's
Home wizard, host fencing or live cutover.
No tests/CI, Windows UI execution,
folder creation or production migration.



### Phase 03 operator cutover ADR: Original-design gates and unresolved privilege location

The original V18 Phase 03 checklist includes design/research
gates in addition to implementation. The verified
Venus-now/Artemis-Debian-13-later host policy, genuine
`BackupEngine`, `CanonicalSQLiteGuard`,
`state_relocation`, signed nonactive pointer,
external erasure journal and source failure receipts
have been consolidated into one operator-cutover
design contract:

`docs/development/ws2-phase03-operator-cutover-contract-2026-10-11.md`,
commit `14378197f4f6e3177eda975b8e9f715660f2e734`
(`[skip ci]`).

It details the observable state machine
`OBSERVE → QUIESCE_REQUESTED → SOURCE_FENCED
→ SNAPSHOT_VERIFIED → STAGED_NONACTIVE →
PENDING_SIGNED → COMMIT_AUTHORIZED →
ACTIVE_VERIFIED → OLD_COPY_RETIRED`, receipts
required at each gate, failure/rollback
classification for Git, Discord, Home Assistant,
JMRI, Hyper-V, signed erasure and new writer
writes, tiered/portable retention, clean-host
restore drills and the explicit **external**
privileged broker/key custody decisions.

**Do not mark Phase 03 completed from this ADR.**
There is still no accepted independent host-fence
implementation, two independently restored live
recovery snapshots, validated clean Debian guest,
signed active pointer commit or tested rollback.
This document is a source-grounded design
deliverable, not an LLM authority grant.
No tests/CI/live commands executed.



### Phase 03 item 91: Standalone recovery JSONL checksum and schema validator

The existing `export_portable_conversations`
already produced a sensitive plaintext
`sofia.portable-conversations.v1` JSONL
archive with original message and
audience-binding records, thread
catalog/links, exact record counts
and a SHA-256 footer over the preceding
physical UTF-8 lines. However the
repo lacked an **independent, read-only
validation utility** that an operator
could use on a clean OS without
installing Sofía, SQLite, its LLM or
its production application dependencies.

The new standalone standard-library
`scripts/verify_sofia_portable_export.py`
checks exact header/footer schema,
sensitive privacy labels, bounded
UTF-8 JSONL record size, correct
type ordering, required original
source keys, booleans and record
counts. It computes the exact
preceding-line SHA-256, detects
truncation, corruption, missing/
duplicate footers and trailing data,
and prints **counts and digest only**,
never original text. It does
**not** load a state database,
grant channel access, edit a file
or treat the export SHA as a
cryptographic signature. The
original verified encrypted backup
MAC and independent erasure head
remain the source authenticity
and anti-resurrection authorities.

- Independent script
  `401cc215aa5c346275b0425f755519b602f2b134`
  (`[skip ci]`).
- Deferred synthetic valid/tampered,
  missing footer, count drift,
  junk/trailing record and bounded
  read cases
  `test/test_ws2_portable_export_validator.py`
  `b97de071e9c9114bd017e112ebdc7661b81f825f`
  and fixture refinement
  `a7b5b9f049236930ee2672c92c07b63334b332ed`
  (`[skip ci]`).

Original CA relevance: CA-5205,
CA-5207, CA-6104, CA-6107,
CA-6810. This does not validate
an entire cold archive, media,
secret escrow or future schema
without further work. No tests,
actual plaintext export, clean
host recovery or live changes.



### Phase 03 original task evidence: Three newly partial, one enriched

The original V18 evidence ledger was reconciled only
where audited implementation exists. Of four Phase 03
IDs checked, CA-6104 (portable versioned export),
CA-6802 (read-only Settings storage inspection) and
CA-6812 (typed crash/uncertain relocation recovery)
now have `partial_wiring` evidence. CA-5205
(portable disaster recovery format) was already
partial and gained the independently readable
checksum validator. No original task became
`accepted` or `code_complete`.

Ledger commit:
`16c5761c060fd2e0aaa101d31354913c881ef5b5`
(`[skip ci]`). The remaining original design
requirements and actual privileged writer
fencing are still open. The Phase 03 operator
cutover ADR supplies researched decisions but
does not pretend their entire production
implementation was finished.



### Phase 03 item 92: Settings canonical database diagnostics use read-only SQLite

The existing Windows Settings Advanced
`database_diagnostics` reads the canonical
database integrity and table catalog without
writing SQL, but previously obtained its
connection through the general-purpose
`CanonicalSQLiteGuard.connect` method,
which intentionally uses `mode=rw`.
This granted write-capable file access
for a read-only operator inspection,
contrary to the requested inspection
versus maintenance privilege separation.

Production `src/sofia/ui/settings_service.py`
now pins and revalidates the existing
canonical file identity, opens
`sqlite3.connect(...?mode=ro, uri=True)`,
runs only `PRAGMA quick_check` and
table enumeration, and checks the
canonical inode identity again before
returning output. A missing/replaced
state raises instead of creating a new
database. It grants no schema mutation,
restore, migration or operator approval.

- Production `a408cf42927bec855fd30fd3525939be8f41c563`
  (`[skip ci]`).
- Deferred read-only mode and absent
  state checks
  `test/test_ws2_storage_read_only_diagnostics.py`
  `b25fb0fce3d98d17d920e3023c76ad162731f7ac`
  (`[skip ci]`).

Original CA relevance: CA-6802,
CA-6815, CA-6817. No actual
UI launch, CI, tests, live
SQLite operations or host cutover.



### Phase 03 item 93: Plaintext SQLite snapshot never enters encrypted backup destination

The existing `BackupEngine.create` uses the
SQLite online backup API to obtain a
consistent plaintext `sofia.db` snapshot
before AES-256-GCM encryption. Source
audit found that the temporary
`sofia.db.snapshot` was created
**inside the eventual encrypted backup
archive directory** and was not
explicitly removed before publication.
Besides exposing a raw SQLite file
in an archive labeled encrypted,
the earlier staging location risked
writing private cleartext onto an
untrusted NAS/off-host archive medium
**before** encrypting it.

Production `src/sofia/ops/backup.py`
now creates the online SQLite snapshot
inside an access-controlled
`TemporaryDirectory` (mode 0700)
on the canonical **source host's local
state filesystem**, never under the
backup destination. It encrypts the
snapshot into its authenticated
ciphertext payload and unlinks the
plaintext source immediately after
encryption. The temporary directory is
removed on success or failure; the
archive also explicitly refuses a
leftover staging snapshot before
manifest publication. The completed
archive contains only the encrypted
payload directory and authenticated
manifest/HMAC. Read-only verification
still authenticates all payload
digests, but no plaintext SQLite
file is intentionally transported
to the backup destination.

- First archive exclusion guard
  `0b06cf796323878b2b9ad98a234822fba91862f8`
  (`[skip ci]`).
- Source-local ephemeral plaintext
  snapshot redesign
  `5986556aec958f4dd6df95fbb4f8452fc9c91fbe`
  (`[skip ci]`).
- Deferred proof of local snapshot
  path, encrypted archive contents
  and failure cleanup
  `test/test_ws2_backup_snapshot_plaintext_isolation.py`
  `80369ae23ec8f70a7b50400ebcfa388008ccc9de`
  (`[skip ci]`).

Original CA relevance: CA-5202,
CA-5205, CA-6105, CA-6106,
CA-6806. This does not
retroactively remove plaintext
files from any **previously made**
backup archives or inaccessible
snapshot remnants on physical media;
the owner must inventory and
remediate existing backup copies
after the deferred test/audit campaign.
No tests/CI, live backup or
host/storage mutation performed.



### Phase 03 item 94: Verify encrypted backup has no unlisted plaintext or foreign files

Follow-up to Item 93: the preexisting
`BackupEngine.verify` authenticated the
manifest HMAC and each listed AES-GCM
payload, but never examined **extra
unlisted files** in the archive root.
A legacy backup created before the
plaintext temporary snapshot fix could
therefore pass as "verified encrypted"
while still carrying
`sofia.db.snapshot` in cleartext,
potentially on a NAS or other
backup medium.

Production `src/sofia/ops/backup.py`
now checks the entire backup directory
inventory after authenticating the
manifest. Only `manifest.json`,
`manifest.hmac`, the `payload/`
directory and the exact manifest-listed
encrypted payload files may exist;
the canonical `sofia.db` logical entry
must be present. Redirected links,
unexpected directories, special
entries, extra files or an incomplete
listed inventory fail closed with
`BackupError` **before** a verified
receipt or restore publication.
This does not remove any owner's
existing files automatically.

- Production `bf840071635c6c2c95f9b07c14ff17963a36cdfd`
  (`[skip ci]`).
- Deferred synthetic legacy-plaintext,
  unexpected log and private directory
  regressions
  `test/test_ws2_backup_snapshot_plaintext_isolation.py`,
  `2b63e83c0b274685133264d9977342ca2c913a9e`
  (`[skip ci]`).

Original CA relevance: CA-5202,
CA-5205, CA-5207, CA-6105,
CA-6107, CA-6810.
**Existing backup archives must be
reviewed after tests;** changing
source cannot retroactively guarantee
their confidentiality. No CI/tests,
live backup scan, cleanup, key
rotation or host operation ran.



### Phase 03 item 87: Bounded discovery of unreadable or oversized recovery candidates

`discover_local_state_candidates` scans a small, approved collection of
local Sofía homes without activating a database or selecting a writer.
Before this fix, opening any candidate SQLite header and hashing any
`protected/identity.json` could raise an unhandled `OSError`,
aborting recovery discovery of other valid roots. Identity reads were
also unbounded, allowing a misplaced large identity file to force a
disproportionate memory read even though discovered homes are not
authoritative.

Production `src/sofia/ops/state_mobility.py` now caps candidate
identity reads at 64 KiB; an oversized, symlinked, redirected or
unreadable identity cannot claim lineage to the configured home.
Unreadable or vanished candidate DBs are skipped individually, and
their failures cannot suppress other candidates. The SQLite-header
read and file-size snapshot are guarded together. No candidate is
promoted based on its filename, content timestamp or hash alone.

- Production `da9a3af1c20aace02918ff334fdfd37a42ed25eb`
  (`[skip ci]`).
- Deferred synthetic discovery regression
  `test/test_ws2_state_candidate_discovery_resilience.py`,
  `13a0763fe49201413cd4eca8dbae1f39e1cfdde2`
  (`[skip ci]`).

Original CA relevance: CA-6803, CA-6804, CA-6807 and CA-5207.
Original requirements remain partial; recovery lineage and
writer authority still require an independent operator and
privileged cross-host fencing. No tests/CI or live file scans
were executed.



### Phase 03 item 88: Inspect operator-selected recovery roots before defaults

`discover_local_state_candidates` previously appended explicit
owner-selected `extra_roots` after conventional search locations,
then truncated the combined list at `max_roots`. Under a small
inspection budget the user-approved roots could therefore be
**silently skipped**, while unrequested conventional directories
consumed the entire scan quota. That is particularly dangerous
when the active state home is unavailable and a known backup
must be presented for operator review.

Production now inspects the configured home first, then explicitly
approved extra roots, and only afterwards uses remaining slots for
known conventional locations. The existing bounded maximum is
preserved; this remains discovery, NOT active-writer selection,
state creation, credential transfer or cutover.

- Production `579bbb755ff6b2986b1323fdb6c5ae9724634d01`
  (`[skip ci]`).
- Deferred cap-priority fixture in
  `test/test_ws2_state_candidate_discovery_resilience.py`,
  `96a7efc1161e9c52377255529fd28513cd0d0455`
  (`[skip ci]`).

Original relevance: CA-6803, CA-6804, CA-6807.
No tests/CI or live discovery executed; requirement acceptance
remains pending.

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

## Operator architecture decision: Venus now, Artemis later (2026-10-11)

**Decision supplied by the operator, not inferred from hardware:**

- Current production authority: **Venus** holds the sole writable canonical
  `sofia.db`, Sofía runtime, desktop UI and available GPU inference.
- Future architecture: a dedicated **Sofia VM on Artemis** owns the single
  canonical runtime, `sofia.db`, memory, goals, scheduling and services.
  The other Artemis VMs remain available as separately scoped test agents.
- Future compute split: **Venus** provides RTX 3080 Ti inference and desktop
  UI over an authenticated, explicitly provisioned network connection;
  the Artemis Sofia VM is not required to have a GPU. No model fallback is
  implicitly approved.
- If Venus inference becomes unavailable, Artemis must retain canonical
  state and continue explicitly eligible non-LLM scheduling/service work.
  Cognition-dependent work becomes unavailable/deferred and must **never**
  fabricate an LLM reply or silently substitute another model.
- The single-writer handoff from Venus to Artemis is **not authorized now**.
  It requires a reviewed snapshot, host identity and independent fencing
  proof, old writer shutdown, source/backup integrity verification, explicit
  operator cutover approval, and a tested failback/rollback procedure.
  Direct network-shared SQLite WAL and dual simultaneous writers are forbidden.
- This design decision does **not** permit modifying existing Windows
  services, certificates, environment configuration, host paths, database
  placement, GPU providers, network firewalls, or VM startup state.

Future host-independent coding must preserve these invariants. Physical
writer fencing, authenticated inference fail-closed behavior, and actual
migration acceptance remain separate implementation/verification gates.

## Hard boundaries

- Canonical writer TODAY: **Venus**. FUTURE approved target: **Artemis** only after separately verified, operator-authorized migration. No cutover authorized.
- No live database move, restore, failover promotion or host cutover without
  explicit operator approval.
- Mobile devices require distinct independently authenticated credentials.
- No direct remote client access to SQLite, no concurrent writable replicas.
- Shared bootstrap/application/memory files and the global 700-ID ledger
  are reserved for coordinated non-conflicting integration.
- Avoid calling any task complete without entrypoint → composition → execution
  → effect/receipt → durable persistence trace and appropriate test evidence.
