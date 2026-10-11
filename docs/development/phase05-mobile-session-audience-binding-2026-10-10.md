# Phase 05: mobile session owner binding at create/resume

The mobile gateway previously deferred `SocialSessionStore.bind` until the
first model turn and used an unconditional conflict update when persisting
a device/mode session ID. This allowed a mapped but unbound session after
state-only access, and concurrent gateways could silently overwrite an
existing device/mode association.

The production `_conversation` path now binds every new/resumed session to
the exact derived principal and audience before it is published in
`mobile_conversation_binding_v2`. A previously mapped session with an
absent social binding is migratable only if it has **no durable messages**.
Any populated unbound session fails closed; a mismatched social binding
always fails closed.

Publication now uses first-writer-wins INSERT OR IGNORE and checks the
stored session ID within the same SQLite transaction. A concurrently
inserted different session cannot replace an existing association and
is surfaced as an explicit reconnect error. The same session/mode is
idempotent across restarts.

No test execution, real host deployment or client migration was performed.
Audited regression cases were written but deferred per user instruction.
This does not provide independent device credentials, which still requires
a pairing policy and migration decision.
