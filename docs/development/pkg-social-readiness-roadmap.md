# PKG-SOCIAL | deferred scope and readiness roadmap

**2026-09-21 | proposed package in draft PR #4, documentation-only; no SOCIAL implementation branch or active general multi-user release.** The original 13-package roadmap remains on main, while draft PR #4 now contains the reconciled ordered **16-package** proposal including SOCIAL, RUN, and AVATAR. No additional user is enabled by this document.

## Current one-on-one contract

Sofía is **one canonical identity for Sparks** for the initial rollout. Only the exact independently authenticated Sparks Discord account in private DMs may interact through that channel; unknown actors, other users, group DMs and guild messages denied by the trusted adapter + SAFE. The PR #5 policy flag or account-name string alone cannot authenticate a user. A single user still needs explicit privacy boundaries between private reflection, original user data and content deliberately shared on the virtual workbench.

## What may be coded offline now

- Stable typed `principal_id`, channel/session, owner and audience IDs independent of usernames or model prose; conservative default-deny and source-linked provenance for eventual memory, AVATAR props, UI thumbnails, logs and notifications.
- Fixtures that deny unknown/wrong actor, stale/revoked session, unverified gateway, different room and unauthorized presentation. No fake second-user relationship or public message visibility to satisfy a fixture.
- Review handoff between trusted adapter/SAFE, INTERACT, MEM, UI/AVATAR and ACT without creating an additional conversation store, emotional identity or authorization gateway.

## Explicitly deferred until Sparks asks to expand

Enrolling a second principal, relationships and relationship-specific memories, sharing semantics, public channel membership, cross-user notes/props, erasure/export/retention/consent and moderation policy. Before any such feature: decide who may join, what is private versus shared, revocation and data deletion, no metadata or object-existence leak, independent cross-user isolation and replay tests, plus real authenticated two-person channel acceptance. Neither admin status nor the same bot token grants access to someone's private DM.

## Testing and decisions

Now: validate *Sparks-only* identity and private audience at the actual Discord D0–D4 and MEM/UI gates; unknown principal stays denied. Later: separate approved scope, architecture, negative isolation and live two-person testing. Do not infer user preference or consent from prior conversations to authorize another person's access.

**Status:** design-only; general multi-user code and tests NOT RUN, no enabled second user, merge or deployment. Search remains after Discord and verified 24/7 RUN.
