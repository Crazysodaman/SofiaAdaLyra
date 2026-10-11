# V18 coding completion means production wiring, not file presence

**Policy established 2026-10-11.** No tests, CI or live hosts were exercised during this source-only review. The original 700-task master is unchanged.

## Binary coding judgment

A task is **CODED / TESTS ONLY** only when the original task's required behavior is implemented and the static source audit traces a real authority-preserving **production entrypoint → composition → active caller → implementation → durable effect or truthful output**. Required external boundaries and safe failure handling must already be implemented. Only focused/full tests, CI or applicable supervised live proof may remain. A commit, class, dataclass, adapter, stub, mock, unit test, or comment is never by itself sufficient.

A task is **NOT CODING-COMPLETE** when any required production functionality or wiring remains missing, or when it cannot yet be traced to production. This includes source-only scaffolds, library APIs with no active caller, research contracts, partially guarded routes, and unimplemented integrations. Existing code remains valuable reusable work, but it gets **zero coded-complete credit**.

A task is **NOT AUDITED** when there is insufficient task-specific review. **Unknown is not missing code.** It is not counted as complete either.

**ACCEPTED** is a separate later gate: actual exact-SHA tests/CI and relevant live-host receipts have passed. Merely writing tests does not make an item accepted.

## Machine-readable contract

The historical evidence ledger retains the existing four source states so its 700 fixed IDs, existing audit provenance and release tooling remain compatible:
- `code_present_unverified`: six **candidate wired / tests only** tasks with an explicit `production_wiring` proof map, enforced by `sofia.verify.v18_roadmap`. Their review is still static and does not certify actual behavior.
- `partial_wiring`: **not coding-complete**, even when a large production slice is present.
- `unassessed`: unknown, not counted.
- `accepted`: must include exact-SHA verification receipts.

For each coded/tests-only task, `production_wiring` records a real entrypoint, composition path, calling path, implementation path, effect path, source snapshot and an explanation of the actual flow. The source-integrity gate rejects a code-present claim missing that chain or using a tests/docs file as a production route. This is necessary evidence, **not sufficient proof of actual reachability or correctness**; reviewers must still inspect conditional configuration and security.

## Six currently traced production paths (tests remain deferred)

| Task | Production source chain | Remaining acceptance |
| --- | --- | --- |
| CA-2201 | Application LIFE worker → `SelfDirectedLifeCoordinator` → registered read-only objective validator → real artifact bytes | Focused/full tests and lifecycle check |
| CA-2204 | LIFE artifact scheduler → existing RUN transactional enqueue → canonical LIFE job/authorization record | Crash-boundary tests and restart proof |
| CA-3001 | Application CreativeService → real workspace allocation → SHA-mapped safe filesystem path → managed asset | Windows exact-SHA and real Project Forge checks |
| CA-3003 | `release-candidate.yml` → staged independent source → installed-package provenance → revision-bound verification gate | Run real Windows CI and record revision receipt |
| CA-103 | Application `independent_life` background task → LIFE tick → settled RUN reconciliation / review | Runtime restart/live cadence and package tests |
| CA-111 | LIFE completed-job settlement → verified creative artifact preview/hash → typed objective checks / evaluation | Independent objective and completion regression tests |

**No claim is made** that a specific feature works in a deployed host; six are *source-traced coding-complete candidates*, not production-accepted.

## Current Phase 09 production-reachable additions

The original 300-second application LIFE background callback now reaches a source-verifying milestone reconciler, which checks the actual stored artifact and canonical successful RUN evidence before writing original objective milestones with the existing SQLite CAS. Interrupted writes are retried by the same production tick without a second scheduler or new creative job. `test/test_life_verified_milestone_production.py` records real-job, restart and foreign-evidence regression contracts, not executed.

Auto-created projects now require an original tool-free TEXT/STORY authoring response. The old `_initial_specification` boilerplate is removed from autonomous scheduling. No model or unsupported native media yields an explicit unavailable result and **zero** creative jobs, artifacts or fabricated authoring receipts. Manual Project Forge approval remains a separate path. Other media need real authoring integration before CA-2202 can be considered coded-complete. Tests are authored, not run.

The stricter ledger after this wave is **6** coded/tests-only candidates, **64** partial/not coded-complete, **630** not yet individually inspected and **0** production accepted. **Job 5 remains open.**

## Strict handling of known unfinished areas

- CA-101: The committed experience-interest loop covers reviewed LIFE artifact evaluations, not every eligible ordinary observation or experience; **NOT CODING-COMPLETE**.
- CA-105/106/110/112/113/3014 and Codex Job 5: complete autonomous critique, milestone progression and GOALS/RUN uncertain-result handling **NOT YET CODED-COMPLETE**.
- CA-6201: screen consent token/receipt without complete OS-selected capture/user-journey wiring **NOT CODING-COMPLETE**.
- CA-6804: no-create SQLite protection without operator-fenced cross-host recovery **NOT CODING-COMPLETE**.
- CA-6701: model training categorization/adaptation manifests without all owner UX and execution functionality **NOT CODING-COMPLETE**.
- CA-701: the connectome motifs are a bounded research prototype, **not** a real whole-fly-brain production simulation.

## How to keep this honest

1. Inspect each CA requirement exactly as written.
2. Inspect source-level import, composition, real caller, enabled runtime path, authority/consent, failure behavior, durable outcome and consumer/output.
3. If any part is missing, code the real production behavior first, then reconsider the label.
4. Only when the full original task requires **no further source coding** assign `code_present_unverified` with `production_wiring` and list tests/CI/live evidence remaining.
5. Perform deferred verification; promote to `accepted` only with exact-SHA receipts.
6. Always distinguish tasks with genuine experimental/research limits and operator-dependent decisions from tasks implementable now.

**Current checkpoint:** 6 source-traced code-complete candidates / 63 partial, NOT complete / 631 not fully inspected / 0 accepted. **Do not turn 6/700 into an overall coding-completion percentage; 631 are still unknown.**
