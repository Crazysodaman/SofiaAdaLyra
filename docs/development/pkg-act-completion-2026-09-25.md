# PKG-ACT completion candidate

**Revision:** 2026-09-25. **Branch:** `feature/pkg-act-completion`. **Status:** source candidate based on current `main`; focused tests are authored but have **not yet been executed on the current Windows checkout**. No sender, schedule, Discord delivery, general web access, or live autonomous outreach is enabled by this branch.

## Ownership

- **INTERACT** owns goals and creation of queue-only messages in `interact_queued_messages`.
- **ACT** owns outreach eligibility, explicit recipient/channel binding, delivery attempts, retry policy, dedupe, and acknowledged delivery receipts.
- **RUN** may wake ACT later, but does not decide outreach eligibility and does not own ACT's outbox semantics.
- **SAFE/SOCIAL/UI** remain authoritative for actor identity, recipient/channel authorization, secrets, stop/revoke, and actual transport.

## Implemented candidate

`sofia.act.outreach` provides bounded, source-linked eligibility for an exact recipient with disabled-by-default policy, mute/stop/busy gates, UTC quiet windows, cooldown, daily cap, stale/clock checks, and acknowledged-delivery dedupe. Eligibility is not permission to send.

`sofia.act.delivery` binds an immutable delivery envelope to an existing INTERACT queue item and records durable attempts in the existing application state database. Only acknowledged deliveries enter delivery history. Known failures can retry after a bounded delay and attempt cap. If the sender raises after handoff may have occurred, the attempt and queue become `outcome_unknown`; ACT does not blindly retry a possibly delivered message.

The sender remains an injected host boundary. Importing ACT starts no thread, scheduler, network connection, model call, or notification.

## Focused offline acceptance

Run on the exact branch:

```powershell
python -m pytest -q test/test_act_outreach.py test/test_act_delivery.py test/test_interaction_goal_journal.py
```

Then run surrounding regressions:

```powershell
python -m pytest -q test/test_action.py test/test_action_authority_boundary.py test/test_idle_reflection_worker.py test/test_idle_reflection_application.py
```

A passing offline gate supports repository integration only. Real Discord/channel delivery and long-running RUN scheduling remain separately deferred/live-gated.
