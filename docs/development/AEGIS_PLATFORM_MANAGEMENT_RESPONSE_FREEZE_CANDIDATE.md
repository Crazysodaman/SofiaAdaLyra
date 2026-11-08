# Aegis Platform 1.0 management read response | A/C freeze candidate

**Status:** PROPOSED, **NOT JOINTLY SIGNED OFF**. Team A #241; Team C #243.
**Do not use as release authorization.** Rust/Python schema tests are source verification only.
**Baseline:** request `aegis.platform.management.read.v1`, response
`aegis.platform.management.read-response.v1`, protocol `"1.0"`.
Cross-language normative fixtures:
`contracts/platform/management-read-valid-v1.json`,
`contracts/platform/management-read-response-valid-v1.json`.

## Envelope, normalization and version negotiation

Exactly these JSON keys, with **no additional or duplicate keys**:
`schema`, `protocol`, `request_id`, `platform_id`,
`platform_generation`, `operation`, `source`, `observed_at`,
`outcome`, `data`, `denial`. Bytes <= 32768 (request is bounded separately).
Reply envelope is **not signed or authenticated by JSON**. `source` must be
`PLATFORM_SESSION` but is only a syntax constant: client MUST validate service
origin using native OS-authenticated socket/pipe identity and installed service
receipt before trusting the payload. A successful parser is never an authority grant.

Only protocol **exactly** `"1.0"` is supported. There is **no** unauthenticated
protocol discovery, offer/accept negotiation, implicit downgrade, or fallback
to incompatible #232 `aegis.platform.management.response.v1`. Unknown major
or minor numbers, missing protocol, unknown schema or additional authority
fields are rejected. A future minor/major protocol needs a new, explicitly
authenticated negotiation and an A/C contract review. Unsupported replies
never become successful observations.

`request_id`, `operation`, `platform_id`, and `platform_generation`
must match a previously constructed, bounded `UntrustedManagementRead` request
(`target_platform_id`, `expected_generation`). Response generation must
be positive and must match current service RUN lease/generation. Client never
accepts credentials, owner grants, user-passed generation or `source`
from reply as authentication.

`observed_at` is RFC3339 UTC or offset-aware, 0 to 6 fractional second digits
(the Python service emits 6). For an accepted reply: request-created <= observed
< request-deadline; observed <= trusted client receipt time; receipt time <
request-deadline; elapsed trusted client receipt minus observed <=5 seconds.
A stale, replayed, future or generationally inconsistent reply is rejected,
not cached as current health.

## Strict mutually exclusive outcomes

`outcome:"OK"` => `denial:null`, `data` typed per operation.
For `platform.status` exactly four fields:
`platform_id:string`, `generation:positive int`,
`operator_stop:false`, `core_started:false`.
No capability or owner permission is implied. Stop-active status is
never a successful `platform.status` observation.

`outcome:"DENIED"` => `data:null`, `denial:{"code":"..."}`
with **only** these codes:
`NOT_PERMITTED`, `REVOKED`, `STOPPED`,
`STALE_GENERATION`, `EXPIRED`, `UNAVAILABLE`.
No explanation, secret, token, proof, path, or additional status fields.
No `error` alias, arbitrary nested denial keys, or success+denial hybrid.
Sensitive keys, nonfinite JSON and unbounded nesting/lists are rejected.

A **kernel/token-authenticated but never-enrolled or now-revoked** peer gets
no content / EOF, not a typed denial that would reveal existence or
revocation of an identity. For a currently enrolled peer, production may
return typed STOPPED or STALE_GENERATION only if the current SAFE grant and
OS identity remain valid at both checks immediately around constructing that
denial. No claimed owner, local group membership, or JSON `peer` can enroll
a client. REVOKED is reserved for a future independently authenticated
session model; it is not an excuse to leak revocation to strangers.
Consequential mutation operations are outside this read contract.

## Team C GUI/TUI consumption

| Transport or verified server result | Client display decision |
| --- | --- |
| Native endpoint absent/unreachable | OFFLINE or CONNECTING; health UNKNOWN |
| Transport identity unverified or response forged | UNVERIFIED; health UNKNOWN |
| STOPPED (verified and correlated) | STOP_ACTIVE; no actions |
| REVOKED (only if independently authenticated session) | REVOKED; no actions |
| NOT_PERMITTED | DENIED; no actions |
| STALE_GENERATION | UNKNOWN_GENERATION; drop cached live state |
| EXPIRED | STALE; drop cached live state |
| UNAVAILABLE | OFFLINE/UNKNOWN; no health claim |
| Wrong request_id/version/operation/stale observed_at | STALE/UNVERIFIED; no observed health |
| Verified OK status, current generation, fresh receipt | OBSERVED, read-only; never an execution permit |

GUI/TUI never infer stopped/removed/uninstalled/healthy from silence,
stale status, EOF, old generation or an earlier owner grant.
Any reconnect needs a **new** OS-authenticated session, a new request_id,
current exact RUN generation, fresh expiry and current service SAFE grant.
Unsigned or untrusted UI cannot set permissions or bypass owner ceremonies.

## Team B installer handshake and native access

Windows pipe DACL is SYSTEM + service token + at most one **currently owner-
approved individual user SID** (SidTypeUser verified by Win32, never
Administrators/Everyone/Authenticated Users or group SID). Live SAFE grant
checks still occur before and after responses; changing the DACL on restart
requires exact signed installer evidence. Owner-secret rotation revokes old
grants but cannot magically modify an already opened Windows DACL; stale
connection alone must not yield data.

Existing Debian 12 unit uses `RuntimeDirectory=aegis`,
`RuntimeDirectoryMode=0700`, `PrivateTmp=true`; keep default owner-private.
Only an independently reviewed signed installer may provision
`/run/aegis` mode `0750` with dedicated enrolled operator GID, and
epoch-fenced AF_UNIX socket `0660`. Group membership is OS connection
eligibility, never authorization by itself. `/run` is not a PrivateTmp
namespace; do not weaken `PrivateTmp` unnecessarily. No `/tmp` external
socket, broad chmod, inherited active endpoint, symlink, or group wildcard.
Service and client verify pinned state, socket inode and STOP at dispatch.

## Freeze checklist and evidence owners

Team A: exact-head Rust/Python parity, strict positive/negative tests,
OS-native identity and SAFE/STOP/live-revocation admission.
Team C: explicit written ACK/REQUEST CHANGE for schema, version policy,
denial-to-view mapping, reconnect/state fences; no unapproved GUI IPC.
Team B: signed installed operator identity and runtime ACL policy
with exact service-bound receipt and no privilege broadening.
Team E: independent native Windows/Debian 12 signed installed-host
positive and adversarial receipts, crash/restart and owner-secret rotation
with exact source SHA. Issue #201 rows 10/11/12/31 remain OPEN.

**Freeze decision:** BLOCKED until explicit Team C written signoff AND
exact-head cross-language parity CI green. A draft commit is not a signed
API contract or release permit.
