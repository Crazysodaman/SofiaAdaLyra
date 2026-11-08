# CORE-004 / C-006 | Development-first functional evidence and IG-001 handoff

**Scope:** isolated draft PR #254. No release certification, merge, protected-state mutation, production Core/Discord operation or host cutover. Main remains unchanged. Use the PR metadata for the **latest** SHA, not this document's source snapshot.

## Actually executed locally, 2026-11-08

Environment: isolated Linux 6.18.57 x86_64 container; Python 3.13.5; pytest 9.0.2; cryptography 46.0.4. No complete Sofia worktree was mounted; environment cannot resolve github.com for `git clone`. GitHub connector was used to retrieve and compare exact source excerpts.

Command:

```bash
python -m pytest -q test_core004_source_probe.py \
  test_core004_disposable_tls_probe.py \
  test_core004_sqlite_order_probe.py \
  test_core004_provider_deadline_probe.py
```

**Observed: 24 passed, 0 failed, 0 skipped in 2.30s.** These are four **independent disposable probe suites**, not direct execution of the original repository test files. Local evidence ZIP SHA256: `1331ab5ad0529d2470a949fc203cf7e4f893be145429562b55a06a13746dc841` (exported to this coordinating conversation, not installed as a GitHub release artifact).

- 9/9 desktop source-method probe: exact extracted `_request`, `send`, `_clear_settled_turn`, `reconcile_pending`, `refresh_history` source from Team 4. A transport response dropped after one synthetic gateway completion leaves the original durable client key, refuses another send, and recovers with `conversation.result` without second synthetic inference. Positive message routing, multi-page newest-history and duplicate cursor negatives included. Extracts were checked against GitHub source length/Adler32.
- 4/4 **genuine loopback TLS socket** test double: ephemeral CA with proper X509 extensions; client cert required; server public-key SHA256 pin and CA/hostname enforced; lose the first HTTPS reply without reading, reconnect with same client identity and key, recover a single stub result; wrong host pin/missing client certificate/revoked result denied. This is **NOT** Sofía CoreLinkServer or canonical enrollment.
- 7/7 **genuine SQLite transactions with simplified authority schema**: STOP/revoke before canonical-style admission, between gateway precheck and commit, while an admitted fake inference is blocked, plus last-check-to-wire TOCTOU model. The full LifelongThreadStore and host SAFE approvals were **NOT** exercised.
- 4/4 **exact Team 1 provider deadline source**: retrieved from Team 1 draft PR #256 SHA `20bf12a3613f1ad5a4d9b9cc8541651827805f8a`, source blob `5cd8e865c3ed0bc3f645869a7d084ebbd1958b9d` matched by local `git hash-object`. Quick completion, blocking timeout, typed error and already-expired deadline tested. Its daemon worker is NOT physically cancelled and the full IPC/RUN generation fence is NOT verified.

Earlier direct strict-model JSON parser local vectors: **7/7 passed**, source blob `f107e51f7bdd34195bca2cddc7bfedf52e8b134f`. These are separate from the most recent 24-test run; do not double count them as full integration.

## PR #254 functional code/tests staged (NOT full-repo executed here)

- Fix the Core Link Desktop stale first-100-message bug by authenticated forward-page traversal with one newest-100 bounded projection, strict cursor/order/replay denial and no partial history publication; `test/test_core004_history_paging.py` added. A very long session (over 3200 messages) still requires a versioned server-side seek-latest API; current implementation fails explicitly.
- Keep the 30s client envelope deadline. On a lost transport response, retain the original pending turn key, classify `RemoteTurnUncertain`, and reconcile only with `conversation.result`, never automatic resend. `test/test_core004_client_deadline.py` staged.
- Strengthen opt-in genuine Ollama test to require observed real `ollama.Client.chat()` calls and nonempty content for the exact selected model. Normal CI skips it; **not executed** without an isolated installed model and full repository.
- Add `test/test_core004_real_mtls_reconnect.py`: exercise real **repository** `CoreLinkServer` and `PinnedCoreLinkClient` over disposable mTLS with a **fake gateway**, drop a response after actual POST completion, recover with a new desktop instance and one original key, enforce wrong-host pin denial. This is **committed source only** until Team 5 executes it. The separate local TLS test double passing does not automatically certify the repository test.
- Preserve original STOP/revocation canonical `BEGIN IMMEDIATE` admission and post-inference reply recheck candidates. Original full `test/test_core004_admission_fence.py` remains **unexecuted** in this environment.

## Team 5 executable disposable target (one IG-001 integration branch only)

From **the same integrated exact SHA** with all four teams' source blobs pinned and verified, on an isolated VM with temporary `SOFIA_STATE_ROOT`:

```bash
python -m pytest -q \
  test/test_core004_real_mtls_reconnect.py \
  test/test_core004_wire_security.py \
  test/test_core004_admission_fence.py \
  test/test_core004_client_deadline.py \
  test/test_core004_history_paging.py \
  test/test_core_link_conversation.py \
  test/test_core_link_binding.py \
  test/test_core_link_desktop.py
```

Then opt into Team 2's genuine Ollama integration on a **disposable loopback model only**; collect actual provider route/model digest, canonical durable receipts, host identity/generation, TLS public certificate fingerprint, revocation/STOP UTC ordering and timeout/late-result evidence. One client disconnect must preserve original idempotency and the canonical model-call count must remain one. If a real client disconnects during generation, `OUTCOME_UNKNOWN` must not itself cause another inference; require fresh authenticated result reconciliation. Do not use personal Discord.

### Timeout and authority coordination

- **30s Desktop**: HTTP timeout and v1 request deadline; timeout/connection-loss is ambiguous, not proof of failed inference. Preserve key, return uncertain, no resend.
- **45s Team 2 Ollama**: per-I/O not strict wall-clock; model may need two calls for quality repair.
- **120s Team 1 Worker**: new `provider_deadline.py` bounds parent wait using monotonic time; leaves a late provider daemon thread running, never forwards its late result through that request. Team 1 must independently show old Core generation quarantine and no stale effect when the provider later completes.
- **180s lease TTL**: separate writer authority; must be independently fenced at every effect/admission boundary. No 180s grace permission for unauthorized actions.
- **PROCESS_READY** is liveness; **CORE_READY** is current canonical state/writer/STOP/generation; **INFERENCE_READY** is proven real provider health. v1 link status `ready` is not inference readiness.
- Last pre-send authorization check → physical socket bytes remains an unresolved TOCTOU; already-sent bytes cannot be revoked. No claim of physical cancellation, release signoff or G8.

**Pending:** full original Python/Windows/Linux package pytest, actual integrated Team 1+2+3+4 Core, genuine model conversation, separate Windows-client/Debian-host installed mTLS, authority ACKs, independent Team 5 IG-001 signed receipts, end-of-IG-001 exact-SHA CI. CORE SHAKEDOWN NO-GO, production NO-GO. G8 remains 0/16.
