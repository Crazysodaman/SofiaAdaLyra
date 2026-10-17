# CA-3502: independent creative success and authority separation

**Status:** reviewed source/design candidate, **not independently accepted Gate 1**. Original requirement: *Separate generator, reviewer, test oracle, evidence store and approval authority. Identify which existing components already provide independence and prohibit an LLM from self-minting success receipts.*

**Source revision examined:** `6b839026ea2c9d0fdfc1a0dcd78c75cfba4236ab`, `main` (October 17, 2026). All host behavior and future acceptance must be retested at the actual review SHA. This design follows the owner's canonical `sofia.db` and protected SAFE approvals. It creates no alternative source of authority.

## Canonical independent roles

| Role | Actual existing owner and interface | May say / do | Must NEVER be allowed |
| --- | --- | --- | --- |
| Generator / proposer | `life/draft_agent.py`, `life/idea_agent.py`, provider behind COGNITION | Suggest project concepts, draft bytes and optional critique commentary | Mark its generated content as passing an original objective, grant a permission, authenticate external work, invent evidence |
| Original brief / selection | `life/model.py` `ProjectIdea` / `ProjectBrief`, `life/coordinator.py` | Carry original bounded objective strings and selected project scope across lifecycle | Change criteria after work to make arbitrary output pass; silently remove unsupported criteria |
| Objective-checking oracle | `life/validation.py` `inspect_objective_artifact`, closed `_VALIDATORS` | Independently read original revision path and bytes, bind SHA-256, check original typed objectives, report PASS / FAIL / UNKNOWN | Interpret model prose or JSON `true` as quality; run untrusted Python while checking syntax; upgrade UNKNOWN to PASS |
| Structured review | `life/validation.py` `StructuredArtifactCritique`, `structured_critique_from_report`; `life/coordinator.py` `prepare_artifact_critique` | Keep measurable outcome, optional subjective `PersonalJudgment`, deterministic revision suggestions and independently checked structural confidence distinct | Mint its own RUN receipt, confer new goal authority, self-approve a subjective owner preference |
| Canonical execution and external effect | `run/work.py` `TaskExecutionManager`/`DurableWorkStore`; `life/coordinator.py` `schedule_artifact`/`_create_artifact`; `capability/gateway.py` | Admit and settle bounded, authorized work; attach canonical operation result and original revision evidence | Treat `WorkStatus.COMPLETED` alone as independent goal success or bypass SAFE |
| Evidence storage and lookup | `goals/evidence.py` `GoalEvidenceLedger` and `GoalEvidenceIndex` on canonical SQLite; CREATIVE revision store; LIFE evaluation/experience store | Record/read typed evidence with principal, audience, observed time, source and linked action/goal; store original revision digest | Accept a model-provided evidence-reference-looking string as a verified observation |
| Approval authority | `safe/execution_approval.py` one-use execution approvals; capability/GOALS authorization and `safe/operator_stop.py` | Require independent exact-action authorization, owner presence where protected; support revoke/stop | Derive permission from creative quality, personal taste, model confidence, a project completion flag or a request from retrieved text |
| Final state decision | `life/coordinator.py` `evaluate_artifact`, `commit_artifact_critique`, `_settle_personal_project`, `_settle_verified_milestones` | Recheck immutable original artifact/revision, scoped successful RUN receipt, objective report and canonical project state; persist idempotent evaluation and guarded transitions | Let a generator award its own success or let false revisions escape original resource/consent gates |
| Independent Gate 1–4 acceptance | External, owner-approved reviewer under `docs/development/v18-gate4-development-standard.md` | Review original task and independent test evidence; record signed review when requirements met | Accept CI green, historical source packet, or the model's own self-reported evaluation as sufficient review |

## End-to-end source-to-authority chain

```text
Original approved brief and scope -> LIFE proposes bounded work
    -> SAFE / GOALS / RUN authorize and execute the exact operation
    -> actual creative revision + RUN operation receipt
    -> independent byte/path/SHA-256/revision check
    -> closed original-objective checker (PASS / FAIL / UNKNOWN)
    -> StructuredArtifactCritique
       - technical outcome (evidence-based only)
       - optional personal judgment (separate, default UNKNOWN)
       - confidence (fraction of original objectives independently graded)
       - revision plan (suggestions ONLY, not executable authorization)
    -> LIFE rechecks revision/receipt and stores original evaluation
    -> guarded milestone / complete, pause, abandon or bounded revision
    -> experience / preference eligible only under original evidence guards
```

**Operator/owner consent is a separate branch.** A subjective LIKE/DISLIKE does not prove technical success, and technical success does not imply personal satisfaction or social outreach authorization.

## Required negative and recovery contract

1. Generator outputs `{"passed":true}` or a convincing `review_success` field: ignore as a technical verdict. `test/test_life_objective_parser_bounded.py` and `test/test_v18_success_oracle_contract.py` are candidate coverage, not independent acceptance.
2. An original natural-language objective has no registered predicate: return `UNKNOWN` and refuse independent completion; do not substitute easier model-selected criteria.
3. A copied file at another path or an in-place symlink/swap: source identity/hash/metadata must fail; do not elevate the substitute to the original RUN revision.
4. A source-backdated, cross-principal/audience, revoked, stale, wrong-goal or fabricated receipt: `_confirmed_artifact_run_receipt` and scoped evidence checks must fail before critique settlement.
5. A valid revision's objective PASS with an explicit DISLIKE: store both independently, never overwrite one with the other. Existing LIFE tests cover preference-vs-technical distinction; `test/test_life_structured_critique.py` targets the new boundary.
6. Forged revision-plan text or a new artifact revision after prepare: `commit_artifact_critique` rechecks the original report and refuses inconsistent drafts.
7. Restart after RUN completion, after evaluation commit or before milestone persistence: canonical LIFE store and CAS recover without duplicate work or fabricated completion. See `test/test_life_verified_milestone_production.py`.
8. An operation is UNCERTAIN or SAFE approval revoked: no automatic retry, fresh permission acquisition or project success derived from pending external effects.
9. An untrusted code artifact that parses but fails Python compilation: no independent syntax PASS; syntax validation never executes the code.
10. Objective-only PASS, without originally required human-quality or physical-world claims, is explicitly restricted to structural eligibility. Original subjectivity remains unverified.

## Remaining G1 evidence

- Audit actual source-to-effect callers for every live deployment path and prove the structured review is used by `_settle_personal_project`; it is now wired in source on `main`, not yet independently signed or accepted.
- Pin relevant Windows and Linux test selectors and inspect exact CI assertions, especially LIFE/RUN/SAFE integration, unknown objective denial, original source path, replay and restart. Installed-wheel coverage must be demonstrated.
- Demonstrate that SAFE approval and owner presence are exercised at their own boundary, not retroactively inferred from a passing artifact. Capture specific original requirements and reviewers.
- Obtain independent design review and owner acceptance of role division; review any live-host or multiday obligations separately, where originally mandated.

**No Gate 1 or later task status is promoted by this design document.** A completed diagram is not a security proof, permission grant, executed test, or certified original-task acceptance.
