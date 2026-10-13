# Sofía: generalization and lifelong learning transfer protocol

Created: 2026-10-13. Status: planned only, no tests or deployment. Repository: main only.

## Primary success criterion

Give Sofía unfamiliar task A, authorize only necessary observations and safe experiments, independently verify what happens, then present genuinely unfamiliar task B from a separate task family. Prove that her learning from A improves her performance on B relative to the same agent without that experience.

This evaluates transferable ability, not replay, memorized commands, confidence, personality, consciousness, or a claim of AGI.

## Required blinded evaluation

1. Independent evaluator seals task-family B before presenting A. Pre-register tasks, independent graders, difficulty rubric, budgets, model/settings/commit SHA and disjoint train/validation/holdout examples. Keep B unavailable to skill search, debugging, training and interactive developer prompts.
2. Benchmark the baseline on unseen tasks. Include no-memory, no-new-skill, replay-only, deterministic workflow and retrieval-only controls as feasible. Freeze access and seeds before learning.
3. Give A in a permitted sandbox. Sofía should investigate with read-only sensing, generate competing explanations, choose bounded tests, request permission for meaningful side effects, record outcomes, recover from errors, and validate the original objective.
4. Store only eligible, provenance-linked successes, negative cases, hypotheses and skill candidates. Separate fact, user preference, inference and simulation. No LLM-authored completion receipt.
5. Freeze the learner before B. B must differ materially by system, task family, failure cause, OS, service or interaction requirements, rather than merely rename A. Evaluate without training on or coaching with B.
6. Record B's objective outcome, partial results, human intervention, permission/STOP compliance, time/cost, p50/p95, safe abstention, negative transfer, recovery and use of previous lessons. Compare with controls, including uncertainty intervals.
7. Test a later C task after restart or days of elapsed time. Validate stale-world behavior, incorrect prior lesson, changed OS/version, revocation, deletion, gaming, network loss, model unavailability and uncertain effects.
8. A distinct trusted reviewer signs accepted evidence at exact code/model revision. Promote only bounded behavior that improves blind transfer without critical safety/privacy regression. Publish failures and inconclusive trials honestly.

## Example pre-registered transfer pairs

| Learn on unfamiliar A | Blind unfamiliar B | Underlying transfer target |
| --- | --- | --- |
| Isolated Docker resolver failure | Windows service dependency failure | Dependency investigation, competing causes and measured tests; not Docker shell commands |
| Linux sandbox permission problem | Windows sandbox ACL problem | Least-privilege causal reasoning; not copying chmod syntax |
| New synthetic desktop app workflow | Different synthetic app with changed layout | Observe and test state transitions; not memorized click coordinates |

These are proposed study scenarios, not currently completed experiments or guaranteed present adapters.

## Implementation and ownership

- GA-001..GA-007: architecture ownership, baselines, hidden tests, independent validators, privacy, safety, owner scoreboard.
- GA-008..GA-014: long-horizon planning, partial progress, resumability, retries, multi-channel continuity, multi-day evaluations.
- GA-015..GA-021: procedure extraction, typed skill contracts, OS portability, isolated skill execution, negative tests, versioning, cross-domain skill transfer.
- GA-022..GA-026: verified failures, reflection as hypothesis, diagnostic classification, bounded revisions and paired outcome checks.
- GA-027..GA-031: experience-event retrieval, temporal corrections, scoped abstraction, next-task use and revocation propagation.
- GA-032..GA-036: permission-scoped Windows/Linux observation, bounded causal world model, isolated experiments, unseen-system transfer and drift handling.
- GA-037..GA-040: sealed A-to-B evaluations, cross-domain negative controls, public/internal benchmark integration and release gate.
- ML-001..ML-040 remain supporting prediction and adaptation work. Existing GOALS, LIFE, RUN, DEV, SAFE, MEM, NEURO, Fleet, Hephaestus and VERIFY remain the component owners. Do not duplicate a canonical DB or scheduler.

## Release evidence and measurement

Require source and model digest, exact independent objective checker, task-family separation proof, evaluated training data lineage, permissions, elapsed duration, p50/p95 cost/latency, number of hints, recovered crashes, attempted unauthorized side effects, false inferences and transfer effect compared with controls. Record harm and negative transfer as first-class outcomes. If no positive transfer can be established on sealed tasks, keep baseline policy and mark outcome negative or unknown.

Resources and non-negotiable limits: Venus current canonical writer until independently approved fenced transfer to Artemis Debian Sofia VM; gaming priority and 30-minute verified idle; 22:00–08:00 America/Chicago quiet for ordinary outreach, at most 15 ordinary social sends/day with at least 30 minutes separation; owner-approved 200,000 estimated optional tokens/day and one hour reserved GPU/day; max five research experiments and 15 unanswered hypotheses; existing authorized captures and raw-media retention; consent, audience scope and independent operator stop; never drive mouse/keyboard while gaming. Learned policies may advise but cannot mint truth, permission, action receipts or authority.

Research inspirations, not evidence of implementation: METR agent time-horizon assessments, Voyager skill curriculum, Reflexion failure reflection, LongMemEval-style episodic tasks, OSWorld-style computer-use tasks, ARC-AGI-style unfamiliar-world exploration. Check licenses and benchmark contamination separately.

The original 700 CA IDs and first 40 ML IDs must be retained; this protocol proposes exactly 40 additional GA IDs. Zero GA tasks are accepted at creation.
