# Phase 02 / 05: opaque mobile notification handles and title privacy

A source audit found that the initial mobile-notification privacy repair
redacted only `content` and `preview`, but still returned the original
notification `title` and canonical ACT `notification_id` to the phone.
The title may contain project/memory content, and notice IDs can contain
private project names. A generic preview is therefore not sufficient.

The production mobile gateway now sends the title **"Sofía"** unless the
existing independent host `private_chat` and `adult_external_delivery`
grants plus private-mode intent allow full preview. It never sends an
original ACT notification ID to a remote device.

`MobileNotificationStore` now owns a durable opaque delivery-handle mapping
in the same canonical `sofia.db`. Each original notice gets one random,
stable, nonsemantic `mn1_` handle, including preexisting legacy queue items.
The handle is stable across claim lease expiry and retries, so Android's
existing ID-based deduplication works. Acknowledgements resolve the handle
back to its original notice ID **inside the authenticated host** and still
enforce the original claimed-device owner. Unknown or original ACT IDs are
rejected rather than treated as valid mobile handles. The original ACT
outbox receipt stays authoritative; no duplicate notification queue owner.

No user-facing notification content was expanded. The change preserves
individual device authentication, SAFE host privacy gates, and the
operator-only enrollment decision. The canonical database writer host
remains undecided; no host cutover or deployment was performed. Regression
checks were authored but not run.
