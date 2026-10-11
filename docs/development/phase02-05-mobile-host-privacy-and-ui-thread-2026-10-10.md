# Phase 02 / 05: mobile private chat authority and Android UI dispatch

Source audit: `src/sofia/mobile/gateway.py`, `src/sofia/mobile/server.py`,
Android `MainViewModel`, and the canonical SAFE `PermissionStore`.

A privacy discrepancy was found: Mobile Main history enforced durable host
`private_chat` permission, but `MobileCompanionGateway.chat` accepted a
phone-local private-mode toggle without checking that grant. This meant the
private Main view could be denied while fresh private conversation could
still be sent to cognition. The host now evaluates the same current durable
grant inside the serialized chat dispatch lock. Denial returns HTTP 403 and
does not call the conversation/model. Standard owner chat remains available.

Android's existing `launchRequest` executed the entire mutable Compose
state update block on `Dispatchers.IO`. It now executes only network calls
on IO and applies message/history/emotion/view state on the ViewModel's main
coroutine. Failed history fetches preserve the previous displayed page. A
failed/ambiguous chat request preserves the outgoing text as a draft, removes
only that request's optimistic line, and explicitly tells the owner to check
Main history before manually resending. It never silently replays a remote
message after an unknown transport outcome.

**No tests, Android builds or host exercises were executed.** The authored
private denial/HTTP response checks remain unexecuted. Other Phase 05
requirements remain open, especially device-specific pairing identity,
durable cross-channel message idempotency and ordered offline acceptance.
This patch does not claim they are complete.
