# GA-021 through GA-040 production ownership

This batch extends the existing `SofiaApplication.generalization` owner. It
does not create another database, scheduler, memory authority, capability
gateway, experiment executor, or promotion mechanism.

## Canonical source relationships

| Record | Source owner | Production rule |
|---|---|---|
| Grounded failure | RUN + typed Evidence Index | Only failed, blocked, cancelled, or uncertain canonical jobs are admitted. |
| Failure hypothesis | GA projection | Remains explicitly falsifiable hypothesis until new scoped evidence exists. |
| Retry proposal | RUN/SAFE | References an already admitted job; uncertain identical effects cannot replay. |
| Experience episode | Evidence Index + Learning data-use grant | Ordered intent/observation/hypothesis/action/outcome with independently labelled outcome. |
| Transferable principle | Experience episodes | One episode creates only a candidate; verified facts require multiple eligible episodes. |
| Planning influence | GOALS | Read-only trace naming eligible episodes and explicit with/without-experience ablation. |
| Environment observation | Vision/OPS/Fleet/synthetic evidence | Exact read-only route, permit, expiry, scope, and source class are checked. |
| Environment model | Scoped observations | Always tentative; contradictions are retained and drift reduces confidence to zero. |
| Experiment | RUN | Only approved Hephaestus or synthetic work; GA records the plan and never executes it. |
| Skill transfer | Learned skill + platform adapter + paired GA runs | Source and target must differ and benefit is computed rather than asserted. |
| Blind study | VERIFY signed A→B assessment | All control conditions, independent signatures, chronology, holdout digest, and receipts are verified. |
| Promotion eligibility | VERIFY + SAFE evidence + benchmark registry | Beneficial transfer, resources, privacy, authority, rollback, restart, and benchmark coverage must all pass. Eligibility is not deployment authority. |

## Revocation and retention

Advanced records share canonical `sofia.db`. The existing application
background coordinator performs bounded retention and revocation propagation.
Revoked sources disappear from retrieval, invalidate dependent episodes and
principles, invoke the existing LearningService cleanup, and invalidate learned
skills whose exact provenance contains a revoked source.

## Permanent safety invariants

- Hypothesis is not fact.
- Failure is not success.
- Similarity is not transfer.
- A retry proposal is not execution or approval.
- A screen/API/command observation permit grants no control action.
- Synthetic evidence is not real-host evidence.
- Promotion eligibility is not deployment authority.
- Missing, inconclusive, unsafe, privacy-invalid, or authority-invalid transfer retains the prior baseline.

## Acceptance still requiring genuine work

- Apply a verified skill to an approved substantively different real host or service.
- Execute controlled failure-reflection and no-reflection/replay-only comparisons.
- Run approved Hephaestus/digital-twin discriminatory experiments.
- Complete signed paired A→B campaigns in at least two real domains, including restart controls.
- Register actual licensed benchmark metadata and privately held-out assets.
- Obtain exact-revision CI evidence. Fixtures validate software contracts but are not generalization results.
