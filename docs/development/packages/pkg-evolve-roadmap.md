# PKG-EVOLVE | Controlled adaptation and protected amendments

**Branch:** `feature/pkg-evolve-foundation` from `main` SHA `2141879`. **Status:** immutable review-only proposal plus tests; no write to Constitution, identity, personality, memory or approval tables.

## Aim and boundaries
Allow Sofía to propose and reflect on *mutable* preferences, interests, habits, skills and non-foundational expression while protecting canonical identity, foundational values and Constitution from silent alteration. LLM output, administrator root rights or a prior conversational promise cannot grant constitutional amendment authority. Preserve historical change evidence rather than rewriting past state to imply she always held a new belief.

## Slices
1. **E0 policy audit:** read the actual Constitution amendment sections and current hash-verifier/identity stores. Identify actors, required approvals, protection tiers and emergency-recovery mechanisms; do not invent a vote procedure or quorum.
2. **E1 typed proposals:** stable proposal ID, domain, expected original digest, change summary, motivation, source IDs, scope, risk, rollback and expiration. New `src/sofia/package_foundations/evolve.py` validates these minimal inputs but never applies a change.
3. **E2 ordinary learning:** route mutable preference changes through MEM/REL reviewed evidence and retention, with reversibility and negative preferences. A prediction or user's repeated pat cannot grant standing consent.
4. **E3 protected procedure:** independently verify real authorized approvers, consent/constraints required by current Constitution, immutable audit, before/after integrity hashes and deny-by-default conflicts. Do not create or amend constitutional rules by editing the proposer itself.
5. **E4 experimentation:** sandboxed trial personality/models with explicit instance boundaries, measurement, no production identity mutation and review of claimed continuity. Derived minds require separate ACT/SAFE authority.
6. **E5 rollback/recovery:** immutable version history, signature/hash validation, interrupted modification, backup reconciliation, revocation and escalation when protected state differs unexpectedly.

## Verification and release
Run `python -m pytest -q -x test/test_pkg_evolve_foundation.py`, followed by unauthorized reviewer, forged source, replayed approval, digest mismatch, concurrent amendment and forced-failure recovery tests. Use disposable copies only for protected-file mutation tests. The actual Constitution remains unchanged throughout this branch. CORE supplies self-state, MEM/REL supply reviewed mutable source evidence, SAFE enforces authority, VERIFY measures integrity/recovery. Full tests, actual constitutional-procedure review and separately approved merge are outstanding; never auto-deploy an amendment.
