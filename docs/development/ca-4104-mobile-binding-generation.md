# CA-4104: per-device pairing generation in authenticated mobile session ownership

A token rotation previously invalidated the old bearer but kept the same
`device_id`-derived `PrincipalContext.audience_id` and existing
`mobile_conversation_binding_v2` session. An operator re-pairing a phone
under the same device ID could inadvertently grant the new enrollment
direct access to the prior generation's private and shared session history.

The current `MobileDeviceCredentialStore` already persists generation and
revocation state. Production session binding now keys on **device, audience
mode and canonical credential generation**, using
`mobile_conversation_binding_v3` in the existing `sofia.db`. Generation-one
users keep their existing session and principal IDs, with a safe read-only
migration from the legacy V2 mapping. Generation two and later use distinct
audience IDs and fresh sessions; the previous generation's bound session
and historical events are not removed or rebound.

Mobile response receipts are bound to generation too: a replayed request ID
from an older enrollment cannot return its stored response to a new token,
even when the message and device ID happen to match. Existing receipts
are migrated with explicit default generation one, not discarded. Revoked
credentials cannot authenticate externally, and session binding generation
is always read from the one canonical pairing store.

This implements CA-4104's per-device generation at the existing session
ownership boundary. Full cross-transport default-thread and global Main
association remains partial; no independent second thread owner was added.
Regressions authored but not run; no live Android pairing or host modified.
