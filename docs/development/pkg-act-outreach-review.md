# PKG-ACT: source-linked outreach eligibility preflight

**Status:** standalone code/tests on a draft package branch, not merged, wired, running or deployed. This **never sends a message**, schedules work, claims that Sofía thought while offline, or grants authority. It returns only `eligible_for_authorization`, which a separate trusted execution and channel policy can still deny.

## Offline slice

`sofia.act.outreach` validates candidate source IDs, exact single-recipient ID, bounded validity times, opt-in `enabled=False` by default, mute/stop/busy, UTC quiet windows, acknowledged-delivery replay IDs, cooldown and daily cap. Timestamps require time zones; invalid claims fail closed. History comes from an independent trusted host, not user prose or LLM-proposed acknowledgments. Existing ACT outbox and RUN periodic gate remain their respective owners; no second scheduler/outbox is introduced.

**Command:** `PYTHONPATH=src python -m pytest -q test/test_act_outreach.py`. Equivalent staged source and tests passed **46 focused tests on Linux Python 3.13.5 / pytest 9.0.2**. GitHub checkout, Windows, CI, full repo suite and real Discord delivery not run.

## Review when ACT/Discord/RUN are active

- Reconcile `Candidate`, `History` and stop/mute/cooldown configuration with existing durable unsent outbox, RUN opportunity gate, per-user principal, SAFE authorization and actual Discord gateway. Do not use the proposed eligibility enum as an execution grant; a sender must enforce recipient/DM rights again and record an actual receipt.
- Resolve local-time versus UTC quiet hours and daylight-saving preference with Sparks; UTC defaults are fixtures, not a guessed personal schedule. Handle partial sends, retries, durable duplicate rejection, crash recovery, rate limits, deletion and credential compromise.
- Review emotional/non-clingy quality, novelty and user correction; an elapsed absence alone does not create a notification obligation. No continuous worker, second-user access, helper process, shell, network or web search in this branch.
- Run Windows focused tests, coordinated current-head full suite and supervised real opt-in delivery tests with independent channel acknowledgment before accepting ACT. Keep planned general search after Discord and verified 24/7 RUN.

No changes to production DB, protected identity or Constitution; no deployment or merge.
