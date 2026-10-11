# V18 Phase 02 / 05: owner-approved per-device mobile authentication

**Decision:** Independently authenticated mobile credentials are required.
Re-pairing is permitted. **Canonical writer host remains undecided**.
Nothing in this change selects Venus/Artemis, rewrites the signed state-home
pointer, performs network pairing, or makes live host changes.

## Existing source seam audited

Before this change, `MobileCompanionServer` authenticated one global
`SOFIA_MOBILE_TOKEN`. The `device_id` in request JSON could name any mobile
device, so a token holder could read another enrolled device's audience,
send chat as that device or claim/ack its notifications. Although
`MobileCompanionGateway` derived separate audience IDs from device_id, it
could not prove that the caller controlled that device.

## Production implementation

- `MobileDeviceCredentialStore` uses the existing canonical `sofia.db`
  to store exactly one current random credential verifier per device. Only
  SHA-256 verifiers (of 48 cryptographically random bytes), generation,
  status, and append-only enrollment/rotation/revocation audit entries
  persist. No plaintext server-side tokens or secondary authority.
- Enrollment/rotation/revocation is an explicit **local operator CLI**
  requiring `--owner-approved` and host OS access to `sofia.db`. Enrollment
  returns the secret once; rotate requires explicit `--rotate`.
- Revoked/rotated bearer tokens become invalid on the next request, without
  server restart. Other enrolled devices remain valid.
- Every mobile HTTP route resolves the device solely from its bearer and
  rejects JSON with any other `device_id` with 403. This covers sensors,
  chat, Main history, state, notifications and acknowledgement. There is
  no remote enrollment or global shared-token compatibility fallback.
- Desktop worker starts the real mobile server using the SAME canonical
  credential-store instance as the gateway. `MobileProvisioning` no longer
  issues a global token. ACT "mobile ready" requires at least one active
  enrolled device. A mobile server may start without enrolled devices, but
  no request succeeds until the operator enrolls one.
- Android sends the existing per-phone device ID, accepts only an
  `sm1_`-format enrolled bearer, persists it in existing Keystore-backed
  settings, and scrubs old transcript/history on credential or endpoint
  change.

**Threat boundary:** Per-device bearer tokens are not Android hardware
attestation. A stolen token can impersonate its associated enrolled
device until rotated/revoked. The host still requires independent SAFE
adult/private grants. TLS remains mandatory off loopback; approved named
tunnels are separate from bearer/device authentication. Device credential
rotation does not widen model/tool permissions.

**Unexecuted evidence:** Auth tests cover independent device scopes,
token nonstorage, credential rotation and revocation, HTTP 401/403 for
disallowed paths, restored legacy-token denial, host worker integration
and ACT readiness. Regression tests have been authored or updated but
NOT executed, per owner instruction. No deployment, pairing command,
Android build, database move, CI or hardware validation was performed.

**Still open:** owner must choose the canonical writer host before any real
state relocation; actual device enrollment/re-pairing is an owner action
later; Phase 05's offline causal ordering, long-horizon cross-channel
migration and live acceptance remain separate work.

## Follow-up: startup adapter and notification cache audit

The HTTP server requires a `main_history` method; the real
`_WorkerMobileGateway` lacked it despite the canonical gateway implementing
it. This caused production worker startup to reject the mobile adapter.
The method now forwards through the existing owner-thread command queue
rather than opening an unauthorized parallel conversation connection.

The notification endpoint previously sent the entire notification `content`
field even when only `preview` was masked under host PRIVATE/SAFE delivery
policy. Android cached the full content in encrypted unopened notices, so
a later screen mode or credential switch could reveal content that had never
been approved for delivery. The server now redacts BOTH `content` and
`preview` unless the established full-preview grant is current, and Android
clears the cached unopened notices on privacy/credential/endpoint changes.
The background notification receiver checks the pairing and mode it used
to fetch a notification immediately before caching and display, rejecting
late responses from a former pairing.

For operator invocations use `python -m sofia.mobile` as the stable CLI
entry point. This avoids Python's double-import warning when executing
`pairing.py` directly after the package initializer has loaded it.
No automatic enrollment, cutover or live host changes were made. Host
tests, Android builds, and full production acceptance remain deferred.
