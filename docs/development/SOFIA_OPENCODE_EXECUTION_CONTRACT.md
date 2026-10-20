# SOFÍA V18: OPENCode DEVELOPMENT & PRODUCTION-INTEGRATION CONTRACT

**Status:** Operator-supplied development contract, not a release authorization  
**Prepared:** 2026-10-20  
**Repository:** `Crazysodaman/SofiaAdaLyra`  
**Target branch:** `main` (existing owner convention; respect repository Git rules)  
**Baseline inspected:** `fd9d319241f98c646135677552a3d2d8992d5124` on `main`  
**Workload:** 700 CA requirements + 40 ML + 40 GA = 780 planned items; open GitHub issues, uncaught regressions, implementation gaps, and unverified production work **in addition** to the task index.  
**Mission:** Turn requirements and defects into *real, integrated, testable, reviewable functionality*, not just code fragments, green-looking badges or another plan.

> **Non-negotiable distinction:** source code on GitHub ≠ integrated runtime ≠ packaged release ≠ installed active release ≠ observed live behavior ≠ independently accepted Gate 4. Never collapse those states. Never award yourself an independent acceptance certificate.

---

## 1. FIRST THING THE AGENT MUST DO

On every new OpenCode session, **start acting, not just planning**:

1. Read the existing root `AGENTS.MD` in full. On Windows do not create a second `AGENTS.md` with different case; that could overwrite or conflict with it. Existing authority, evidence and Git constraints prevail.
2. Read this entire contract. Then examine the current Git status, branch, HEAD SHA, running environment and existing uncommitted changes **without modifying them**.
3. Locate and read the live original requirements, 780-item atlas and ledger, Gate 4 scripts, CI definitions, top-level architecture, and all currently open GitHub issues and PRs. Do not assume the inspected baseline is still current.
4. Build a reproducible inventory of **every** outstanding task, GitHub issue, tracked `TODO`/`FIXME` with code impact, failed/ignored/empty test selection, disabled wiring, release gap and actual runtime defect. Deduplicate by references; never discard an issue because it does not have a CA/ML/GA number.
5. Select the highest-priority coherent implementation batch allowed by the safety boundaries, write objective acceptance tests, **make concrete code changes**, execute focused tests, inspect integration and packaging, then publish an evidence-based result. If one item is blocked, record it and continue other eligible items.
6. Before ending a session, save a handoff specifying remaining defects, exact paths changed, commands run, test results, SHA(s), permissions pending and the *next executable step*. Do not merely say “continue later”.

**Stop condition:** All safely executable work for the current batch has either been implemented and verified or has a named, evidence-backed blocker. Do **not** stop after producing an inventory, a design, a TODO list, mock code, or a passing unit test if production wiring remains missing.

### First-turn output contract

After the initial audit, produce these items and then immediately begin the first change:

- `BASELINE`: branch, SHA, dirty state, runtime access, OpenCode/model version.
- `QUEUE`: scoped backlog with item IDs and concrete evidence, plus one prioritized batch.
- `IMPLEMENTING NOW`: exact source/tests/integration points to change.
- `SAFETY`: changes that require separate owner approval.
- `EVIDENCE LOCATION`: machine-readable receipts and human-readable summary for the batch.

**Forbidden substitution:** A very long plan does not count as implementation. The agent's next action after planning must be inspection or modification of a real file, a test, or a verifiable reproducible issue.

---

## 2. HONEST MODEL SELECTION

### Big Pickle recommendation

`opencode/big-pickle` may be useful for small, independently testable patches, reviewing code layout, drafting specs or examining one subsystem. **Do not appoint it the sole autonomous release engineer for all 780 tasks.** Independent October 2026 small-task tests were encouraging, but did not test a repo this complex. Reports cite long-context degradation, unwanted Git operations and inconsistent output. OpenCode says Big Pickle's free-period data may be used to improve the model.

**Recommended split:** use a capable coding/reasoning model for multi-file design, integration, security, release troubleshooting and acceptance evidence; a second independent reviewer where possible; Big Pickle only for bounded low-risk work if desired. Choose from `opencode models` rather than hardcoding a model that may disappear or a benchmark that does not prove suitability. Some other free models have different retention terms. Validate current provider terms and cost before use.

**Data boundary:** Only use a clean, source-only checkout with cloud models. Do not feed cloud OpenCode production databases, credentials, tokens, owner chat logs, screenshots, private avatar media, local service registry exports or unredacted telemetry. `.gitignore` does **not** prevent an agent from reading local untracked files. Use filesystem isolation and limited tool permissions, not just a prompt.

**No absolute guarantee:** A prompt cannot compel a model to execute indefinitely, keep a service running, pass CI, or invent missing hardware evidence. The controls in this contract make skipping work **detectable and rejectable**.

---

## 3. SOURCES OF TRUTH AND RECONCILIATION

Never treat a single tracker as complete. Audit the **union** of the following, with provenance:

| Source | What it contributes | Required handling |
|---|---|---|
| `docs/roadmaps/Sofia_Companion_Autonomy_Master_Roadmap_V18_Priority_Phases.md` | Original CA definitions and phase priorities | Read original task text and acceptance clauses. Never infer requirements from a task title alone. |
| `docs/atlas/Sofia_Complete_System_Atlas.md` | Full 780-system atlas including ML/GA | Reconcile actual CA/ML/GA IDs and dependencies. |
| `docs/development/v18-task-evidence.json` | Existing per-task evidence ledger | Preserve provenance. Do not mass-promote statuses. |
| `gate4-progress.json` and `gate4-progress.md` | Generated progress and verifier report | Re-run exact verifier before claiming a new count. Treat snapshots as snapshots. |
| `docs/development/v18-gate4-independent-acceptance.json` | Independently authenticated acceptance certificates | Only authorized independent evidence updates Gate 4 acceptance. Never self-sign or fabricate records. |
| GitHub **open issues, PRs and comments** | Reported defects, blockers, cross-subsystem gaps | Enumerate using GitHub/API `gh` when available. Link issue references to tasks without replacing them. |
| `.github/workflows/` and GitHub Actions | Release/CI reality | Distinguish failed, skipped, cancelled, not-run, stale-SHA and passing jobs. |
| `src/`, `test/`, scripts, config, manifests, installer/service paths | Actual implementation and gaps | Trace actual startup callers and user-facing production paths, not merely modules that import. |
| Owner/operator verified logs and installed release receipt | Live-host facts | Use only when specifically authorized and accessible. Never fill these with guessed values. |

**Known checked-in baseline, not a live verdict:** The project describes 780 tasks (700 CA + 40 ML + 40 GA); the checked-in Gate 4 progress snapshot showed **0 independently accepted Gate 4 items** at inspection. The original 700's code-status breakdown in that snapshot was 421 unassessed, 273 partial and 6 code-present/unverified. Those are *triage labels*, not proof of unfinished percentage. On 2026-10-20, the accessible GitHub issue search returned **issue #119 as the only open issue**. Requery each session because this can change. The 700-task issue body preserves an older baseline and does not supersede current 780-count accounting.

**Item identity:** Every discovered problem gets a stable reference (`CA-*`, `ML-*`, `GA-*`, GitHub `#N`, or `DISC-YYYYMMDD-NNN`), fingerprint, owning subsystem, observed evidence, source revision, priority and status. One root cause may satisfy multiple requirements, but every requirement must retain its own proof.

**No false negatives:** If the GitHub API is unavailable, report `issues: UNKNOWN (API unavailable)`, not `zero open issues`. If Windows is inaccessible, report `Windows host: NOT TESTED`, not `Windows passed`.

---

## 4. PRIORITY AND DEPENDENCIES

Apply this order unless verified dependencies require another order:

1. **P0 release blockers:** broken tests or imports, package/source mismatch, zero-test CI jobs, security/privacy regression, duplicate writer, unbounded data export, bad installer/active release, loss of canonical state.
2. **P0 owner-impacting defects:** service fails to start, broken chat, authority leak, memory/privacy violation, installation or recovery defect. Never jeopardize canonical data to diagnose them.
3. **Open issue #119:** same-SHA CI, Windows and Linux package/release gates, cross-channel identity and memory, LIFE, later host/NEURO gates. This is an umbrella acceptance issue, not a checkbox to close after one patch.
4. **Known incomplete production wiring**, including MENTOR runtime/service deployment and behavior observability, tray controls, avatar assets, voice, ComfyUI service lifecycle, Discord/Android, RUN/LIFE and approved memory workflows.
5. **Remaining planned requirements**, in phase/dependency order, in batches of approximately 5–20 tightly related requirements when feasible. Never batch by number alone and leave 20 disconnected stubs.
6. **New code-observed defects** even if no roadmap ID exists. Do not hide a production bug outside the 780 count.

Keep separate queues for `READY`, `IN_PROGRESS`, `BLOCKED_OWNER`, `BLOCKED_ENV`, `BLOCKED_DEPENDENCY`, `SOURCE_IMPLEMENTED`, `TESTED_LOCALLY`, `CI_VERIFIED`, `DEPLOYED_VERIFIED`, and `GATE4_INDEPENDENT_ACCEPTED`. A task can be developed and tested while live deployment remains blocked by authorization. That is a *partial* completion report, not failure to work.

Selection algorithm: group by shared runtime flow; prioritize severity and dependency; require a demonstrable end-to-end acceptance scenario and feasible environment; pick the best ready group; implement it before accepting more scope. Do not choose only trivial tests to inflate counts. Preserve tracked blockers and retry when their prerequisites change.

---

## 5. PRE-FLIGHT: PRESERVE THE WORKSPACE

Run read-only checks before modifying any files, adapting to the host shell:

```powershell
# Execute from the existing local checkout or an isolated worktree.
Get-Location
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git status --short
git diff --stat
git diff --cached --stat
git remote -v
python --version
python -m pytest --version
opencode --version
opencode models
```

- If the worktree is dirty, **do not use** `git reset --hard`, `git checkout --`, `git restore`, `git clean -fd`, blind `git stash`, history rewrite or destructive merge. Preserve pre-existing work. Use an owner-approved isolated worktree or restrict changes to safely separable files.
- Confirm whether your `H:` checkout is a network-mapped path. A path that looks local to the user may map to an Artemis SMB share. **LocalSystem cannot be assumed to use it.** Never “fix” service access by granting broad SMB privileges or moving the canonical database.
- Check other actors are not writing to the same checkout/branch. Do not silently overwrite Codex/owner edits. Refresh `main` cautiously; stop on a non-fast-forward and diagnose.
- Do not enable automatic Git pushes, releases or live installs based on this document. The existing `AGENTS.MD` says Git commits/pushes require the intended workflow approval and automatic push is forbidden.
- Do not give OpenCode production credentials, local administrator elevation, secrets manager access or the right to alter service settings implicitly.

**Repo setup note:** The root already has an uppercase `AGENTS.MD`, and an `opencode.jsonc.old` was visible in the root. Merge any future OpenCode config with existing instructions; do not rename/overwrite these automatically.

---

## 6. THE MANDATORY ENGINEERING CYCLE

The agent **MUST** complete the following cycle for each batch, rather than just writing a proposal.

### A. Establish the requirement and evidence baseline

For every scoped item, store exact acceptance-language excerpts/links, testability, current evidence and “unknown” parts. Inspect code and issue history relevant to the feature. Record the starting SHA and failing behavior **before** changing it.

Classify each acceptance criterion as `EXISTS_VERIFIED`, `EXISTS_UNVERIFIED`, `PARTIALLY_WIRED`, `MISSING`, `BLOCKED_AUTHORIZATION`, `BLOCKED_ENVIRONMENT`, or `NOT_APPLICABLE_WITH_REASON`. A file/function existing is not equivalent to a working capability. Verify routes, callers, registration, dispatch, state transition, error handling, persistence, config, documentation and installer packaging.

### B. Trace the real production path

For a user-visible feature, draw or describe:

`entry point -> authentication/authority -> composition/bootstrap -> handler -> domain logic -> persistence / side effect -> telemetry -> installed-package path -> actual user-facing observation`.

For scheduled work, trace:

`existing coordinator -> eligibility/idle/STOP gate -> task admission -> bounded execution -> restart reconciliation -> outcome verification -> history / owner-facing state`.

For voice/avatar/tool actions include actual UI/protocol edges and safe no-op/disable paths. For Windows services include process identity, source-root availability, active-release child inheritance and component version, not just editable checkout code.

**Anti-stub test:** Identify at least one *actual production* entrypoint invoking the changed feature, an integration test that traverses it, and an observable output/failure mode. Otherwise, classify `NOT_IN_PRODUCTION_PATH` and keep working.

### C. Write a measurable acceptance matrix

For each requirement, specify:

- Positive user/system scenario with expected side effect or returned result.
- Negative/authorization scenario (unprivileged, revoked, missing consent, path traversal, wrong session, busy/gaming, STOP).
- Persistence/restart scenario when state matters.
- Error, timeout, cancellation and crash-boundary behavior.
- Install/release or service identity verification where relevant.
- Observable evidence, test fixture names and exact command.

Write tests before or alongside implementation; fail the test for the intended root cause when practicable. Tests must assert behavior, not only that a class exists. Preserve existing tests, add negative tests, and verify tests are actually **selected** in package CI.

### D. Implement all required layers

Perform actual source modifications. Reuse existing architecture and services. Deliver a vertical slice, including as applicable:

1. Configuration with documented defaults, validation, feature-flag semantics and safe disabling.
2. Composition/registration/startup and shutdown; import/call path is real.
3. Authority check at execution boundary, STOP/consent/revocation/least privilege.
4. Domain implementation, bounded resource handling, error categorization, retry/idempotence.
5. Durable storage and migrations (if required) without a second canonical writer.
6. User-facing CLI, tray, Discord/Android/API surface where requirement says it exists.
7. Runtime observability, clear status, safe redaction and diagnostics.
8. Packaging, manifests, service host/release expectations, smoke tests and rollback path.
9. Tests, documentation, evidence and operators' activation steps.

Never call a new module “done” until the **real composition root** uses it. Never introduce fake output, placeholder classes, commented-out integrations, tests with hard-coded success, broad exception swallowing, permissive defaults, sham schemas or feature flags that are always off with no approved activation plan. Flag disabled-by-design opt-in features honestly.

### E. Verify in layers

At minimum:

1. Run changed-file syntax/type/import checks as supported by the project.
2. Run named focused tests and record exit codes and test-selection counts.
3. Run related subsystem integration tests, including failure/restart/authorization cases.
4. Run package/release validation available in the current environment. Inspect wheel or installed entrypoint when relevant.
5. Run the full configured test suite before *batch-complete* claims, unless genuinely blocked, and mark unrun suites transparently. Do not silently substitute `pytest -q` if the project uses a partitioned CI matrix.
6. Check relevant GitHub Actions on **the exact tested commit SHA** when authorized and available. Treat skipped, cancelled, pending, stale SHA and zero-selected-test jobs as not passing acceptance.
7. For physical Windows/Artemis/Android/Discord/ComfyUI tests, obtain actual operator-approved host receipts. A Linux mock/CI job cannot stand in for hardware acceptance.
8. Inspect `git diff`, `git status`, source-to-package provenance and regressions before checkpoint.

Example targeted Windows invocation (only when matching tests exist):

```powershell
python -m pytest -q test/test_mentor_windows_service_settings.py
python -m pytest -q test/test_mentor_foundation.py test/test_mentor_report.py
python -m sofia.verify.v18_gate4 --repo . --output gate4-progress.json --markdown-output gate4-progress.md
```

Keep the exact process return codes. If a test path differs, locate it and report the corrected path rather than manufacturing a green result.

### F. Independent review and honest closure

Audit diff for security and performance; preferably have a **different model or reviewer** inspect changed source and challenge assumptions. Model agreement is advisory, not a test oracle. Run a final unmodified test command after fixes. Only propose independent Gate 4 acceptance after the repository's required authenticated proof and task-specific receipts genuinely exist. Never write to signed acceptance registries on the model's own authority.

**Definition of locally complete:** correct functionality integrated into actual code path + positive/negative tests + packaging path checked where relevant + recorded commands/exit codes + no unresolved known defect in the scoped behavior. **Definition of deployed:** explicitly approved installer/activation occurred on the target host and the installed revision was verified. **Definition of Gate 4:** only the independent authenticated verifier's actual rules, not the agent's opinion.

---

## 7. MENTOR: FIRST-CLASS OPEN INTEGRATION CASE

MENTOR is **not** solved by finding `src/sofia/mentor/`. Treat it as an end-to-end product with several distinct scopes. The Oct 19 repo docs provide the current contract; re-audit current code at the latest SHA.

### Existing components to verify, not blindly reimplement

- `src/sofia/mentor/`: read-only audit/report, local synthetic dialogue, independent answer keys, behavior monitor/history and Windows service setting helpers.
- `src/sofia/application/emotional_conversation.py`: settled-reply passive observer hook.
- `ApplicationBackgroundCoordinator`: optional bounded idle monitor registration.
- `src/sofia/mentor/__main__.py`: operator diagnostics including behavior-service status/plan.
- `.github/workflows/mentor-readonly-audit.yml` and named mentor tests.
- `docs/development/mentor-continuous-personality-emotion-2026-10-19.md` and `mentor-windows-service-activation-2026-10-19.md`.

### Known gaps in the inspected documentation

1. A synthetic `qwen3:14b` smoke test succeeded, but `runtime_turn_tested:false`. This does **not** demonstrate real Sofía turn evaluation.
2. The service runs as `LocalSystem`, with potentially separately pinned active-release code. A Git pull does not update its installed wheel or restart it.
3. Developer-shell MENTOR settings do not establish what the running service process received.
4. The owner's checkout path was observed to resolve through an `H:` network mapping / UNC share. MENTOR intentionally refuses a service `source-root` on that mapping. Do not widen share access or relocate `sofia.db` as a workaround.
5. Source read-only registry query and local-source validation fixes exist; re-verify them and the installed stable service host.
6. Local synthetic conversation runs are **not** the same as `SofiaApplication.conversation.respond`; do not report synthetic capability as full production mentoring.
7. Optional private-turn scoring must not upload raw conversation or silently enable external API use. Local `qwen3:14b` is an advisory critic, never a SAFE/FIDO2 or release authority.

### MENTOR mandatory work items

**M-01 Source/packaging audit.** Identify actual service host loader and release selection, where `MentorBehaviorEnabled` and `MentorSourceRoot` are read, and whether the stable installed host and active-release child contain the intended MENTOR observer. Ensure the release manifest/wheel includes all necessary files. Evidence: paths, installed vs checkout version checks, tests.

**M-02 Composition audit.** Trace final persisted real response to passive observe queue, then idle coordinator to local critic and numeric-only scores. Test owner/private scoping, replay deduplication, bounded queue, long input rejection, expired sample cleanup, busy/game unknown gates, disabled state, failed Ollama, STOP, shutdown and restart.

**M-03 Service settings.** Validate read-only status for standard user, missing registry key, malformed settings, safe paths and rejection of network roots; retain explicit approval on `enable`/`disable`; no implicit service restart.

**M-04 Authenticated observability.** Provide or improve a **supported, authenticated** owner diagnostic for actual service-account review counts/health without exposing conversation samples or unauthenticated debug endpoints. A zero in an interactive developer profile does not prove a zero in `LocalSystem` history.

**M-05 Synthetic versus production truth.** Keep local synthetic two-model evaluations separate from live application pipeline. Tests must fail if their results are mislabeled as production acceptance.

**M-06 Independent quality.** Critic output never self-certifies factuality/personality/emotion. Require fixed oracles, blinded/unseen scenarios where possible, observable voice/avatar receipts for those modalities, and human spot-review of failure findings.

**M-07 Owner-assisted deployment plan.** Prepare exact signed/verified release activation, LocalSystem-readable *local* path, runtime compatibility and rollback checklist. Do not perform it without explicit separate host-change approval. After approval, prove one consented real turn produces a service-owned numeric review when idle and no review is produced when disabled/gaming/STOP.

**MENTOR acceptance statement required:** `Source integrated [Y/N]`; `Windows stable service version observed [Y/N]`; `active release version observed [Y/N]`; `actual LocalSystem review observed [Y/N]`; `private data stayed local [Y/N/UNKNOWN]`; `owner-approved activation [Y/N]`. Any `UNKNOWN` or `N` prevents claiming fully deployed MENTOR.

---

## 8. OTHER HIGH-RISK SUBSYSTEM CONTRACTS

| Subsystem | Concrete integration proof required |
|---|---|
| Canonical runtime / Venus -> Artemis migration | Venus remains single writer until separately approved Phase 03 migration. Verify one writer, ownership, shutdown, rollback and DB integrity. No shadow-brain failover or silent cutover. |
| Conversation, Discord, Android | Authentication, session/audience isolation, display consent, deduplication, message order, paging, revoke, restart and negative cross-channel exposure tests. A session ID alone grants no authority. |
| Memory / correction / privacy | Temporal provenance, revocation, deletion, backup/restore behavior, no resurrection of corrected/suppressed facts, privacy boundaries and owner-visible evidence. |
| Personality / emotion / relationship | Test real application response pipeline, after persistence, channel matching, non-repetition, quiet hours, interruptions and honest emotion semantics; no canned fake persona pass. |
| LIFE / RUN / Project Forge | Genuine artifact bytes, objective validation, persistent scheduling, authenticated authority, durable reconciliation, idempotence, restart/crash tests. No fake “done” goals. |
| 2D avatar / wardrobe / ComfyUI | UI controls reach real state/assets; rig/slot geometry, correct image parts, lifecycle/open-close/crash recovery, permissions, content separation, no test-only placeholder art called complete. |
| Voice / screen / OS control | Real consent, per-host capabilities, active-gaming exclusion, STOP, no unauthorized input, actual Windows and Linux checks, no simulated speech receipts labeled observed. |
| BODY / robotics | Simulator-first, actuator authority gates, emergency STOP, no accidental physical movement, negative test assertions and hardware acceptance only with supervision. |
| Workshop / Hephaestus / NEURO | Explicit provisioned isolation, quotas, provenance, bounded experiments, no grant of new authority from training or an evaluator. |
| Release / Windows service / CI | Same-SHA install provenance, correct wheel contents, clean test selection, service principal/active release checks, restart verification and rollback. |

**Protected invariants:** Existing authority model, constitution, FIDO2 approvals, STOP, private data, one canonical DB writer, approved GPU gaming policy, artifact safety, resource budgets and nonautomatic external disclosure. Never weaken these to claim progress.

---

## 9. GITHUB ISSUES, PULL REQUESTS, CI AND CODE DISCOVERY

### Mandatory discovery cadence

Requery at batch start and after significant merge (if authorized): GitHub open issues including body/comments, open PRs including reviews and status checks, failing current-HEAD GitHub Actions, project issue references in source/docs, `TODO`/`FIXME`/`NotImplementedError`/`pass` in production-critical locations, test skips/xpasses, feature flags, inactive registrations, packaged-but-unreachable modules. **Not every `pass` is a defect:** prove reachability and intent; false positives stay `TRIAGED_NOT_A_DEFECT` with reasons.

Example commands, only if `gh` is installed and authenticated with appropriate access:

```powershell
gh issue list --repo Crazysodaman/SofiaAdaLyra --state open --limit 200
gh pr list --repo Crazysodaman/SofiaAdaLyra --state open --limit 200
gh run list --repo Crazysodaman/SofiaAdaLyra --branch main --limit 30
rg -n 'TODO|FIXME|NotImplementedError|xfail|skip\(' src test scripts .github
```

If no `gh` or `rg`, use the GitHub integration or Git API and native search. Do not install new CLI tools without permission. Never let absence of one tool abort source coding.

### Issue #119 acceptance structure

For the known open umbrella issue, keep sub-evidence separate:

- Same-SHA full CI and release candidate package/provenance checks.
- Phase 05 authenticated desktop/Discord/phone/restart scope.
- Phase 06-07 correction/revocation/deletion/retention proof.
- Phase 08-09 personality and LIFE outcome truth.
- Phases 11-15 device/host gates as available and approved.

Do not close issue #119 until all issue-owned criteria actually pass and a permitted maintainer authorizes closure. Linking a successful patch does not close an umbrella issue. Propose new issues for uncovered defects or unblocked follow-ups; issue creation is a repository write and must follow Git permissions.

### CI contamination prohibitions

No shrinking CI selectors to zero, unconditional skips, disabling negative assertions, deleting regressions, raising timeouts without diagnosing hangs, replacing real entrypoints with mocks in a production test, undocumented CI condition changes, or certifying a stale SHA. If CI is flaky, reproduce root cause and show the before/after statistical or deterministic evidence.

---

## 10. GATE MODEL AND ACCEPTANCE POLICY

Treat tracked task status and release evidence as separate dimensions. Use repository-specific verifier conventions when names differ.

| Gate | Operational meaning | Evidence threshold |
|---|---|---|
| G0: DISCOVERED | Original requirement or defect identified | Stable ID + provenance + owner/subsystem + original text |
| G1: ANALYZED | Real code-to-requirement reconciliation | Paths, entrypoint trace, missing behaviors, acceptance matrix |
| G2: IMPLEMENTING | Concrete, meaningful source modifications | Diff linked to requirement, not just a design file |
| G3: PRODUCTION_CODED | Full approved code path exists, wired to actual caller/packaging | Source trace, config, interfaces, negative-path implementation and packaging inspection |
| G4-CANDIDATE: TESTED | Focused/integration/full suite as applicable; independent review sought | Exact SHA + nonempty tests + objective results + unresolved-environment disclosure |
| G4-INDEPENDENT: ACCEPTED | Repository's signed/independently authenticated acceptance protocol satisfied | Genuine authorized certificate and task-specific proof. Agent cannot self-award. |
| G5: LIVE TRIAL (if needed) | Extended owner-authorized host trial | Real operational time window and device/host receipts; never assumed from CI |

If the repository describes slightly different stage labels, **preserve the actual schema**, map this table in human prose and do not overwrite accepted fields with invented labels. For requirements that genuinely mandate host trials at G4, do not demote the requirement to make it easier; record `BLOCKED_HOST_ACCEPTANCE` until completed. The user's target is **every applicable requirement fully implemented and verifiably tested through G4**, with multi-day behavior tracked separately where permitted by the original task acceptance.

**Exact-SHA invariant:** test SHA, source SHA, wheel build provenance, installed release SHA, and acceptance SHA must agree or be explicitly recorded as different and not conflated. CI on an older green SHA does not accept new code.

---

## 11. MACHINE-READABLE EVIDENCE: REQUIRED FOR EACH BATCH

Create or update a **separate work evidence area** at a non-sensitive, repo-approved location such as `docs/development/opencode-evidence/` only if consistent with existing schema. Do not edit the independent certificate registry to force a pass. Use a record following the fields below; adapt its format only if a working established schema exists.

```json
{
  "schema": "sofia.opencode.batch-evidence.v1",
  "run_id": "YYYYMMDD-HHMM-batch-slug",
  "captured_at_utc": "ISO-8601-time",
  "base_sha": "full-git-sha",
  "tested_sha": "full-git-sha-or-null",
  "branch": "main",
  "item_ids": ["CA-xxxx", "ML-xxxx", "GA-xxxx", "GH-119"],
  "requirement_refs": ["file:line-or-issue-url"],
  "initial_failures": ["observed error and reproducible command"],
  "changed_files": ["src/...", "test/..."],
  "production_call_paths": ["startup -> handler -> side effect"],
  "tests": [
    {
      "command": "python -m pytest ...",
      "exit_code": 0,
      "selected": 1,
      "passed": 1,
      "failed": 0,
      "skipped": 0,
      "environment": "Windows 11 dev or GitHub ubuntu runner",
      "artifact_ref": "log or CI URL"
    }
  ],
  "ci": {"sha": null, "required_jobs": [], "status": "NOT_RUN"},
  "installed_release": {"sha": null, "host": null, "status": "NOT_TESTED"},
  "security_review": {"authority": "NOT_TESTED", "privacy": "NOT_TESTED", "rollback": "NOT_TESTED"},
  "remaining": ["specific outstanding work"],
  "blockers": [{"type": "OWNER_APPROVAL", "next_action": "precise requested authorization"}],
  "claimed_stage": "G3_OR_LOWER_UNTIL_PROVEN",
  "independent_gate4_certificate": null
}
```

Never use fictional SHA values, fake pass counts or made-up file:line references in an actual receipt. `NOT_RUN`, `UNKNOWN`, `BLOCKED_*` and `0 selected` must be visible. `selected=0` is **not** success. Only record an independent certificate identifier after verifying it through the established authenticated verifier.

### Required human-readable batch report

```text
BATCH: [IDs / user-visible outcome]
BASE: [full SHA / dirty state]
CHANGED: [exact files + purpose]
PRODUCTION PATH: [real entrypoint through side effect]
TESTS: [commands | selected | pass/fail/skip | exit code | platform]
PACKAGING: [what real package/install path was inspected]
SECURITY: [checks performed and failures]
GATE: [per-ID stage; never merge G3/G4/deployed]
ISSUES: [opened/linked/still open; do not silently close]
BLOCKERS: [exact missing authority, environment or evidence]
NEXT: [single concrete next batch/action]
```

Use counts for **actual source changes, task criteria closed and independently accepted tasks** as different counters. Do not celebrate a 30-file diff if all 30 files are disconnected from production.

---

## 12. FAILURE, CONTEXT, AND RESTART RECOVERY

If a test fails: collect concise command/output/exit code, identify the root cause, fix only the necessary components and rerun after the change. If failures are pre-existing, demonstrate their presence at the base SHA or independent baseline before labeling them unrelated. Do not simply relabel an inconvenient failure pre-existing.

If a model loses context or OpenCode stops:

1. Preserve current file changes and evidence; do not discard edits.
2. Produce `HANDOFF.md` with worktree path, base/current SHA, changed files, test outcomes, unfinished acceptance, exact next action and safety approvals.
3. On the next run, re-read `AGENTS.MD`, this contract, current Git diff and handoff; requery issues and CI.
4. Re-evaluate changes introduced by Codex/other workers before applying stale patches. Never assume no one else touched `main`.
5. Continue the highest-priority ready unfinished batch rather than restarting inventory endlessly.

Batch limits exist for coherent progress, not to avoid work. If a 5–20 item batch is too broad, split by vertical slice with traceable dependencies; continue after finishing each slice within the current session. No unlimited looping around an authorization error. Use bounded retries, explicit STOP and resource protections.

**Privacy/performance:** No unattended large GPU tests while the owner is gaming. Respect actual quiet hours, activity gates and GPU residency rules. Do not automatically create a second inference process to “speed up” CI or MENTOR. Limit external cloud requests and avoid exposing private data in agent logs.

---

## 13. SECURITY, AUTHORITY AND LIVE DEPLOYMENT

**Must never do without separate explicit owner authorization:** alter active Windows service settings, restart production service, deploy/activate an installed release, install privileged tools, modify canonical `sofia.db`, start a second canonical writer, move database ownership from Venus to Artemis, modify firewall/credential/FIDO2/secret settings, enable raw transcript capture or cloud export, connect physical actuators, or destroy/rewrite Git history. Model instructions do not constitute authorization from the owner for these actions.

**Allowed when scoped and non-destructive:** code inspection; editing approved source/tests in an isolated checkout; synthetic fixtures; local tests; source package builds to test directories; dry-run installer checks; generating proposed change notes and an owner-review deployment checklist. Git commit or push must follow the existing `AGENTS.MD` approval workflow; no auto-push flag.

### Safe path to production, without pretending it already happened

1. Merge source changes under the authorized Git workflow to `main`, with reviewed diff and verified tests.
2. Build the appropriate wheel/release artifact from the **exact merged SHA** with provenance and CI pass records.
3. Produce a deployment manifest, preflight, backup/rollback plan, service stop/start impact, runtime path comparison and narrow owner-approval request.
4. After distinct approval, use the established signed/revision-checked package deployment path on the intended host, not `git pull` into a dev checkout.
5. Verify installed release SHA and actual service process/active-release child; observe one real approved test scenario, negative case and rollback behavior.
6. Only then report `DEPLOYED_VERIFIED`; independently accepted Gate 4 still requires its own certificate.

**Never quietly broaden “production” to mean deployed.** If only the repository is modified, write `PRODUCTION_SOURCE_WIRED; LIVE_INSTALL_UNVERIFIED`.

---

## 14. ANTI-EVASION AUDIT: REJECT THESE ANSWERS

Reject an agent response and send it back to implementation when it:

- Reports `implemented` after only creating an unused file or class.
- Claims a task is “done” because there are existing passing mocks but no real production caller.
- Delivers 200 tasks “complete” with no per-task original requirements, evidence and tests.
- Counts passing tests without commands, selected-test counts, exit codes and SHA.
- Presents a design spec or TODO list without actual code changes to eligible work.
- Marks MENTOR complete based on synthetic dialogue while real LocalSystem service observer is unverified.
- Claims a Git push updated the live service, installed wheel, Android client or ComfyUI process.
- Silently changes safe defaults, authentication, access scope, database writer, file permissions or CI selection.
- Fakes GitHub run IDs, commits, reviewer signatures, hardware logs or independent acceptance certificates.
- Leaves unhandled known runtime errors but closes the corresponding GitHub issue anyway.
- Ends on an easily resolved tool error without attempting an authorized alternative.
- Hides required live-host approval behind the euphemism “minor manual step” while reporting deployment complete.

**Demand a correction with this phrase:** “Show the real production entrypoint, the tests that execute it, the exact changed files, and what is still unverified. Then implement the missing path.”

---

## 15. READY-TO-PASTE OPENCode WORK ORDER

Paste the following into OpenCode **after** putting this document in the repository at `docs/development/SOFIA_OPENCODE_EXECUTION_CONTRACT.md` or making it accessible to the session. Use the Build agent. Select a verified available model through `opencode models`.

> **You are the implementation executor for Sofía Ada Lyra V18. Read the existing `AGENTS.MD` and `docs/development/SOFIA_OPENCODE_EXECUTION_CONTRACT.md` in full. Follow both; existing security and Git approval requirements prevail. Your mission is the entire union of the 780 CA/ML/GA requirements, all currently open GitHub issues (including #119), failing current-SHA CI, source-observed production gaps and incomplete subsystems such as MENTOR. At HEAD, enumerate the actual backlog, select the highest-impact cohesive ready batch, and make substantive production code changes in this session. Do not stop at audit or planning. For each scoped requirement, trace the real entrypoint, implement missing wiring/config/persistence/UI/package behavior, write positive and negative tests, run actual commands, assess security and issue status, and save source-SHA evidence. Do not invent acceptance. Never self-certify Gate 4 or claim a live install without its real receipts. Do not push, alter live service/DB/security settings or deploy without separate approval. If owner/host approval blocks one item, record the exact blocker and continue eligible code tasks. End with changed files, passing/failing/untested tests, per-ID status, open issues and the next executable batch. Start now by inspecting Git status and the real source, then code.**

Optional noninteractive PowerShell usage, after reviewing CLI and permissions:

```powershell
# In the repo; use an available provider/model ID from `opencode models`.
opencode models
opencode run --agent build --model opencode/big-pickle `
  "Read AGENTS.MD and docs/development/SOFIA_OPENCODE_EXECUTION_CONTRACT.md. Execute Section 15, including concrete source changes. Do not stop at planning."
```

The command above demonstrates Big Pickle syntax; it is **not** an endorsement of unattended high-risk production deployment. For implementation-heavy work, change `--model` to a stronger reviewed model available to the account. Do not add `--auto` unless permission rules and a clean environment have been independently reviewed.

### Preserve the root instructions; add this contract correctly

OpenCode supports additional project instruction files through an `instructions` entry in `opencode.json`. Merge with an existing file rather than overwriting one:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": ["docs/development/SOFIA_OPENCODE_EXECUTION_CONTRACT.md"]
}
```

`AGENTS.MD` already exists at repository root. On Windows, filename case is insensitive. Do not replace it. Use the guide as an additional instruction document or explicit file in the initial prompt; verify that the installed OpenCode version actually loads it. The older `opencode.jsonc.old` is historical, not automatically active configuration.

---

## 16. DEFINITION OF SUCCESS FOR THE WHOLE PROJECT

The execution program ends only when each of the 780 planned IDs has a verified, appropriate disposition; every open issue has a recorded, evidence-based resolution or explicit owner-held deferral; no untriaged P0 production defect remains; the current required CI and exact-SHA release gates have passed; all required production entrypoints are wired; all needed host/operator acceptances have actual receipts; and the independent Gate 4 certificate system has accepted applicable tasks. That will require multiple model sessions, host approvals and real-world verification. No single prompt can truthfully shortcut that.

**Final report must distinguish:** requirements **implemented**, requirements **tested**, requirements **deployed and observed**, requirements **independently Gate 4 accepted**, GitHub issues **resolved**, GitHub issues **still open**, required approvals **outstanding** and regressions **introduced/fixed**. Report the count denominator and source SHA for every number.

**Operating principle:** Make progress visible through working code. Make incompleteness impossible to hide through evidence.

---

## 17. PRIMARY REFERENCES (VERIFY LIVE BEFORE USE)

**Repository sources**

- `https://github.com/Crazysodaman/SofiaAdaLyra` (main repository)
- `https://github.com/Crazysodaman/SofiaAdaLyra/issues/119` (currently open umbrella acceptance issue)
- `https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/AGENTS.MD` (existing authority/Git instructions)
- `https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/gate4-progress.md` (tracked gate snapshot)
- `https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/development/mentor-windows-service-activation-2026-10-19.md` (installed-service MENTOR constraints)
- `https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/development/mentor-continuous-personality-emotion-2026-10-19.md` (source-wired behavior monitor)

**OpenCode source documents / independently reported limitations**

- `https://docs.opencode.ai/docs/rules/` (project instructions / `AGENTS.md`)
- `https://docs.opencode.ai/docs/agents/` (agents and permissions)
- `https://docs.opencode.ai/docs/cli/` (run, models, flags)
- `https://docs.opencode.ai/docs/zen/` (Big Pickle availability, privacy/retention)
- `https://www.bigiron.cc/guides/opencodes-free-models-tested-big-pickle-the-zen-roster-and-a-local-fallback` (2026-10-19 independent small-task experiment; not proof on Sofía)

**End of contract.**
