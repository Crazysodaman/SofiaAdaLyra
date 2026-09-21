# PKG-ACT | Bounded goals, initiative, outreach and helpers

**Branch:** `feature/pkg-act-foundation` from `main` SHA `2141879`. **Status:** pure delivery-eligibility proposal and planning; no scheduler, Discord bot, worker, recipient enrollment, actual send or helper started. The separate always-on RUN PR #3 is untouched.

## Outcome and existing foundations
Enable Sofía to maintain evidenced goals and choose useful, restrained next actions **only while a separately enabled runtime is running**. Existing idle reflections and queue-only outbox do not prove autonomous agency or delivery. INTERACT's proposed Discord private DMs are a future UI transport; ACT owns eligibility, authorization, cadence, outbox and send receipts rather than a second Sofía process.

## Slices and dependency gates
1. **A0 evidence audit:** inspect existing goal journal, idle worker, outbox, authorization and session identity at exact revisions. Separate model proposals from admitted goals and executed work; never infer activity while off.
2. **A1 goal lifecycle:** source-linked pending, accepted, blocked, active, completed and failed states; owner, expiry, retry ceiling, dependencies, cancellation and restoration after process restart. A goal is not a permission grant.
3. **A2 scheduler:** user-enabled, bounded running-only worker with visible health, resource limits and independent kill; novelty dedup and meaningful abstention. Games and homelab compute need measured, authorized NET input, not assumptions.
4. **A3 outbound permissions:** authenticated recipient/channel enrollment, distinct opt-in for proactive delivery, quiet hours in recipient timezone, mute, frequency cap, revoke and cross-client stop. `src/sofia/package_foundations/act.py` checks only eligibility; it authenticates nobody and sends nothing.
5. **A4 Discord DM lifecycle:** after INTERACT D0–D2 security and quality gates, source-linked draft -> authorized -> queued -> attempting -> provider receipt -> delivered/failed; retries must not duplicate. No server-wide listening or privileged bot commands by default.
6. **A5 helpers:** independent restricted child processes with externally enforced resource quotas, capability grants, audit, isolation, stop and force-kill. Resolve constitutional derived-mind issuer procedure before any creation.
7. **A6 recovery:** outages, restart, user away/busy, stale evidence, duplicate delivery, missed schedules, stop races and credential loss must fail closed or visibly queue with no invented completion.

## Verification and release
Run `python -m pytest -q -x test/test_pkg_act_foundation.py` on this branch; later add fake-clock quiet-hour boundaries, sender/recipient spoofing, opt-out during dispatch, queue idempotency, provider error receipts, restart replay and uncooperative helper termination. Real DM receipt and user-observed delivery are distinct; merely printing `sent` cannot pass. Review privacy, Discord bot token storage, message retention and abuse/rate limits. No new tests are reported passed for this branch. **Owners:** INTERACT typed social events; ACT initiative/outbox; UI Discord adapter; SAFE auth/revocation; NET host availability; VERIFY real E2E checks. Deployment and merge require separate approval, not this roadmap.
