# CA-5305: Hybrid Main Conversation and linked activity feed

**Owner decision confirmed: 2026-10-12 (America/Chicago). Selected B: Hybrid.** This reaffirms the owner's prior preference for Sofía to pursue independent LIFE projects and choose to share meaningful experiences without per-project approval, or voluntarily remain silent. This is **design approval only**, not tested implementation or permission to deliver an external message.

## Approved behavior

1. The stable, authenticated owner Main is a conversation, not a raw event log. Direct eligible owner/Sofía messages and actually delivered chat messages remain in the correct logical Main thread and original principal/audience.
2. Background LIFE/GOALS activities, experiments, reflections, verified project milestones, optional world/environment observations, voice/gesture/rendering receipts and diagnostics are **separate bounded, typed, source-linked activity events**, visible in an authorized activity view. They are not automatically injected as ordinary chat messages.
3. Sofía may **choose** to share an independently source-verified meaningful discovery, completed creative achievement, interest, insight or project update in Main using the existing Presence → ACT voluntary outreach route, subject to source freshness, SAFE/privacy/consent, mute, quiet hours, busy/gaming state, rate limits, audience, destination authorization and verifiable delivery. She may also choose silence. She is not required to obtain fresh approval for each ordinary eligible LIFE update.
4. One approved outgoing message must keep original event/source identity for deduplication. An activity event does not automatically create a Discord DM, Android push or cross-channel copy; an accepted delivery is not proof the owner read it.
5. Voice, avatar and screen observation receipts may link from an authorized event when relevant, but raw screenshots, private content, system logs, credentials, private LIFE artifacts or third-party material are never copied into Main on the strength of this policy. Screen capture and sharing require their **separate** existing authority. An erased/revoked source cannot be resurrected via feed projection or message replay.
6. Main, linked activity and cross-device views must check present authorization and original principal/audience at every read. Private or device-local material stays redacted outside eligible scope. A declined update suppresses future duplicates; user silence is not permission or an emotional signal.
7. Optional creative self-expression does not expand Level 3–5 execution grants, install software, change canonical database writers, consent to surveillance or authorize uploading data.

## Source and acceptance separation

- Existing source includes voluntary LIFE → Presence → ACT notification pathways, source-linked original receipts, mobile notifications and lifelong Main history. See docs/development/v18-workstream-3-phase08-source-audit-2026-10-11.md and docs/development/v18-workstream-2-phase03-06-report.md.
- A complete separate searchable linked activity-feed UI, all modal event projections, per-device privacy handling and cross-channel end-to-end acceptance have **not** been verified. Do not mark CA-5305 accepted because a design decision is recorded.
- Remaining distinct owner values: optional media retention CA-4906, digital legacy CA-5108, numeric outreach limits CA-404/410, and numeric optional background LLM research budgets CA-3203/3907. Do not treat decisions on independent sharing as automatically answering those.

**Affected original tasks:** CA-5305 (Phase 05), CA-403, CA-404, CA-410, CA-4108, CA-5503, CA-2507. Exact master wording and shared 700-task status remain unchanged. No live machine/VM/state/permission/delivery changes were authorized or made.
