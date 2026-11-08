# CORE-004 C-001-T4 | Admission, readiness and disposable cross-host acceptance

Status: **DRAFT, NO-GO**, owner-directed. No merge, personal Core startup, Discord delivery, real-host cutover or G8 row closure.

Source baseline: `main@dd7020ce48c06e82684d3439779266de9ea965b4`.
Scope: PR #254 and coordination with Core Teams 1/2/3/5 and Platform authority owners A/C.

## 1. Security linearization point (proposed implementation)

On main, CoreLinkConversationGateway checks the mTLS client certificate, current enrollment, STOP, exact platform/Core/generation and scopes, opens a channel, then checks enrollment again *before* calling `service.respond`. Another process can revoke access or activate STOP between that recheck and `LifelongThreadStore.admit_turn`; a previously authenticated request could still be canonically admitted.

PR #254 adds a **bounded** source-level correction to the existing `LifelongThreadStore.admit_turn` transaction:

1. The canonical method already uses `BEGIN IMMEDIATE` to serialize a durable turn claim.
2. When the channel is `core-link`, require a client-source binding and Core Link event reference. In the *same SQLite transaction*, read canonical `core_link_client_access` and `safe_operator_stop`.
3. Deny unless the specified client still exists, is unrevoked, within the effective enrollment time window, has matching principal and audience, and retains the explicit `conversation.send` scope; deny if STOP is active or its state row is absent.
4. Commit the turn claim under that same transaction, so a revocation or STOP committed *before* admission cannot slip through an older in-memory gateway snapshot. A STOP/revoke committed *after* admission cannot retroactively unmake a successfully admitted turn.
5. The mTLS gateway still has sole transport authority: the database admission check cannot authenticate a certificate, a host pin, or the current live Core-worker generation.

**Pending authority signoff:** Platform A / Core Team 1 must verify SQLite shared writer fencing, emergency STOP latency and in-flight cancellation semantics. Core Team 3 must verify canonical audience and replay contracts. This is a draft candidate and does not yet certify atomic generation fencing, in-flight effects, response redaction or full shutdown.

**Concurrency test:** `test/test_core004_admission_fence.py` deliberately revokes enrollment or activates STOP *after* the gateway's final check and before `ConversationService.respond` reaches durable `admit_turn`; asserts no canonical event exists. The positive control proves current enrollment and clear STOP still admit a normal test-provider turn. All tests use disposable temporary state. Validate Linux and Windows exact-head CI and independent forced interleavings.

### Follow-on security requirements

- Tie generation changes to the same host-owned admission fence, or prove a serialized worker generation lease and canonical writer fence enforced across process restart.
- For **already-admitted** in-flight model/tool work: STOP must fence every later effect; never claim a truthful physical cancellation if Ollama has no abort receipt.
- Re-authenticate immediately before publishing a response; if revoked or generation changed, withhold content and keep the durable receipt available only to a future authorized client. Delivery race with late STOP requires a documented terminal semantics and independent test.
- Do **not** hold a global SQLite writer transaction during inference; no multi-second DB lock behind model latency.

## 2. Readiness state contract for desktop and SDK

The legacy `status` response's `state:"ready"` currently represents a reachable authenticated Core Link gateway that reports STOP separately. It is **not an inference-ready attestation**. Do not silently change its meaning in v1 without contract versioning and coordinated client tests.

Proposed client-facing four-state policy:

| Display | Required trusted evidence | Never infer |
| --- | --- | --- |
| **OFFLINE** | No usable selected binding, transport failure, revoked binding, failed server certificate, wrong Core identity, or inaccessible Core endpoint. Preserve last verified identity as *stale*, not active. | Availability from a cached host name. |
| **RECONNECTING** | An actual bounded ongoing reconnect attempt for the **same explicitly selected binding**, with pending turns reconciled before further send. | Connection established merely because a retry was scheduled. |
| **DEGRADED** | Authenticated TLS and exact Core Link identity exist but fresh provider/worker health is absent, STOP blocks conversations, a pending turn is uncertain, or the Core is not conversation-capable. Status must display the reason, not expose private memory or secrets. | Inference ability from the TLS handshake or deterministic test response. |
| **READY** | Fresh, signed/host-authenticated Core worker generation observation, STOP clear, current scopes, exact selected binding and trusted endpoint, plus a **real successful inference-route health proof** within a bounded TTL and no unresolved pending turn. | Successful mock provider, skipped integration, or old successful reply. |

Provider health must come from Team 2's actual cognition/inference path; worker generation must come from Team 1's authoritative lifecycle. A proposed bounded readiness evidence record should include `protocol`, `core_identity_id`, `platform_id`, `core_generation`, `checked_at`, `expires_at`, `worker_state`, `provider_route`, `inference_health`, and a non-secret provenance/receipt reference. It must be authenticated, freshness-fenced and refused on mismatch; do not include prompts, responses, credentials or raw owner state.

**Current draft behavior:** The minimal Tk Core Link desktop now reports `DEGRADED · authenticated Core Link; inference unverified` on successful v1 connection, `OFFLINE` on a failed operation, and provides a **manual Reconnect** button that displays `RECONNECTING` while the actual reconnect task runs. The SDK wire status and gateway status are not changed, and READY is intentionally not displayed without the future provenance owner contract.

## 3. Protocol compatibility requirements

- Python mTLS request and response decoders reject duplicate object keys and non-finite JSON at all nesting levels through the existing strict decoder.
- Preserve v1 schema, field set, wire byte limit, request-id correlation, exact Core/platform/generation binding, deadline and TLS certificate/public-key pin.
- Check the existing Rust/Python shared `contracts/core-link/valid-*.json` fixtures against the strict Python decoder and typed SDK round-trip. Rust R2 remains *read-only* and is not a replacement conversation transport.
- Test missing/extra fields, oversized frames, invalid UTF-8, invalid content-length, invalid TLS CA, wrong public key pin, wrong identity, stale generation, expired enrollment, revoked scope and STOP. Tests must distinguish local parsing denial from actual remote dispatcher denial.
- Existing default `PinnedCoreLinkClient` timeout is 30 seconds, while optional Core-worker `response_timeout_seconds` is 120 seconds. Team 1/2 must align worker/provider/deadline handling, preserve uncertain outcome semantics and ensure a slow model cannot silently trigger a duplicate inference.

## 4. Disposable two-host acceptance topology

- **W-CLIENT:** clean disposable Windows 11-like client/desktop or Windows runner, Core-free role `CORE_LINK`, owner-private local binding/state only, unique Platform ID, no writable canonical Core database.
- **D-CORE:** isolated Debian 12/13 guest with one installed optional Core worker, one unique disposable Core identity, canonical `sofia.db` in the guest only, generation 1 then supervised restart to generation 2. No production Artemis or Venus state.
- **Inference:** Team 2-owned explicitly isolated test model/provider with genuine observed inference call. Model name, response provenance and elapsed time must be recorded without uploading a private prompt.
- **Transport:** mutually authenticated TLS, per-host test-only CA/leaf certificates, certificate host-name verification, pinned server public key, exact enrolled client ID, audience and scopes. Never use `verify=False`, shared production certificates or a duplicate Core writer.
- **Channels:** local simulated client only. Do not enroll or deliver to personal Discord DM.

Run the same signed build at exact SHA on both disposable installed hosts, then record:

1. Boot and authenticate; verify selected remote Core ID, platform ID, Core generation, certificate pins and UTC TTL.
2. Send two distinct **genuinely generated** messages through the canonical SDK boundary. Check the durable assistant/user receipt IDs and the actual provider evidence.
3. Abruptly break network during a turn: record `OUTCOME_UNKNOWN`, query `conversation.result`, reconcile after reconnect, never blindly resend with a different idempotency key.
4. Replay identical idempotency key: one canonical user/assistant result and no duplicate inference. Conflicting payload with the same key must deny.
5. Restart *only* the disposable Debian Core: bind generation 2 only after authenticated re-enrollment/reconciliation; stale generation 1 denied. Preserve the same core identity and authorized session history; reject unrelated or replaced Core identity.
6. Inject wrong-host certificate, wrong CA, wrong pin, stale/expired/revoked access, changed audience/scope, STOP-before-admission, STOP-during-inference and STOP-before-delivery, latency/timeout and private-file ACL negatives.
7. Verify client status moves through OFFLINE/RECONNECTING/DEGRADED and becomes READY **only** on agreed fresh worker+provider evidence. Shut down both clients cleanly.
8. Preserve separate signed receipts: source SHA, wheels/binary hashes, OS versions, certificate public fingerprints, model ID, endpoint identity, Core writer lease/generation, request/turn IDs, observed latency and failure outcomes. No secret keys, owner transcripts or private data in logs.

Evidence grades: **SOURCE** is implementation/tests in Git, **DISPOSABLE** is observed isolated execution, **INSTALLED** is actual same-release two-host installed-host acceptance, **G8** is independently accepted owner checklist. There are **0/16 accepted G8** items as of this draft.

No merge or certification without cross-team signoff, exact-head CI green, installed-host security/continuity proof and Team 5 acceptance.
