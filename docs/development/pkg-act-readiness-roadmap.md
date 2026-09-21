# PKG-ACT | branch readiness roadmap

**2026-09-21 | draft PR #15 | baseline head `fd34a33b9ebd716a59d3e2d3e387845490e6861e`.** Companion: `pkg-act-outreach-review.md` and original ACT outcome in `ROADMAP.md`. No outbound message is enabled by this document.

## Existing slice and evidence

A side-effect-free, **disabled-by-default** eligibility screen checks source IDs, expiry, stop/mute/busy, quiet window, cooldown, daily cap and acknowledged-delivery replay. Equivalent staged code passed **46 focused Linux tests** after a test-fixture time-window correction. Eligibility is *not* permission, queue acceptance or proof of delivery; real Discord/Windows/full-suite tests NOT RUN.

## Work / test sequence

1. Inspect current ACT goals, unsent durable outbox, opt-in idle worker, authority rules and RUN PR #3 periodic gate. Reuse **one** scheduler, event ID and message/outbox pipeline; no competing reflection loops or second Sofía.
2. Add source-linked goal/follow-up candidate states: draft → independently authorized → queued → sent/acknowledged or failed/canceled, with privacy audience, origin, TTL, idempotency and operator-visible reason for abstention. Distinguish `not sent`, `accepted by channel`, and actually delivered only when confirmed.
3. Bind trusted Sparks recipient and host-enforced SAFE grants/revocation to rate limits, quiet hours and stop; handle process crashes, gateway reconnect, resends, token expiry, time jumps/DST and confirmed prior delivery. A model request cannot unmute itself or authorize contact.
4. Review optional helper contracts: independent resource/permission quotas, force-kill by supervisor, restricted file/network scope, audit and recovery; no self-spawning agent or task capability from model prose.
5. Test focused branch suite, actual Windows, interaction/outbox/NET/SAFE/RUN integration on disposable state, failure injection and concurrency; live authenticated DM acknowledgments only after Discord gate. Measure foreground model responsiveness and game resource budget before autonomous opportunities.

## Decisions for Sparks at ACT review

Set opt-in and destination for proactive messages, acceptable frequency and quiet hours **in local time**, notice/priority types, whether a pending thought may become a task or notification, and resource caps for optional helpers. Defaults remain no sending. Long silence does not imply Sofía ran or had feelings while stopped.

**Exit:** offline eligibility slice tested; queue/delivery/supervisor/live tests NOT RUN. No merge/deployment, independent outreach authority or network granted.
