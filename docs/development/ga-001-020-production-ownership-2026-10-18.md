# GA-001 through GA-020 production ownership

This record describes the production architecture added for the first twenty
Generalization and Lifelong Learning tasks. It is an ownership map, not host
acceptance evidence.

## Reused authoritative owners

| Concern | Canonical owner | GA use |
|---|---|---|
| Objectives and visibility | `GoalService` | A workflow may reference only visible, live goals. |
| Work and outcomes | `DurableWorkStore` / RUN | Steps and rehearsals reference existing jobs and their canonical states. GA never enqueues or executes a job. |
| Procedure proof | `LifeProcedureCatalog` | Candidate skills require the current independently verified procedure proof. |
| Evidence | `GoalEvidenceIndex` | Grading, replanning, channel binding, adapters, rehearsal, and lifecycle changes recheck typed scoped evidence. |
| Data use | `LearningService` | Suites and active runs require the same exact principal/audience grant and retention window. |
| Safety and resources | `OperatorStopStore`, `OptionalAutonomyBudget`, RUN | STOP blocks starting and continuing evaluation. Admission reserves bounded optional-work credits. Any external effect remains a RUN/SAFE concern. |
| Scheduling | `ApplicationBackgroundCoordinator` | Daily retention and skill-source reconciliation use the existing application scheduler. |
| Persistence | canonical `sofia.db` | All GA tables are projections beside their source owners; no sidecar or shadow database exists. |

## Production paths

`SofiaApplication.generalization` owns one `GeneralizationService`. During
composition it attaches one workflow projection to the application
`GoalService` and one learned-skill projection to LIFE's procedure catalog.
The read-only owner CLI is `python -m sofia.generalization diagnostics` and the
existing EVOLVE settings surface exposes the canonical GA tables.

A sealed suite records the exact source revision, family-separated split,
expected host-owned digests, provenance reference, scope, grant, and retention
window. An evaluation run reveals one validation/test case at a time. The host
grader compares canonical digests and independently indexed evidence; model
self-report is never accepted. Metrics retain the supplied route, actual model
identifier, latency, tool calls, interventions, and token estimate.

A long-horizon workflow is a revisioned explanation of already-created GOALS
and RUN work. It validates dependencies, canonical risk and completion
constraints, and exact scope. Checkpoints copy actual RUN state and artifact or
receipt identifiers. Uncertain effects remain uncertain. Replanning requires a
failed, cancelled, or uncertain prior RUN outcome and scoped new evidence.
Cross-channel continuation requires authenticated evidence in both audiences
and exposes no transcript or execution authority.

A learned skill begins with an independently verified LIFE procedure. Its
typed contract retains tools, exact capabilities, prerequisites,
postconditions, risk, version, scope, and provenance. Qualification requires
distinct reviewed Windows and Linux adapters plus successful held-out positive,
missing-dependency, version-difference, and counterexample trials. Rehearsal
accepts only an existing completed RUN receipt and requires rollback evidence
for non-read-only work. Revocation, invalidation, deprecation, and supersession
remain durable and scoped.

## Invariants

- Evaluation evidence is not execution authority.
- A workflow step cannot create, retry, approve, or complete RUN work.
- A learned skill cannot mint a capability, permission, job, receipt, or goal.
- STOP and data-use revocation fail closed during an active evaluation.
- Principal/audience scope is exact; cross-channel continuation does not merge audiences.
- Missing grades, elapsed time, model claims, and uncertain external effects are never converted into success.
- Long-running 24-hour/72-hour results and Windows/Linux transfer are unknown until genuine trials occur.

## Acceptance still requiring genuine evidence

- Run a source-pinned unfamiliar-task baseline on configured production model workers.
- Run a learned condition against distinct held-out families and compare it to the baseline.
- Complete genuine Windows and Linux adapter verification on approved hosts.
- Complete real-clock 24-hour and 72-hour workflows, including a restart.
- Exercise a non-read-only skill through the approved DEV/SKILL/RUN path with an actual rollback receipt.
- Obtain exact-revision CI evidence. Local focused/package tests are not CI.
