# Sofía V18 | Authoritative five-level task reporting standard

Owner decision: 2026-10-18 (America/Chicago).
Scope: the complete **780-task** V18 planning inventory (original CA tasks plus separately governed ML/GA additions).

## Status levels

| Level | Canonical label | Minimum evidence |
| --- | --- | --- |
| **1** | **UNKNOWN / NOT DONE** | No verified task-level implementation evidence, including work not yet inspected. **Unknown does not prove that no code exists.** |
| **2** | **AUDITED / PARTIAL** | Requirements audited, design completed, or partial code exists; some acceptance requirements, production wiring, or independent verification remain open. |
| **3** | **PRODUCTION CODED** | All requirements implemented in real production callers and interfaces (where applicable), including state/configuration/migrations/security/recovery; source and integration wiring independently reviewed. Tests may be authored but are not yet proven passed. |
| **4** | **TESTED** | Level 3 plus required focused regression and cross-component integration tests actually executed and passed on a recorded revision/environment, with a documented audit. |
| **5** | **TESTED + CI** | Level 4 plus applicable automated CI checks executed and passed for the matching revision, with immutable run references. |

### Counting rules

- Every task belongs to exactly one level, 1 through 5. **780 = L1 + L2 + L3 + L4 + L5.**
- A task is counted in its highest **individually evidenced** level only; never double count.
- Reports show each level count and cumulative **Level 3+**, **Level 4+**, and **Level 5** totals, as well as the source revision and the last-evaluated time.
- Historical statements, plans, generated code, unchecked assertions, and test files without passing runs cannot promote a task.
- Unknown/unassessed goes to Level 1; it is **not** a claim that the feature does not exist.
- A task's Level 3 must cover its own full acceptance scope, not merely one working code slice.
- Level 4 requires recorded passing results (test command, environment, revision, counts) and a task-specific security/behavior audit where relevant.
- Level 5 requires actual passing CI checks associated with the revision being assessed. Local test runs are not CI.
- CI may pass while a task remains Level 1–3, if that task has not met its earlier acceptance requirements.
- Regressions and invalid evidence can downgrade a previously assigned level. Report the downgrade explicitly, preserve historical evidence and explain why.
- Owner-required physical host, multi-day soak, pairing, credential or deployment trials are separately tracked as **live acceptance: pending/passed/failed/not applicable**. No claim of live deployment is implied by Level 3–5.
- The original 700 CA task ledger and its source-integrity validator remain authoritative for their original fields. The separate ML/GA inventories complete the 780 total; **do not silently rewrite the original master or reinterpret its legacy status values as levels 1–5**.
- Any new automated reporter must generate levels using task-level evidence, not numeric conversions from legacy `unassessed`, `partial_wiring`, `code_present_unverified`, or `accepted` labels. Until then, report unknown levels explicitly instead of making up totals.

## Required per-task evidence

- Task ID, phase, verbatim requirement and acceptance criteria.
- Level (1–5) and verification timestamp; commit SHA/branch.
- Source files and actual production caller/wiring evidence for Level 3.
- Focused/integration test commands, environment, run outcome and audit for Level 4.
- CI run URL/ID, exact commit and conclusion for Level 5.
- Outstanding work, blockers and applicable live acceptance status.

## Report shape

```text
Sofía V18 — 780 task evidence report
GitHub branch: main | assessed commit: <sha> | assessed on: <timestamp>
L1 Unknown / not verified: <count>
L2 Audited / partial:    <count>
L3 Production coded:     <count>
L4 Tested:              <count>
L5 Tested + CI:         <count>
TOTAL: 780
L3+: <count> | L4+: <count> | L5: <count>
Unclassified evidence gaps: <count> [explain how counted in L1]
Live host acceptance: tracked separately
Next highest-priority blockers: <IDs and verifiable gaps>
```

This status standard does not itself certify that any task has passed an acceptance gate.
