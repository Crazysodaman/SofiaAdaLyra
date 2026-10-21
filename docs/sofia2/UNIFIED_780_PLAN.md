# Unified 780-task integration into Sofía 2.0

**Decision:** retain all existing original requirements, statuses, task IDs and acceptance criteria; integrate them into the new product ownership tree. Do not run a parallel task universe.

## Source of truth

Original inventory: [700 CA, 40 ML, 40 GA](../Sofia_V18_700_Tasks_Brief_Table.md). Original evidence and historic acceptance remain in their existing files. This new plan is a mapping/projection, not an overwrite of task provenance.

## Per-task record required

- Exact task ID, original requirement text, original acceptance requirements, original references.
- Primary destination: `CORE`, `PLATFORM`, `RELEASE_MODULE`, `OPTIONAL_MODULE`, `VERIFICATION`, or `DEFERRED`.
- Secondary dependencies: zero or more Core IDs, platform responsibilities and module IDs.
- Existing code: actual producer, persistence owner, application composition and runtime caller.
- Assessment: reused / adapt / repair / replace / no implementation evidence / intentionally deferred.
- Evidence: source SHA and paths, test command/outcome, independent audit and CI where applicable.
- Original task Level 1–5 and separate live-host evidence.
- Implementation work, owner decisions and blockers.

There is one **primary owner** per task; cross-cutting requirements may have multiple secondary references. Mapping is **not** a claim of completion.

## Proposed ownership examples, not exhaustive classification

| Original task/family | Primary direction | Related area |
| --- | --- | --- |
| CA-001 | CORE | trace canonical cognition and outcomes |
| CA-1203 | CORE | memory/attention context budget |
| CA-1204 | CORE | evidence-backed preference/learning |
| CA-1208 | PLATFORM | consent, provenance, retention |
| CA-3103 | PLATFORM | single-writer backup/redundancy |
| CA-3112 | RELEASE_MODULE | voice/avatar truthful expression; Core contract consumer |
| ML-001–010 | PLATFORM | learning foundations and governed data use; Core may consume reviewed results |
| GA-001–020 | CORE or PLATFORM per original task | learned skills, behavior evaluation and integration; require individual audit |

These examples are routing hypotheses, **not** finalized task-by-task evidence. Do not bulk assign every ML or GA task by family.

## Execution of reconciliation

1. Enumerate exactly 780 unique task IDs and compare them to original inventory.
2. Read original text and linked specifications; never infer acceptance from abbreviated title alone.
3. Locate actual code, production caller, state writer and tests.
4. Assign primary destination + secondary owners with documented reason.
5. Evaluate existing evidence independently; unassessed does not mean missing.
6. Preserve original status and report the exact evidence source.
7. For confirmed scope overlap, map multiple task IDs to one implementation with separate acceptance proofs.
8. Detect new Core 1.0 requirements not covered by old tasks without inventing CA/GA/ML IDs.
9. Publish reviewed mapping batches with commit SHA; only upgrade Gate status on independent task-specific evidence.
10. Make optional-module work eligible after Core prerequisites rather than blocking the Core release on every historic task.

**Known prior Codex report, not independently verified here:** it claimed 780 categorized destinations and 652 evidence-unclassified entries on an unpublished local snapshot. Do not treat its numbers or paths as a verified repository fact until that exact working tree/projection is available.

## Acceptance semantics

Maintain the [five-level standard](../development/V18_TASK_STATUS_STANDARD.md): L1 unknown, L2 audited/partial, L3 production-coded, L4 executed-test verified, L5 exact-revision CI. Separate live-host approvals and trials. No status conversion from legacy labels; no completion inflation for documentation, declared registry metadata or passing unrelated tests.
