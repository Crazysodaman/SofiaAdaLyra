# V18 Phase 04/05: durable single-turn Android delivery journal

The host mobile API already requires a stable `request_id` and refuses to
re-run an unsettled mutation. An Android process restart previously discarded
the ViewModel's in-memory pending request ID, so manually retrying the same
text could allocate a different ID, bypassing that deduplication.

This change completes the actual phone-side delivery identity path for one
outstanding chat turn. `SecureSettings` durably commits an AES-GCM encrypted
message/nonce record in its existing Android Keystore-backed SharedPreferences
**before the first HTTP request**. A new ViewModel instance restores the exact
nonce and message on startup. The record includes origin URL, private/shared
mode, and SHA-256 credential fingerprint (never the plaintext token) so
a resumed request cannot cross a different phone pairing or audience.

The phone will never automatically retry an uncertain message. The owner
must inspect canonical Main history and deliberately resend the **same**
recorded bytes and request ID or explicitly discard the unresolved local
send. A different text or request ID cannot replace an unresolved send.
A successful authenticated response durably clears the journal; a timeout,
app death, provider error, or corrupted encrypted record does not.
Pairing or privacy-mode switching is blocked while an unconfirmed send
remains, with a visible explicit discard choice.

This is a **single-outstanding-turn** mobile outbox, an intentional bound to
prevent conflicting concurrent sends. It is not offline multi-message causal
sync, a CRDT, a network retry worker, or a promise of exactly-once external
effects. Existing server-side per-device authorizations and at-most-once
receipts remain authoritative. Only the operating host writes canonical
SQLite; no offline replica is introduced.

Instrumentation regression cases use actual Android Keystore and
SharedPreferences for restart recovery, identity binding, no nonce reset,
and damaged ciphertext behavior; tests were AUTHORED BUT NOT RUN. Android
Gradle instrumented-test dependencies were pinned; no Android emulator,
build, network, operator pairing, or live host action was used.
