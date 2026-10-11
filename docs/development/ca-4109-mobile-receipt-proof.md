# CA-4109 / CA-6302: Android must prove host logical delivery before clearing outbox

The mobile server now returns a durable `delivery_receipt` with the
original request ID, device, privacy mode, credential generation,
trusted server timestamp and monotonically increasing per-audience
sequence. Previously Android accepted any HTTP 200 JSON containing
`response` and immediately cleared its encrypted outgoing message.
An invalid/stale response after a reconnect could falsely claim delivery.

`SofiaApi.chat` now verifies the exact source-linked receipt before
returning success to `MainViewModel`. The existing ViewModel only
calls `SecureSettings.confirmOutbound` after this verification. Missing
receipt, mismatched request ID/device/mode, invalid generation, absent
server time or nonpositive source sequence leaves the durable nonce and
message intact for explicit owner review or replay under the same ID.
No automatic resend, privileged action or new conversation state is added.

This is authenticated HTTPS response consistency, not a cryptographic
signature or global Discord/desktop event-sequence proof. The canonical
host remains authoritative and is still the only SQLite writer. Android
instrumentation tests were authored but NOT built or executed.
