# Sofía V18: five-stage engineering status (780 tasks)

**Owner decision: 2026-10-17. Active for all future progress reporting on `main`.** This supersedes Gate 1–4 and mandatory independent-review certification as *development status labels*. Do not rewrite history or erase previous evidence. The 700 CA plus 40 ML plus 40 GA original requirements remain authoritative.

## Exactly five statuses

| Status | Meaning | Minimum evidence |
| --- | --- | --- |
| **NOT_WORKED_ON** | No task-specific implementation or deliverable can be established by current audit. This is an evidence state, not a claim that no code exists. | Requirement identified; code/design not yet traced or reliably evidenced. |
| **CODED_UNFINISHED** | Source or design work exists but one or more original clauses, production connections or failure paths remain incomplete/unverified. | Relevant paths/commit(s), precise gaps. A drafted design without a finalized deliverable falls here. |
| **PRODUCTION_CODED** | All original implementation clauses are traced through actual production owners/callers, configuration, storage, permissions, persistence and restart/error paths. A design/research-only task has a complete decision/deliverable integrated into the authoritative specification. | Clause-by-clause source links plus canonical entrypoint and negative-case audit; no placeholder-only code. This means wired for production, NOT deployed on Venus/Artemis and NOT proven by tests. |
| **TESTED** | PRODUCTION_CODED plus relevant focused tests actually run and passed at identified revision, with negative, recovery and integration coverage where required. For research/verification tasks, run the specified experiment or produce actual results, not just a proposed protocol. | Test selectors, environment, revision, exit/result and limitations. Any original host/soak test requirement must still be met before TESTED. |
| **TESTED_CI** | TESTED plus appropriate GitHub Actions CI workflows pass for the *same pinned revision* and cover the task's relevant tests, platforms and installed package/release checks. | Workflow URL/run ID, conclusion, head SHA, test selector/output evidence and task-to-workflow mapping. A generic green badge alone is insufficient. |

## Rules

1. **One current status per task, no invented promotions.** Promote in order when all prior requirements are satisfied. On regressions, downgrade to last substantiated stage; record why.
2. **Do not automatically map historical gates or source triage to stages.** Old `unassessed` defaults to NOT_WORKED_ON until inspected; `partial` is only CODED_UNFINISHED after code/design evidence is inspected. A preexisting passing test or workflow is not stage proof until mapped to the actual task, original clauses and revision. Preserve all receipts.
3. **Original requirement wins.** A real-machine measurement, multi-day evaluation, independent comparison, legal/ethical decision, approved design choice or physical permission in an original task remains required. The new status scheme removes a blanket independent-review requirement, not task-specific obligations.
4. **Design-only tasks:** PRODUCTION_CODED means the specified design/research artifact is complete, tradeoffs and rejection criteria considered and decision adopted into the relevant specification. Where the requirement expressly asks for approval, owner approval remains necessary. Do not fabricate measurements to reach TESTED.
5. **No autonomy escalation.** A task's engineering stage never authorizes SAFE/FIDO2 grants, guest provisioning, Fleet actions, database writer transfer, deployment or user-consent changes. Those still require original authenticated approval and protections.
6. **Truthful reporting:** Separate coding, targeted test and exact-revision CI counts; show `unverified` when evidence is inaccessible. No signed reviewer required simply to say CODED_UNFINISHED, PRODUCTION_CODED or TESTED.
7. **Batch size:** work in related groups of 10 task IDs, preferably dependency order. Inspect all original clauses, implement the missing production functionality, add/run tests, verify CI, record per-task status and next blocker, then take the next 10. A batch of ten is a *work allocation*, not a promise of ten completions.
8. **Counting:** show five counts that sum to 780. Until a full 780-item status audit is completed, any unmapped task is conservatively NOT_WORKED_ON (unverified), not asserted code-absent. Report `audited N/780` separately.

## Tracking fields (new status overlay)

Keep `docs/development/v18-task-evidence.json` as historical original-task evidence. Do not destroy its gate proof or confuse it with the new ladder. Sparse audited promotions are recorded in `docs/development/v18-five-stage-task-evidence.json`; `scripts/v18_five_stage_audit.py` validates and overlays them onto the complete 780-item inventory. The generated register preserves stable IDs and at minimum: `task_id`, `stage`, `original_requirement_ref`, `source_sha`, `source_paths`, `production_entrypoint`, `tests`, `ci_runs`, `open_clauses`, `last_audited_at`. Source and tests may be empty for NOT_WORKED_ON. Validate allowed enums, unique IDs, complete 700 CA + 40 ML + 40 GA and ordered promotions.

## Batch 01 transition

CA-3101..CA-3110 already have draft design candidates and acceptance checklists on `main`. Treat these as **CODED_UNFINISHED** *only once their specific draft references have been inspected*, not as PRODUCTION_CODED or TESTED. They still have owner choices, missing artifact clauses, source/host verification or experiments. Other tasks start NOT_WORKED_ON for the new scheme until audited. The prior LIFE CA-2203/CA-111/CA-3502 commits remain evidence of source work, not automatically TESTED.

**Not a runtime/deployment release policy:** separate owner authorization and final rollout still apply.
