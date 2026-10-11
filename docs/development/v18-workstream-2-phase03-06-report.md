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
