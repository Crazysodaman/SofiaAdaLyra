# V18 Partial-Wiring-First Coding Queue (44 original CA IDs)

**Source:** exact original V18 master list, not a re-created checklist. Current GitHub main: `2fe9c1240a9db88fb514297e4c6075decec9cade`. All statuses below are source-audit states. **No tests were run and no task is production accepted.** A coded slice is not a closed phase. The canonical state writer host is intentionally undecided; no live cutover is authorized.


## Phase 01

- **CA-2205** (new source repair: `da78b538`): CA-2205 P0 [GAP] Create a durable LIFE job-result reconciler that handles `COMPLETED`, `FAILED`, `BLOCKED`, `CANCELLED`, `UNCERTAIN` and expired jobs independently; never replay an uncertain mutation without proof.
- **CA-2216** (new source repair: `845694f5`): CA-2216 P2 [GAP] Add canonical-derived operator diagnostics for the exact reason LIFE is idle, blocked, reviewing, awaiting permission, uncertain or finished, with no second authoritative scheduler state.
- **CA-2302**: CA-2302 P0 [RED CI] Investigate Release Candidate Build run `38063542675` failing at `Run revision-bound verification gate`; obtain gate output, exact failing check and revision evidence. Do not infer cause from job status alone.
- **CA-2304** (new source repair: `7b1c1d80`): CA-2304 P0 [VERIFY] Reconcile markers and failing package suites, especially `pkg_body` test selection, without relabeling or hiding failures to make badges green. Record separate unique test roots versus multiply marked copies.
- **CA-3004**: CA-3004 P0 [VERIFY] Add a release packaging truth check: confirm the code tested is precisely the archived/wheel-installed revision, the gate does not accidentally test a different editable checkout, and wheel reproducibility/signing prerequisites remain enforced. Distinguish source verification from installed-wheel smoke verification.
- **CA-3005**: CA-3005 P0 [CONFIRMED WINDOWS FAILURE] Reproduce the `pkg_verify` Windows `WinError 32` from `test_cognition_v2_baseline.py` / `src/sofia/verify/cognition_v2_baseline.py` `TemporaryDirectory` deletion of `sofia.db`. Investigate application shutdown, open SQLite connections, `RUN`/LIFE worker futures, WAL/checkpoint activity, and delayed file handles; close owners deterministically before cleanup. Do not mask by sleeping blindly or ignoring cleanup errors.
- **CA-3006**: CA-3006 P0 [CONFIRMED CI CONFIG GAP] Fix `pkg_body` test selection: `test/test_body_matrix.py` exists but no `test_body_` filename mapping in `test/conftest.py`; presently `pytest -q -m "pkg_body and not integration"` selects zero tests (`4036 deselected`). Add explicit package ownership and required real BODY safety/simulator coverage. Assert package selection remains nonempty.
- **CA-3014**: CA-3014 P1 [STILL MISSING] With path repair merged, close LIFE's remaining automatic artifact evaluation, objective verification, staged critique, iterative revisions, milestone/status advancement and truly verified long-term memory/interest feedback. Current `life/coordinator.py:905` still dispatches an initial artifact only.

## Phase 02

- **CA-1904**: CA-1904 [GAP] Require action-specific intent, target identity, expected effects, bounded arguments and a fresh permission decision immediately before approved execution; do not reuse an earlier plan as an authorization token.

## Phase 03

- **CA-3702**: CA-3702 P0 [DESIGN/RESEARCH] Specify crash-only/uncertain action recovery for LIFE → RUN → VM → Fleet across each point of failure, especially where the command may have executed but its receipt is missing.
- **CA-5201**: CA-5201 [DESIGN/RESEARCH] Identify active owner for `sofia.db`, canonical persistent-asset root and every secret-key authority; resolve Windows/Linux platform file paths and legitimate database access paths; forbid two competing writers after failover.
- **CA-6101**: CA-6101 [DESIGN/RESEARCH] Design a single canonical write owner in `sofia.db`, with hot event metadata, active state, memory provenance, tombstones and archive catalog. Define WAL-on-one-host constraints and fenced owner failover; no multi-host SQLite WAL on SMB/NFS.
- **CA-6804**: CA-6804 [DESIGN/RESEARCH] Define recovery behavior if existing state is missing/unmounted/locked: do not silently create a second identity or new empty canonical DB, never promote a stale read-only copy, present authenticated candidate choices, keep external actions blocked until verified.
- **CA-6807** (new source repair: `248dcb9a`): CA-6807 [DESIGN/RESEARCH] Define destination preflight: owner-specified local path, disk capacity/free growth, permissions/ACL, filesystem type, encryption, symlinks/reparse-point traversal, process access, case and path normalization, anti-rollback lineage and exact host ownership.

## Phase 04

- **CA-6302** (new source repair: `1be739c9`): CA-6302 [DESIGN/RESEARCH] Specify a canonical acknowledge-and-order event protocol: stable client-generated event IDs, origin device/session, client timestamp versus trusted server receipt time, monotonically increasing canonical thread sequence, deduplication and exactly-once *logical acceptance*, not false promises of exactly-once physical actions.
- **CA-6303**: CA-6303 [DESIGN/RESEARCH] Compare safe choices for offline companion behavior: drafts-only (baseline) versus visibly provisional local inference against approved cached context. No separate authoritative Sofía, SAFE grant, relationship owner or unsupervised external action while disconnected.
- **CA-6304** (new source repair: `2fe9c124`): CA-6304 [DESIGN/RESEARCH] Design reconnect conflict handling: server-confirmed order, no dropped or silently overwritten messages, explicit edits/tombstones, stale replies marked, project-thread versus Main routing, device presentation cursors, privacy partitions and owner-visible conflicts.
- **CA-6306** (new source repair: `2fe9c124`): CA-6306 [DESIGN/RESEARCH] Define failure-mode ladder: full cognition, limited approved offline read-only/search, durable unsent draft capture, and safe unavailable state. For missing GPU/model, broken Fleet, stale database, disk-full, low-power and network outage, specify truthful UI/Discord messages and safe recovery.
- **CA-6405**: CA-6405 [DESIGN/RESEARCH] Create one cross-modal observation receipt schema for voice transcription, screen sight, environmental conditions, Fleet sensors, app APIs and web results: trusted source, actual observation time, expiry, original data access, privacy, model interpretation confidence and 'not observed' representation. Explicitly separate inference from ground truth.

## Phase 05

- **CA-4103**: CA-4103 [DESIGN/RESEARCH] Design explicit Authenticated Identity Link: desktop owner login, verified Discord DM bot/user/channel binding, mobile device pairing and future web clients map to one approved principal; no matching by display name or arbitrary session ID.
- **CA-4104** (new source repair: `493a4f62`): CA-4104 [DESIGN/RESEARCH] Design a Channel-to-Thread Association mapping with independent authentication, audience, device revocation, binding generation and operator-selected default thread. Reuse existing binding owner tables; avoid duplicating session source-of-truth.
- **CA-4105**: CA-4105 [DESIGN/RESEARCH] Resolve `SocialSessionStore` audience immutability: a shared conversation must not blindly reuse an audience-bound session under a different audience. Propose separate thread ownership and per-event origin/audience rights, with migration and backward-compatibility plan.
- **CA-4106**: CA-4106 [DESIGN/RESEARCH] Design persistent message/event model with monotonic per-thread sequence, stable message ID, principal, origin channel/device, original audience, reply target, created/received timestamps, moderation/privacy labels, edit/correction/reference IDs and generated response receipt.
- **CA-4107**: CA-4107 [DESIGN/RESEARCH] Specify per-message view authorization for private/local/Discord/mobile/team content. Same user identity does not imply every surface can receive every secret, private artifact, tool output or operational credential. Show redacted placeholders rather than leaking.
- **CA-4109**: CA-4109 [DESIGN/RESEARCH] Define cursor-based history synchronization across desktop, Discord gateway and phones with reconnect catch-up, pagination, edits, delivery acknowledgments, idempotent sends, offline queue and 'last seen' markers. Device restart must not reset logical conversation.
- **CA-4110**: CA-4110 [DESIGN/RESEARCH] Design concurrent turns using an ordered thread append/lease or serialize-at-generation boundary: two rapid messages from different devices must not create conflicting histories, duplicate responses or stale follow-up questions; cancellation/retry must have explicit outcomes.
- **CA-4111**: CA-4111 [DESIGN/RESEARCH] Design authentication and exposure for remote device access via a narrow HTTPS/mTLS gateway and client clients. Do not remotely mount/share SQLite or grant devices direct database writes; evaluate LAN-only and Zero Trust access without assuming an existing connector provides chat UI.
- **CA-5302**: CA-5302 [DESIGN/RESEARCH] Model each message as an authenticated event: thread ID, channel/account/device, principal, original audience, per-audience visibility, monotonic sequence, signature/receipt where applicable, correction pointer and duplicate-delivery key.
- **CA-5304**: CA-5304 [DESIGN/RESEARCH] Preserve channel-local security: a message sent from Discord gets Discord-scoped capabilities even if Sofía sees desktop history; no capability grant ever follows a copied chat event to a new device.
- **CA-5306**: CA-5306 [DESIGN/RESEARCH] Define concurrent-turn arbitration, cancellation and dedup semantics for user submitting simultaneously from Discord, UI, Terra or phone; one authoritative turn ordering without global permanent lock on unrelated tasks.
- **CA-5307**: CA-5307 [DESIGN/RESEARCH] Design 'continue on this device' UX: authenticated device pairing, visible current thread, audience visibility warnings, opt-in cross-channel mirroring, encryption in transit, push notification privacy and immediate revoke.
- **CA-5502**: CA-5502 [DESIGN/RESEARCH] Specify a reversible migration of historical desktop, Discord and mobile session bindings into Main without changing the original audience-bound rows. Include overlap dedup, timestamps, source provenance, ability to preview/import/reject, partial migration rollback and exact before/after audits.
- **CA-5503**: CA-5503 [DESIGN/RESEARCH] Decide and document the Main cross-device *view* policy: approved owners can read eligible Main events; locally protected material is redacted unless explicitly reclassified; never automatically copy Venus messages to Discord's platform history. Provide user-visible reason/controls when an excerpt is unavailable on a device.
- **CA-5505**: CA-5505 [DESIGN/RESEARCH] Specify canonical event identity, server sequence, origin/receive times, client nonce/idempotency key, per-device cursor, device revocation and reauthentication. Resolve concurrent Discord/UI writes deterministically; client-side times and copied session IDs can never establish authority.
- **CA-5508**: CA-5508 [DESIGN/RESEARCH] Define asynchronous delivery and degraded-mode states for devices that are offline, have expired keys, switch networks, or reconnect after months. Specify reconciliation of queued messages, uncertain external delivery, revoked devices, tool receipts and server-side generated event gaps.

## Phase 06

- **CA-5603**: CA-5603 [DESIGN/RESEARCH] Specify incremental message/archive APIs to replace full-session materialization for hot-path conversation and `ConversationOriginalRetriever`: stable keyset pagination, indexed time ranges, precise message-ID retrieval, schema/provenance checks and bounded memory footprint.

## Phase 09

- **CA-101**: CA-101 [GAP] Connect trusted, eligible ordinary observations and experiences to LIFE interest creation/revision, with confidence, evidence, and optional retirement. `revise_interest()` exists, but production experience-to-interest wiring was not found.
- **CA-104**: CA-104 [GAP] Trigger grounded `evaluate_artifact()` for completed outputs, recording technical checks, personal judgment, objective results, evidence, and preference changes.
- **CA-105**: CA-105 [GAP] Independently decide to critique, revise, produce another artifact, advance a milestone, pause, abandon, or complete a project. Require justified limits on rework and cost.
- **CA-106**: CA-106 [GAP] Automatically reconcile LIFE state with canonical GOALS and RUN receipts after each decision, including failures, rejection, and uncertain results.
- **CA-110**: CA-110 [GAP] Add a durable project `review_due` / `awaiting_verification` / `next_milestone_due` decision policy derived from existing project/jobs/evaluation records, using idempotent keys rather than an independent new state machine.
- **CA-112**: CA-112 [GAP] Trigger `evaluate_artifact()` from the recurring LIFE worker with typed objective results, bounded personal judgment, source receipts and failure/unknown handling; speculative LLM critique alone is not evidence.
- **CA-113**: CA-113 [GAP] Implement a policy-driven transition table: `CREATE → VERIFY → CRITIQUE → REVISE | COMPLETE | PAUSE | ABANDON`; track milestone status using the already implemented `update_milestone()` and `complete()` methods.

## Phase 11

- **CA-6608**: CA-6608 [DESIGN/RESEARCH] Design an approved model promotion transaction: compatibility preflight, pin previous model, settle inflight turns, update role mapping atomically, health/continuity check, acceptance receipt and explicit restore on failure.

## Deferred acceptance boundaries

- Phase 01 red CI job/root-cause evidence, exact Windows `WinError 32`, package marker selection and release-wheel equality require actual workflow execution. Existing source repairs do not prove historical CI success.
- Phase 03 needs an operator-selected writer host, independent fencing, real restore, protected key/identity continuity and split-brain recovery proof before any active pointer switch.
- Phase 04/05 need cross-transport canonical thread acceptance, per-event audience authorization, causal edits/tombstones and real Android/Discord/Desktop multi-device verification. Phone-only ordering is not global ordering.
- Phase 09 requires independent objective/source receipts, bounded long-horizon autonomy and host live evidence; RUN result is not subjective success.
- Phase 11 model swapping remains approval-gated; code preparation is not an owner-approved model installation, promotion or rollback drill.
