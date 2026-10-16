# Durable asynchronous FIDO2 owner approval inbox

**Source:** `src/sofia/safe/approval_inbox.py`, `src/sofia/safe/approval_inbox_cli.py`, `src/sofia/ui/owner_inbox_window.py`.

## Operator-selected configuration

| Control | Fixed value |
| --- | --- |
| Pending owner request TTL | 24 hours |
| WebAuthn challenge TTL | 90 seconds, issued when owner opens review |
| Signed exact-action receipt TTL | 600 seconds |
| Pending requests durable | Yes, canonical `sofia.db` only |
| Protected/unknown/level-5 proof | Enrolled physical FIDO2 security-key credential with user verification |
| First-key bootstrap | Separate supervised Windows Hello first-enrollment workflow |
| Local review lease | 3 minutes, fenced by unpredictable review token |
| Notification semantics | SQLite outbox, at-least-once delivery, monotonic event IDs |

## Local setup (Venus, sole approved writer)

Do **not** auto-enroll hardware, copy credentials, change file ownership,
migrate `sofia.db`, start a second writer or silently install a service.
The owner's Windows token SID is pinned by the existing enrollment workflow.
Before enrolling, independently verify the canonical writer, backup/recovery,
native browser and compatible Windows Hello/physical FIDO2 hardware.

First-time key enrollment commands are documented in
`docs/development/hybrid-owner-authentication-2026-10-11.md`.

An operator can create a **request** without creating authority:

```powershell
python -m sofia.safe.approval_inbox_cli request --capability fleet.enroll --parameters-json '{"host_id":"Artemis"}'
python -m sofia.safe.approval_inbox_cli list --status pending
python -m sofia.safe.approval_inbox_cli notifications
python -m sofia.safe.approval_inbox_cli recover
```

The owner can open **Settings → Permissions → Open durable FIDO2 approval inbox**.
This window shows exact parameters and fingerprint. The owner chooses an
enrolled security key and confirms its native browser challenge. The GUI
runs signing in a worker thread; it never approves a request automatically.
The Settings screen also shows durable pending and notification counts.

Equivalent attended CLI ceremony:

```powershell
python -m sofia.safe.approval_inbox_cli approve --request-id "REQUEST-UUID" --credential-id "ENROLLED-CREDENTIAL-ID"
python -m sofia.safe.approval_inbox_cli deny --request-id "REQUEST-UUID"
```

`--credential-id` selects an existing **public credential identifier**,
not a secret, proof, or bypass. A native browser signature with user
verification remains mandatory; wrong Windows SID, missing owner signature,
invalid origin/challenge, unknown credential, revoked key and replay fail closed.

## Consumption and integration

From a trusted capability request path (NOT from a model-supplied approval):

```python
from sofia.safe.approval_inbox import ApprovalInbox

inbox = ApprovalInbox(canonical_path)
pending = inbox.create("fleet.enroll", {"host_id": "Artemis"})
# SAFE persists pending request and owner notification. Do other work.
# Owner separately opens the Settings inbox and approves with real FIDO2.
approval_id = inbox.approved_receipt(
    pending.request_id, capability="fleet.enroll",
    parameters={"host_id": "Artemis"},
)
# Existing effect code MUST recheck STOP, authority, target state and use
# ExecutionApprovalVerifier.consume(approval_id=..., capability=...,
#                                   parameters=..., now=...) before effect.
```

`approved_receipt` is a preflight only. No automatic effect dispatcher is
installed by this implementation. It must be integrated into each host
capability's execution boundary, which retains its existing checks.

For a trusted owner-only transport adapter, call
`deliver_notifications(send)`, where `send(event)` is a synchronous
transport that raises on failure. It receives only immutable event metadata
and must route to an independently authenticated owner audience; do not
accept a channel, destination or webhook URL from model output.
If delivery succeeds but process crashes before commit, the event may be
redelivered. Consumers de-duplicate on `event_id`. The local inbox GUI
already drains events into the owner UI while open.

**Discord push and Debian remote WebAuthn are not part of this local
Windows-SID implementation.** They require separately authenticated owner
channel/HTTPS RP domain bridging after a witnessed sole-writer cutover.

## Recovery and failure modes

`ApprovalInbox.__init__()` performs startup recovery automatically; 
`ApprovalInbox.recover()` can also be called from the CLI or on periodic
owner UI refresh. It expires pending requests after 24 hours; expires signed approvals
after their 600-second window; and returns review leases older than 3 minutes
to pending (unless original request expired). It **never** opens a browser,
signs on behalf of the owner, obtains a receipt or replays an external action.

The review lease token prevents a late browser result from attaching to a
superseding review. If the browser signed but inbox finalization fails, the
inbox also attempts to consume the orphaned SAFE receipt to invalidate it;
it never exposes that receipt as an approved result. Database failures can
prevent cleanup, so the signed SAFE proof remains short-lived, exact-action,
and one-use even under abnormal termination. Because a remote
effect is not rollback-atomic with SQLite, command retry still requires
idempotency/effect receipts at the execution boundary.

No alternate SQLite state may be created if the canonical file is missing.
SAFE audit and inbox event insertions share the same `BEGIN IMMEDIATE`
transaction. Notification transport is not a security authority.

## Test and acceptance rules

`test/test_safe_approval_inbox.py` checks durable state, restart/TTL,
signed synthetic WebAuthn browser proof, exact parameter mismatch,
duplicate approval refusal, consumed receipt refusal, Windows owner denial,
lease fencing, missing canonical state and notification retry.

The synthetic test key is never provisioned in production. Source code and
synthetic tests are not evidence of real Venus physical hardware, live
Windows Hello browser compatibility, Artemis or Debian migration, or
production host acceptance. Require an actual test run and supervised key
test before claiming Gate 4 acceptance.
