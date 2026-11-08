# CORE-001 C-003-T1: Runtime authority, deadlines and independent QA

Status: **DRAFT / NO-GO**. Team 1 PR #256, isolated branch
`chatgpt/core-team1-lifecycle-c001-20261108`.
Pin the actual PR HEAD when testing; this document is not a certification.

## Authority states (not synonyms)

- **PROCESS_READY**: exact live child PID + unique launch token + same
  resolved state + validated local generation marker. This is explicitly
  not proof of canonical writer authority, Core cognition, owner enrollment
  or provider availability.
- **CORE_READY**: a process-ready Core whose expected generation is a
  positive current RUN generation, whose local watchdog lease is unexpired
  and matches that epoch, with durable STOP inactive and a healthy fresh
  generation-bound application heartbeat. The service backend checks this
  before reporting ready. Local lease authority **does not** establish
  cross-host partition safety, signed Platform authorization, or admission
  of an unrelated desktop writer.
- **INFERENCE_READY**: an actually successful permitted request to the
  configured provider/model/digest within the effective turn deadline,
  with attributable execution evidence. Neither a heartbeat nor an
  Ollama process port or synthetic test reply proves this state.

No readiness may be interpreted as authority to activate a signed worker.
Platform A (canonical management / SAFE / STOP / owner principal and
generation) and D (signed, supervised component worker) own the approval
boundary. Keep the installed Core UNKNOWN/DEGRADED rather than READY
when that boundary or the actual provider probe is unavailable.

## C-003 source fixes

1. The Windows service child requires a positive expected generation and
   current local watchdog lease before starting application work.
2. The child rechecks generation, live lease and STOP after startup and
   while running. OS process lock resource `core-runtime` denies a second
   service-hosted child on the same local state. This local lock does not
   fence independent UI starts or cross-host writers.
3. The SCM host checks the same authority before spawning a child.
4. The RUN service backend withholds CORE_READY if authority is absent,
   revoked or STOP is active; an error reading authority is not READY.
5. The per-start readiness document is PROCESS_READY only, pinned to
   PID, resolved state, unpredictable launch ID and expected epoch.
6. Bootstrap and active-release loops both detect unexpected child exit;
   failed spawn and invalid/missing/dead/stale readiness clean up with a
   bounded shutdown. An unverifiable forced exit is not misreported stopped.

The checks are not transactionally fused with every downstream side effect.
A racing STOP, lease expiry, or revocation still requires per-turn,
pre-effect and pre-result acceptance fences at the canonical Platform and
Core Link boundaries. That end-to-end proof is outstanding.

## Deadline mismatch and proposed contract (NOT ACKNOWLEDGED)

Observed on baseline main: Core Link desktop request deadline +30 seconds,
client HTTPS timeout 30s, server socket timeout 30s; Core worker request
budget 120s, worker lease TTL 180s. Team 2 draft #253 proposes Ollama
`Client(timeout=45.0)`, a **per-I/O bound**, not a strict overall inference
deadline; quality policy can retry once. The composed timeout has no proven
unified cancellation or durable outcome-unknown response protocol.

Proposed safety invariants, requiring Teams 2/4 and Platform A/D ACK:

- Assign each admitted turn one opaque idempotency key, request ID, initial
  signed/authorized generation, current STOP/SAFE/lease projection and one
  monotonic/UTC absolute deadline. Effective Core worker deadline is the
  minimum of admitted client deadline, 120s configured Core worker limit,
  and remaining live RUN lease. Worker TTL 180s is an *upper bound*,
  not permission to run for 180s.
- Provider I/O <=45s per attempt, at most one quality retry when the
  *remaining total* time can accommodate it; late data or a hung provider
  cannot extend the absolute deadline. The provider setting alone does not
  enforce the global deadline.
- **30s client behavior must be resolved**: either (A) a genuinely durable,
  authorized PENDING/UNKNOWN outcome with status/cancel/reconnect and
  exactly-once idempotent recovery or (B) an independently approved bounded
  synchronous client timeout >= Core deadline plus transport margin
  (candidate 135s). A 30s abort is not proof the worker stopped.
- On transport timeout, do not automatically reissue with a new key, mark
  success, or assert inferential failure. Report OUTCOME_UNKNOWN until an
  authenticated exact-key result is checked. Re-authorize before reading any
  result or replay. A cancel request is not a cancellation receipt.
- Re-check STOP, revocation, principal/audience, generation, request deadline
  and active RUN lease at admission, immediately before side effects, after
  model result, and before history/response commit. If changed, drop/deny
  late results and retain only privacy-safe terminal/unknown receipts.
- Automatic retry, recovery after restart, and late-message de-duplication
  are DENIED by default until durable per-turn receipts are actually
  implemented, crash-tested and independently certified.

## Full-checkout verification on draft PR

CI `.github/workflows/core001-lifecycle-regression.yml`, Ubuntu 24.04
and Windows latest, Python 3.12:

```sh
python -m pytest -q \
  test/test_run_release_process.py \
  test/test_run_runtime_child.py \
  test/test_run_runtime_authority.py \
  test/test_run_host.py \
  test/test_run_supervisor.py \
  test/test_ui_tray_lifecycle.py \
  test/test_core_worker_process.py
```

No queued check, local unit test, provider=test stub, or application event
is an installed-host PASS.

## Core Team 5: disposable installed-host execution plan

Target two freshly provisioned hosts with synthetic identity, private
disposable SQLite, no owner secrets or production channels. One isolated
Windows SCM host, one isolated Debian 12 systemd host; pin installed
artifact SHA256 and exact source SHA. Before each fault, record PID(s),
generation, active lease owner/epoch/expiry, STOP/SAFE projection, process
lifetime lock, readiness phase, app heartbeat timestamp, model availability
and visible result lineage.

1. START: valid signed installation + operator enrollment + one active
   writer; observe PROCESS_READY then independently proven CORE_READY.
   Do not label INFERENCE_READY until a real pinned provider reply.
2. NO AUTHORITY: absent/revoked/expired lease, missing/wrong epoch, STOP
   active, untrusted package or stale publication: deny Core startup,
   readiness, post-recovery effects, and any alternate service bootstrap.
3. DUPLICATE: concurrently launch two service-hosted children for one state;
   exactly one may start. Also attempt desktop + service and alternate-host
   startup to demonstrate whether a broader writer exclusion exists;
   report unproven paths, do not improvise a second canonical writer.
4. STALE/DEAD: reused ready document, wrong PID/path/launch nonce/generation,
   process exit before/during/after ready publish, corrupt/truncated marker.
   Never report CORE_READY after the child is dead or authority is lost.
5. STOP: normal SCM stop, repeated stop, grace timeout, forced terminate,
   kill timeout, unverified exit and watchdog restart suppression. Verify
   no orphaned child remains and recovery never bypasses durable STOP.
6. RESTART: hard kill while writing synthetic transaction; run SQLite
   integrity_check and WAL recovery, preserve same synthetic identity,
   require a newly fenced generation before post-restart writer effects.
7. WORKER: genuine signed worker staged replacement, wrong signature/ABI,
   old/new generation concurrent attempt, rollback after uncertain old exit,
   revoked enrollment and stale provider binding. A/D must verify.
8. INFERENCE: Ollama absent, broken runner, model missing, slow >30s,
   45s I/O stall, quality retry, 120s worker expiry, lease expiry during
   generation, client disconnect/cancel, late provider result and restart.
   Do not publish late unauthorized results; verify durable UNKNOWN receipts.
9. RECONNECT: authorized desktop/Discord session uses the same original
   turn ID/idempotency and private audience, never duplicate a historical
   reply, and refuses stale generations or revoked principals.
10. Collect command logs, installed manifest/signature digests, exact
    host identity, artifact SHA256, starting/ending PID and process tree,
    relevant service manager events, independent SQLITE/writer receipts,
    timing and PASS/FAIL/UNKNOWN **for each** scenario.

**Team 5 acceptance remains NO** without physical installed-host evidence.
No production startup, Core writer migration, canonical state copying,
merges or G8 acceptance promotion are permitted by this plan.
