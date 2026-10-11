# CA-6303: explicit encrypted offline draft, never an offline Sofía

The Android client already retains one DURABLE attempted chat turn when an
HTTP delivery might have happened. It did not retain a separately typed but
**never submitted** draft across Android process death. A drafts-only
offline companion therefore needed an explicit local save path.

`SecureSettings.saveOfflineDraft` writes a versioned JSON original into
Android Keystore-backed AES-GCM SharedPreferences with synchronous commit.
It includes the exact unsent text, presentation privacy mode, endpoint
and credential fingerprint, but does not contain plaintext credentials,
server-side grants, LLM content or any work request. On restart, the
ViewModel restores the draft only when its original pairing/mode matches
the current one. A corrupt or undecryptable record fails closed until
explicitly discarded, and settings changes cannot accidentally display
an earlier audience's draft.

The **Save encrypted offline draft (do not send)** and **Discard saved
offline draft** actions are explicit owner controls. No startup/reconnect
handler attempts to transmit a saved offline draft. An actual outgoing
chat first obtains the existing durable `request_id` outbox receipt, then
clears the redundant local draft and uses the ordinary authenticated
server path. The canonical server alone accepts logical events.

This is the drafts-only baseline chosen for CA-6303. There is no
secondary state writer, shadow LLM, local self-identity, permission
replica or autonomous offline tool execution. Device/OS acceptance
and full offline UI failure-mode testing remain open. Android
instrumentation regressions were authored but not executed.
