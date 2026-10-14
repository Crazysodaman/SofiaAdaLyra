# V18 next 50: Phase 01 verification execution matrix (CA-901–914, CA-2201)

Checked against original task wording 2026-10-13. Every row below is **required verification**, not an assertion that it was executed. Source-only review and CI, user-host tests and production acceptance are separate.

| Task | Executable gate / independent evidence required | Cannot claim from CI alone |
| --- | --- | --- |
| CA-901 | Unit and integrated EXPERIENCE -> NEURO -> MEM -> PREFERENCE -> GOALS/LIFE -> RUN -> EMOTION/AVATAR/VOICE -> REL/ACT; exact event ID, principal, source, audience and effect receipts; stale cross-turn negative | Full causal chain from a successful model response |
| CA-902 | One genuine 3-day project: interest selection, admitted work, artifact bytes, independent critique, revision, complete/abandon, reviewed memory and opt-in disclosure with time-stamped receipts | Model saying a project is done |
| CA-903 | Owner-approved Gaia mock then hardware only with separate authorization; replay independently verified servo measurements and refuse unsafe serial commands | A simulated reading as real servo evidence |
| CA-904 | Restart, offline, no interest, rejected outreach, explicit denied SAFE grant, stale fact, uncertain RUN effect, game load and provider outage, all with stable state and no duplicate side effects | Happy-path background worker smoke |
| CA-905 | Venus primary and optional approved Fleet nodes: actual TTS sound, avatar expression timestamp, desktop/Discord transport receipts, dual Ollama routes and continuity through restart | Renderer plan or queued ACT state as audio heard |
| CA-906 | p50/p95 response, route token cost, model calls, per-hour wakeups, CPU/GPU/VRAM/RSS, IO, drift in precision, user interruptions and regression rate; exact scenario revision | Timing of deterministic mock as Venus GPU performance |
| CA-907 | Zero independent critical regressions for consent, privacy, SAFE, role-scope, factual claim, original DB write fencing, Gaia and STOP across adversarial and restart paths | Passing tests with unknown/warning failures suppressed |
| CA-908 | Bind every proof to exact commit, test name/host, input fixture, artifact SHA and verdict in existing ROADMAP+VERIFY, keeping coding/test/CI/live/soak/host stages distinct | Prose summary or GitHub green badge as completed task |
| CA-909 | 3+ real Windows restarts over multiple days with no undocumented interactions, duplicate tasks, missed observations or undesired outreach; independently observed uptime | Simulated stop/start in one process |
| CA-910 | Poisoned memory, audience collision, contradicted/stale facts, fake ACT receipt, role-spoof model response, attempted SAFE self-grant; prove denial at effect authority | Prompt filters without capability-side admission |
| CA-911 | Matched gaming/idle/active Windows cycles, NEURO competition toggled; compare real GPU and VRAM and hourly inference wakeups with controlled workload | Unpaired or nonrepresentative host captures |
| CA-912 | Break Discord, Hestia, weather, Fleet, JMRI, Gaia, local inference separately and combined; verify honest degraded state, no invented observation or unauthorized retry | Generic try/except returning a cheery response |
| CA-913 | Freeze 20 decision cases, including DO_NOTHING. For each, require developer trace, user-facing rationale, exact cause/evidence join, independent scoring and false-causality negative cases | A plausible-sounding explanation |
| CA-914 | Enforce stage machine: source-coded -> focused-test -> integration -> entire repository -> live Venus -> restarted/multi-day -> supervised Fleet/hardware -> owner acceptance. Higher stages require independent immutable receipts; refusal of missing or mismatched SHA | Automatic promotion based on self-attested true fields |
| CA-2201 | Existing `sofia.life.validation` closed objective registry: real SHA and bytes, typed text/size checks, malformed huge number UNKNOWN, subjective goals UNKNOWN, mutation FAIL; durable job and owner-reviewed original-objective proof still required | Size/phrase check alone as author-quality completion |

## CI commands for the non-host slice

`python -m pytest -q test/test_life_objective_parser_bounded.py test/test_v18_phase00_batch.py test/test_v18_decision_persistence.py`

For package coverage use existing `package-tests.yml`, `matrix-tests.yml`, Windows/Linux release candidate workflows and exact-revision installed-wheel verification. For the 50-item review itself, use `python -m sofia.verify.v18_next50_audit --repo . --expected-revision "$(git rev-parse HEAD)"` and its tests.

## Required host handoff packet
Exact SHA and installed wheel digest; machine OS/VM enrollment evidence; consent/auth event; pinned performance sensors; allowed test window; backup and rollback proof; resulting actual stdout/action/transport receipts; post-test health; explicit operator sign-off. Venus remains the active single database writer and must not be transferred by an automated test.

**Release rule:** No acceptance until independent task-specific end-to-end proof is recorded. Design documents, regression tests and CI status can advance development while leaving the task open. Research tasks may receive an independent design-review signoff, but it cannot substitute for production acceptance when that objective requires actual behavior.
