# V18 Phase 00 baseline: CA-002 and CA-007

This implementation is **a partial code-and-CI slice**, not acceptance of the
original V18 tasks. It reuses `sofia.verify.cognition_v2_baseline.capture_baseline`
and its disposable, deterministic application startup. It does not add a new
conversation state store, event authority, cognitive engine, or runtime service.

## Per-commit trace and safety

On every push to `main`, `.github/workflows/v18-companion-baseline.yml`
executes the same isolated control scenarios on Linux and Windows, runs its
own contract tests, and emits `v18-companion-baseline.json` as a
revision-bound artifact. `--expected-revision` must match exact Git HEAD both
before and after the measurement. A changed checkout or incomplete/fabricated
metric fails closed. Each report contains only allowlisted timings, coarse
SQLite row counts, instrumentation counters and unavailable metrics, never
conversation content, raw memory, model outputs, credentials or host identifiers.

The semantic baseline contract digest records the scenario/count definitions,
not a false promise that timings on different CI hosts are byte-identical.
Measured CPU time, wall time and optional peak RSS can vary legitimately.
Persisted counts must remain 8 conversation messages and 4 Matrix traces.
A model invocation during the deterministic benchmark is an explicit failure.

## Measured versus missing

| Evidence kind | CI report status | Further acceptance |
|---|---|---|
| Four isolated user turns, startup, idle 250ms, CPU/wall, SQLite counters | Measured by deterministic app path | Compare revisions against an approved baseline/SLO |
| Temporal memory, corrections and cross-device continuation | Not measured | Independent source-grounded longitudinal benchmark |
| Unsolicited outreach and interest continuity | Not measured | Consent-scoped observed delivery and multiple sessions |
| Voice and avatar actual output and synchronization | Not measured | Real speech/render receipts from enrolled devices |
| Production inference latency/accuracy, GPU/VRAM, budget | Not measured | Pinned live Ollama models, Venus idle and gaming |
| Transfer from unfamiliar problem A to novel B and sealed C | Not measured | Preregistered holdout grader, contamination tests |
| 3-day host soak, restart, backup and fleet handoff | Not measured | Supervised Venus/Artemis acceptance |

The artifact explicitly records `unit_tests`, `full_ci`, `venus_live`
and `multi_host` as `not_attested_by_baseline`. A CI job result may later
prove *its own* test execution, but the produced baseline JSON cannot
self-endorse CI success or live deployment.

## Remaining gates

CA-002: Design and collect the user-relevant live outcome measurements,
cross-device continuity, memory correctness and natural outreach quality. The
deterministic app baseline is a limited reproducible reference only.

CA-007: Connect the recorded baseline to explicit per-task promotion gates,
versioned thresholds, the release evidence/ROADMAP ledger and witnessed
single-host/multi-host acceptance. CI generated artifacts are supplementary,
not canonical task completion receipts.

Never overwrite `sofia.db`, silently bootstrap lost authority or automatically
migrate the canonical writer as part of this benchmark.
