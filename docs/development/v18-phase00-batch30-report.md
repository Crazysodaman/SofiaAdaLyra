# V18 original task batch: first 30 of Phase 00 (2026-10-13)

**Status:** Source inspected. Production implementations, CI test execution,
real-host acceptance and task sign-off remain separate evidence layers.

The authoritative reviewed **exact 30 IDs** and their source symbols,
related tests, observed behavior, missing proof, next action, design
alternatives, security boundaries, resource-measurement unknowns and explicit
rejection rule are in
`docs/development/v18-phase00-batch30-audit.json`.

The executable source verification and deliberate false-green negative cases
are in `src/sofia/verify/v18_phase00_audit.py` and
`test/test_v18_phase00_batch.py`. The independent
`V18 Phase 00 Batch 30 Audit` GitHub Action runs those tests and a
representative sample of existing end-to-end contract, turn, life, model,
memory, SAFE, distributed identity and Hyper-V tests on Windows and Linux.
Those focused tests **do not cover every behavior in every one of 30 tasks**.
They validate source pointers and existing slices; they do not substitute for
a live Venus/Artemis approval, sealed generalization benchmark or 24-hour soak.

## The 30 individual task decisions

| Slice | Exact task IDs | Audited finding | Remaining acceptance |
| --- | --- | --- | --- |
| Event/trace | CA-001, CA-003, CA-005, CA-006, CA-1201 | Canonical writer and read-only source/reply joins; decision trace deliberately partial | End-to-end every owner/receipt, audience and external effects |
| Baseline/quality | CA-002, CA-007, CA-1205, CA-1206 | Deterministic scoped benchmark and per-commit CI; no external benchmark scores | Real-model memory quality, heldout/adapted datasets, SLOs, full combinatorial matrix |
| Cognition/learning | CA-004, CA-1203, CA-1204, CA-1207 | Single kernel, model budgets, reviewed candidate and typed provider errors | Per-source measured context, validated feedback, model outage and route proof |
| Privacy/rights | CA-1208, CA-3105, CA-3108, CA-3109 | Existing permissions, identity registry, provenance and evidence sources | Live cross-host revocation, retention and epistemic correction tests |
| Independent work | CA-1202, CA-3104 | LIFE project transitions, RUN uncertainty and reviewed receipts | Full state/restart/goal outcome matrix, no false retry |
| Architecture/VM | CA-3101, CA-3102, CA-3103, CA-3106, CA-3107, CA-3110, CA-3111 | Owner inventory, planned sole writer, partial replication, workshop topology | Independent fencing, RPO/RTO and actual Artemis guest ACL/least privilege tests |
| Embodied output | CA-3112 | Voice playback and headless presentation are separate contracts | Real render/playback/delivery receipts |
| Review integrity | CA-3301, CA-3302, CA-3303 | Machine-verifiable 30-item design-readiness fields, canonical ledger and real CI regression triage | Formal owner review, complete acceptance by task and exact-revision full CI |

## Actual CI defect observed before this change

`Package Tests` at `14df9c27a3a2db4fd0f11af56f07202d4354135e`,
run 38489892961, Windows `pkg_act`:
`test_life_decision_contract_refuses_second_scheduler_or_false_neuro_link`
failed due to the stale string assertion
`neuro_turn_correlated=False`. Recent CA-001 work changed this to
conditionally correlate an explicit **same-message observation**. The policy
remains that a global latest NEURO snapshot is not evidence of causation. The
test now checks both exact message IDs and that explicit conditional
correlation. The contract wording is updated accordingly, without enabling
autonomous permissions or inferring ACT effects.

A `PytestUnknownMarkWarning` also flagged `pkg_cognition` in
`test_ws4_model_admission_positive_metrics.py`. The existing configured
owner is `pkg_core`, so its marker was repaired without inventing a 23rd
package. Prior nested `release-source` import defects and platform SQLite
handles remain historical categories that cannot be declared fixed solely
from this source report. Exact-revision release CI must run.

The static task ledger remains authoritative and `accepted: false`
until tests and production verification are independently witnessed.
**No live machine, guest, key, model or canonical database is modified.**
