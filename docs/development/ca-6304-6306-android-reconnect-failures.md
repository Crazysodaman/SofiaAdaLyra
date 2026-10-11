# CA-6304 / CA-6306: Android reconnection failure taxonomy

A network timeout is not evidence that an action did not execute. The current
Android encrypted, durable one-turn journal already preserves the original
request ID and blocks automatic resend. This correction preserves the
distinction when the server explicitly rejects a request:

- HTTP 409: a canonical replay collision or uncertain prior dispatch. Show
  that status, advise manual Main review, retain the exact local request.
- HTTP 401: pairing credential no longer authorizes this device. Preserve
  the local request; re-pair only after the owner resolves the previous send.
- HTTP 403: host permission explicitly denied. Do not present this as consent,
  success or an automatic retry.
- Timeout, disk/network outage or unknown HTTP: delivery unconfirmed,
  preserve durable draft and require manual review.

`SofiaApi` now raises a typed `SofiaHttpFailure` using only status and
allowlisted server error codes. HTTP streams are read in a fixed-size bounded
loop; the TLS connection disconnects in a `finally` even on read failures,
JSON errors or cancellation. No raw server body, bearer or private text is
included in transport exceptions. The phone does not gain a second
scheduler, offline LLM or permission source.

This implements part of CA-6304's truthful conflict behavior and CA-6306's
degraded transport ladder. Full cross-channel causal merges and cache
authorizations remain open. Tests authored only, not run or built.
