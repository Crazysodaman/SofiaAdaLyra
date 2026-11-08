# CORE-004 C-004-T4 | Exact-head security, timeout and two-host acceptance contract

**DRAFT / NO-GO / NO CERTIFICATION.** PR #254 only. No personal Discord delivery, production Core, protected state or host migration.

## Provenance and status

- Base main: `dd7020ce48c06e82684d3439779266de9ea965b4`.
- Latest branch HEAD MUST be obtained from PR #254 GitHub metadata when executing, not a copied SHA from this document.
- G4 Python 3.12 on Windows and Ubuntu, Rust R2 (debug/release and Python oracles) and cross-gate Windows/Ubuntu **must all report completed PASS on that same exact HEAD**. Workflow checkout now pins `github.event.pull_request.head.sha` (or push SHA) and aborts if `git rev-parse HEAD` differs.
- Earlier queued, pending or superseded/cancelled runs do **not** count.
- Existing G8 real-host acceptance remains **0/16**, with no automatic promotion from unit tests or disposable integration.

## Deterministic authorization ordering matrix

All operations use one canonical writer and the same `sofia.db`. `LifelongThreadStore.admit_turn` uses `BEGIN IMMEDIATE`; revocation and STOP both commit in `BEGIN IMMEDIATE` against this database.

| Ordering | Expected source behavior | Proposed proof |
| --- | --- | --- |
| A: Revoke/STOP **before gateway admission** | Gateway rejects before a canonical user turn exists | Existing `test_core_link_conversation.py` STOP/revoke checks |
| B: Revoke/STOP **after gateway precheck, before SQLite admission** | Admission transaction re-reads enrollment, scope, expiry and STOP; denies; zero canonical turn | `test_core004_admission_fence.py::test_core004_real_admission_denies_change_after_gateway_final_check` |
| C: Revoke/STOP **after SQLite admission, while inference is in progress** | Durable claim remains processing; STOP/revoke can commit without waiting on a model-long SQLite lock. Model/tool effects are NOT automatically cancelled; completed response is withheld on final reauthentication. | `test_core004_concurrent_stop_during_inference_preserves_admission_but_denies_delivery` |
| D: Revoke/STOP **after inference finishes, before gateway forms completed reply** | Gateway's final authenticated check rejects content; canonical completed receipt stays durable; unauthorized client cannot query it | `test_core004_durable_answer_withheld_when_access_changes_before_delivery` |
| E: Revoke/STOP **after last gateway check but before HTTP transmission** | **Unclosed window**: an authorization transition can still occur before `wfile.write`. This implementation must not claim impossible zero-byte delivery. Host owner must define admission/delivery linearization and already-sent-data policy. | Team 1/Platform A design ACK + instrumented transport boundary test; no PASS claimed |

**Security limitation:** Single-process gateway rechecks plus canonical DB admission do not make mTLS reply transmission and cross-process STOP atomic. A lock held over a potentially slow socket can delay emergency STOP unacceptably. The most defensible semantics are: no new post-STOP admission; every new transport request reauthenticates; responses observed under fresh revoked binding are rejected client-side; already committed/in-flight bytes cannot be un-sent. Never infer cancellation of a model or tool solely because a client disconnected.

**Worker generation remains separate.** `SofiaRuntime.core_worker_generation` polls controller `health()` and rejects not-ready/not-accepting worker generations. However the canonical admission transaction currently checks enrollment and STOP, not a writer generation token guaranteed atomic with the worker controller. Team 1 / Platform A must freeze an exact writer lease/generation-fence interface tied to canonical admission and effect dispatch. No second writer and no owner-approved host cutover may be inferred from Core Link selection.

**Effect fencing:** Every non-idempotent capability/tool execution must verify current STOP, valid worker lease and owner authorization at *effect admission*; for already-running work require explicit cancellation receipt or classify OUTCOME_UNKNOWN and audit for reconciliation. Do not claim tool effects were rolled back merely because chat delivery was denied.

## Shared time and recovery contract (candidate for Team 1 / Team 2 ACK)

The following values have distinct meanings, not a chain of four guaranteed synchronous timeouts:

| Timer | Current source default | Required interpretation |
| --- | --- | --- |
| Desktop mTLS client | **30 seconds** | Python HTTPSConnection socket I/O timeout, not strict whole-turn wall clock; new CoreLinkRequest currently also has a **30s server-validated expiry** |
| Ollama `Client(timeout=45.0)` | **Provisional 45 seconds** on Team 2 #253 | Per-I/O timeout; **not** strict total model generation. Model cold-start + allowed quality retry can exceed it |
| Core worker response deadline | **120 seconds** | Core worker processing window; owner must enforce absolute monotonic deadline inclusive of model start/retries, not just one socket read |
| Worker lease TTL | **180 seconds** | Separate lease/writer authority lifetime; 60s reserve beyond nominal 120s does not authorize late effects or constitute durable receipt |

**Proposed bounded protocol, pending ACK:**

1. A client saves stable `idempotency_key`, session and pending content before sending. Caller’s 30s HTTP timeout, lost response, TLS disconnect, or request deadline expiry is **OUTCOME_UNKNOWN** unless canonical evidence conclusively proves no admission. Never silently submit a new key.
2. Host accepts only a fresh authenticated and unexpired request envelope. A 30s request can be admitted initially and remain generating after its original envelope expires; it must not authorize a late new message or reply. Any subsequent result probe is a **new** authenticated request containing the **original turn key** in `conversation.result` payload.
3. Host-owner exact **120s monotonic end-to-end turn budget** is a proposed maximum: session admission, queueing, model cold-start, possible quality retries, persistence and delivery accounting must fit within it. Abort or quarantine late results at the host authority boundary and preserve a durable UNCERTAIN receipt. If an I/O call cannot honor an absolute deadline, it cannot be treated as a bounded end-to-end execution.
4. No automatic model repeat after ambiguous outcome. `conversation.result` under a new currently valid envelope may return `completed` only with the durable source-audience-matched canonical receipt; `processing` / `interrupted` / `uncertain` remain `OUTCOME_UNKNOWN`. Unavailable is not proof it was never admitted when the transport dropped before receipt.
5. `conversation.cancel` currently lacks a trusted mid-call provider abort; a cancel request is **NOT evidence of cancellation** while processing. Mark cancellation requested/unknown only if the future host contract supports an actual receipt; never lie to the client.
6. On reconnect, require same authenticated Core identity, platform and current generation, valid binding and no STOP; call `conversation.result` for pending key before enabling another send. If Core generation rotates, require independently authorized rebind; never auto-rewrite generation/identity.
7. If an admitted turn completes after client timeout, preserve its actual durable response, but only an authorized client may retrieve it later. Do not stream it on an expired original request, revocation, STOP or stale generation. If receipt remains unknown after worker deadline/lease expiry, quarantine and request operator review; no blind retry.
8. Status mapping: **PROCESS_READY** means verified process liveness only; **CORE_READY** requires current writer/generation/STOP and canonical DB readiness; **INFERENCE_READY** requires fresh Team 2 real provider-route evidence. Desktop `READY` requires all three plus authenticated selected binding; otherwise DEGRADED or OFFLINE. RECONNECTING applies only while bounded actual auth reconnect is underway.

This is a contract proposal, NOT an implementation assertion for time budget enforcement or signed readiness. Team 1 and Team 2 must ACK an exact versioned interface, witness negative tests, and classify provider/system clock boundaries.

## Independent Team 5 test plan: two disposable hosts only

Topology: disposable W-CLIENT Windows 11-like Core-free client; disposable D-CORE Debian 12/13 guest with one authoritative Core and one disposable `sofia.db` writer. Inference on permitted loopback/isolated Ollama only. Exact package digest/commit pinned on both. Never touch owner Venus, Artemis production, or live Discord DMs.

| Stage | Action | Required independent witness |
| --- | --- | --- |
| 01 | Install signed test artifacts with exact provenance | Same SHA, OS/architecture, wheel/EXE digests, one writer authority |
| 02 | Enroll client and perform pinned mTLS | Strict host-name/CA/public-key pin + enrolled client fingerprint and scopes; no TLS disable |
| 03 | Exchange two genuine inference turns | Actual Ollama model ID/digest, generated completion request ID, latency, canonical message and evidence refs |
| 04 | Break connection at dispatch, mid-model and after commit | Original durable key, no duplicate inference, OUTCOME_UNKNOWN and authenticated result reconciliation |
| 05 | STOP and revoke at all four deterministic boundaries | No post-STOP admissions, no revoked content delivery; distinguish already admitted effects and bytes |
| 06 | Kill Core worker and restart | PROCESS_READY/CORE_READY/INFERENCE_READY freshness transitions; same identity; new generation; stale binding denial |
| 07 | Inject wrong Core, CA, hostname, client cert, pin and expired credentials | Explicit fail-closed denial; cannot read another audience or session |
| 08 | Windows ACL and Debian private key tests | Non-admin owner, SYSTEM, foreign SID, inherited/unrestricted DACL, redirected path, world/group readable cert key negatives |
| 09 | Inject latency and 30/45/120/180 second boundaries | No automatic replay, no late effects on stale lease, consistent deadline/result receipts |
| 10 | Reconnect and cleanly close | Durable one-response-per-turn invariant, no second writer, no owner/Discord state mutation |

Attach to Team 5 handoff: exact source SHA, checkout assertion, CI run/job URLs, unit results, package hashes, OS/VM names, mTLS certificate *public* fingerprints only, Core identity+generation/lease, request-id/idempotency receipt, Ollama evidence and timestamps, signed admission/STOP receipts and sanitized failure logs. Evidence grades remain SOURCE, DISPOSABLE, INSTALLED, G8 ACCEPTED separately.

**Hold:** CORE SHAKEDOWN READY = NO. PRODUCTION GO = NO. No merge or certification.
