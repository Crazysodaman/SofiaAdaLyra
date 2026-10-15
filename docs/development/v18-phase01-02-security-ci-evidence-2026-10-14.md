# Sofía V18 Phases 01–02: Source-to-effect safety and CI evidence

Date: 2026-10-14 (America/Chicago). Work performed on `main` only.
Original source of scope: 66 Phase 01 and 30 Phase 02 CA requirements.
Gate standard: `docs/development/v18-gate4-development-standard.md`.
This is an incremental source/security audit, **not a blanket Gate 4 claim**.

## Actual production routes and authoritative owners

| Boundary | Production route | Authority and failure path |
| --- | --- | --- |
| Owner execution approval | `safe.owner_browser.authorize_exact_action` → signed WebAuthn challenge → `safe.execution_approval.ExecutionApprovalVerifier.record` → `matches_unconsumed/consume` | L3 exact actions need fresh independently verified WebAuthn. L4+ need an enrolled FIDO2 security key. Unverified older L3 rows cannot pass read or consume. L5 remains barred by capability authorization policy. |
| Emergency operator STOP | `safe.operator_stop.OperatorStopStore.set` → canonical `safe_operator_stop` + `safe_audit_event` | Owner STOP is immediate; signed/one-use exact-revision owner proof required to resume. STOP and resume share one SQLite transaction with the audit entry. No shadow state or automatic new canonical database. |
| Background autonomy | `application.background.ApplicationBackgroundCoordinator.run_once` → reflection, ACT, LIFE/Fleet/maintenance | STOP checked before scheduling and again after admission/budget checks immediately before each callback. Pending claims are closed on late STOP. Running callbacks remain independently responsible for checking STOP at the effect boundary. |
| Cognitive execution receipt | `cognition.tools.CognitiveToolDispatcher.tool_result_produces_execution_receipt` → `cognition.system.CognitiveSystem` | The host must report `CapabilityResultKind.SUCCESS` from the expected exact capability; no rejected response or model-provided evidence field can be reinterpreted as execution. Expected-effect data comparisons preserve JSON types, reject nonfinite values, and cap bytes. |
| Untrusted observations | `CognitiveToolDispatcher.format_result` → model tool result | Tool evidence is explicitly untrusted; normalized generic evidence is bounded by depth 16, 2,048 visited nodes, 128 children/container, and 32,000 chars for an individual field. Cycles and unsupported objects cannot recursively expand, and common structured credential fields are redacted. Filesystem content and entries are capped before joining output. This is NOT a universal secret scanner or injection immunity proof. |
| Recorded Gate-4 evidence | `verify.v18_gate4` → `verify.v18_ci_receipts` → GitHub Actions REST (read-only) | Validate proof digest/schema locally; authenticate remote run ID, exact SHA, repository, branch, completed success and workflow path using read-only GitHub API. Reject missing or symlinked local test selectors. Full test-selection relevance and owner/hardware acceptance require an independent reviewer. |

## Failure cases added

* Late STOP during reflection opportunity, ACT readiness and LIFE/Fleet task readiness.
* Repeated STOP during the same clock tick, backwards wall-clock adjustment and restart.
* Deleted STOP row or dropped STOP table cannot silently restore an inactive state; schema rollback occurs inside an explicit `BEGIN IMMEDIATE`.
* Forged Level 3 execution approvals and unverified legacy rows cannot be consumed. Verified Level 3 platform key remains accepted; Level 4 hardware-key rule is unchanged.
* Failed, denied, unavailable or cross-capability tool replies with fabricated success payloads cannot count as execution receipts; `True` does not equal `1` or `"true"`.
* Bad Unicode, NaN and infinite expected-effect data are not accepted.
* Hostile nested/cyclic tool evidence, huge filesystem results and secret-bearing structured objects have bounded formatting or redaction.
* Forged or failed GitHub run metadata, unsafe test selectors, missing test files and incorrect repo/SHA fail the new remote receipt audit.

## Independent CI receipts observed

* **PASS:** V18 Phase 01–02 SAFE and Release Source Gate, both Windows and Ubuntu, `faca57a8ef895ace0ff97b3cc3cbc6bc170e5d1d`, run `38657130342`.
* **PASS:** V18 Phase 01–02 SAFE and Release Source Gate, both Windows and Ubuntu, `fcad131fae19ee3181f228c2300ed4b9eaba314f`, run `38657588538`.
* **PASS:** V18 Phase 01–02 SAFE and Release Source Gate, both Windows and Ubuntu, `5b3e851906b4d1b091c72fd8c97b456c11fba34f`, run `38657795648`.
* **PASS:** same focused Windows/Ubuntu gate at `4b91d5ecbf6feb381665b15f0e116278afe700af`, run `38658371126`.

Run status is referenced only after both OS jobs actually completed. Newer source revisions demand their own CI proof; earlier green runs do not certify later files.

## Residual security and Gate 4 work

1. Prove in-flight cancellation of long-running autonomous callbacks and external mutations, including stop loss between local precheck and remote effect. At-most-once/uncertain-outcome reconciliation is still needed.
2. Expand AgentDojo-style hostile sources across Discord, GitHub issues/files, local logs, SVG/JSON artifacts, memories, network and Fleet inputs. Redaction by common field name cannot catch free-text secrets.
3. Prove L3 standing-grant scope and revocation immediately before EVERY mutating executor, including direct platform and VM APIs; source tests alone are not a complete attack surface review.
4. Prove actual historical Gate 4 test selector relevance, installed-wheel provenance, all 22 package suites, release candidate and supervised single-/multi-host acceptance. Many heavy CI runs have been cancelled while `main` receives rapid source changes; a cancelled workflow is NOT a passed gate.
5. Run specified longitudinal requirements (three-day project, 24-hour idle metrics, actual Windows restarts and week-long acceptance) at the real hosts before assigning Gate 4 to those original tasks.
6. Design/owner acceptance tasks may only pass after an independently reviewed deliverable, not by adding an arbitrary code module.

No host runtime, VM, database ownership, production keys or operator approvals were changed. `main` source is the only output. Canonical source status remains `docs/development/v18-task-evidence.json`.
