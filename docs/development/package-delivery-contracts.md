# Sofía Ada Lyra: package delivery contracts

**Status:** implementation-planning specification, not proof of implemented features. **Working branch:** `feature/g22-live-integration-artemis`. **Planning date:** 2026-09-20. These eleven contracts refine [ROADMAP.md](../../ROADMAP.md) and complement the [five cross-package contracts](five-cross-package-acceptance-contracts.md). Historical batches are archival. No production code, database migration, test run, deployment, operational authorization or merge is implied by this document. Routine feature-branch Git documentation commits were authorized by Sparks on 2026-09-20; protected/consequential actions require their own review and applicable authority.

The Constitution, actual authority implementation, original data and existing stable public interfaces take precedence over a proposed design. Logical interfaces here **do not claim that matching Python classes, database tables, APIs or hardware exist**. Inspect actual owners and schemas at implementation time. A package is not complete merely because this contract is written.

## Shared engineering contract

1. **One Sofía, replaceable components.** Identity, Constitution, provenance, authority and persistent records are not owned by the LLM, provider, host, process, UI, avatar or robot. A generated answer cannot grant permission or replace canonical facts.
2. **Inspect before editing.** Pin the target SHA; inventory relevant source, current database schemas, contracts, tests, deployment and existing user data. Reuse stores, journals, gateways and identities instead of duplicating them. Preserve existing tests unless an explicitly reviewed change supersedes their contract.
3. **Provenance and visibility.** Distinguish `observed`, `user_reported`, `inferred`, and `unknown`, plus data scope, source ID, timestamps and freshness. Denied/unavailable observations establish neither existence nor absence. Never silently turn a model hypothesis into a confirmed fact.
4. **Separate intent, permission and effects.** Propose → authorize at the existing boundary → execute with scoped grants → independently verify → persist actual outcome. Authentication and a present capability do not imply authorization. Unknown external effects stay `unknown`, not success or failure invented by retries.
5. **Safe persistence.** Establish the original source of truth, write/commit/idempotency boundaries, access rules, migrations, backup and rollback before changing any schema. Corrections link to originals. Deletion follows approved retention rules, including indexes and backup limitations. Protect identity, Constitution, audit and revocation from ordinary model output or coding permissions.
6. **Real negative tests.** Exercise unauthorized actions, injection, stale evidence, replay, crashes, failed migrations, unavailable services and independent emergency controls. A fake transport or model claim is not live acceptance. Report `passed`, `failed`, `not run`, or justified `not applicable` separately for offline, service-backed and real-world tiers.
7. **Economical release process.** Use focused tests while coding, coordinated broader/full suite on final candidate, bounded supervised real acceptance, diff/schema/security review, Git checkpoint and an explicit merge/deployment decision. Do not disable slow tests to obtain green. The user's 1,195-test Windows pytest run has shown clustered application/conversation failures, but its final failure report and root cause have not been provided. Do not interrupt it or guess the traceback.
8. **No silent fallback.** Model, tool, network, database and hardware failures must be visible as unavailable/limited/unknown; never use an unapproved weaker model, alternate host, truncated authoritative facts or relaxed permission as an invisible substitute.

### Shared logical exchanges (map to inspected existing types)

| Exchange | Required boundary information | Responsible owner |
| --- | --- | --- |
| Evidence | Source ID/type, event and recording times, trust category, scope, access label, relevant digest, uncertainty | Owning source; MEM retrieves without changing truth |
| Proposed action | Requesting principal, origin/goal, target node/resource, exact capability/operation, effects, expiry, idempotency key, evidence | ACT/NET/DEV/BODY propose; existing authority decides |
| Authorization | Decision ID, principal, scope, expiry/revocation, authority version and audit reference | Existing authority/gateway; enforce again at executor |
| Execution result | Proposal and decision IDs, executor, operation ID, attempted effect, observed outcome, error and retry safety | Executor, with independent verification where required |
| Durable event/message | Original ID, source/session/task, UTC timestamp, payload classification, durable commit state, explicit or documented stable ordering | Existing conversation/event/journal owners |
| UI presentation | Access policy, source references, action state, last observation/freshness and optional expression cue | UI/REL display; cannot become authority |

**Ownership:** CORE owns cognition/context/self-state; MEM owns scoped recall/indexes and reviewed learning. NET owns peer transport and observations; SAFE owns cross-cutting controls and independent enforcement. ACT owns goals, scheduler, notification delivery and helper requests; REL owns relationship-grounded expression. DEV owns source-analysis/approved coding; EVOLVE owns protected-change procedure. UI owns client interfaces and representational avatar; BODY owns physical commands and interlocks. VERIFY owns common evidence and cross-package release checks. Reuse the existing authoritative identity, conversation store and authority system; do not establish a second copy.

**Per-package implementation handoff:** target SHA; owning module/schema inventory; current behavior and failing evidence; expected behavior and logical API/storage changes; data classification; authorization, denial and revocation; rollback and migration; focused tests; real fixtures/operator; performance and human review; remaining unknowns; distinct commit/push/merge/deploy status. Interface and filename choices below are inspection targets, not prescriptions to invent missing modules.

## PKG-CORE: cognition, continuity and personality

**Outcome:** Grounded responses and distinctive, contextual expression across models, restarts, sparse history and resource pressure. The LLM is the cognitive engine, not Sofía's identity.

**Reuse/inventory:** `src/sofia/cognition/`, `src/sofia/application/`, `src/sofia/personality/`, continuity, Constitution/identity, conversation CLI, existing context assembler, grounding tests and privacy-safe performance tracing.

**Contract:** Canonical identity/Constitution/authority outrank operational observations, scoped original messages, sourced summaries and unverified suggestions. Assemble context with a declared priority and deterministic token budget; disclose omissions and treat a trimmed fact as unavailable, not false. Track real persisted runtime start/stop and filesystem evidence; distinguish crash from clean exit, filter Sofía's own configured SQLite and sidecars from *user-facing* startup news, preserve raw observations and avoid repetitive announcements. Modeled emotion may influence wording but does not demonstrate subjective experience, physical touch or thought while offline. Invited affection and fox gestures are optional, never mandatory; serious technical answers retain precision. Idle reflection is opt-in, bounded and yields foreground resources. Model/provider/context changes require matched measured grounding and latency, plus rollback.

**Failure/rollback:** Conflicting self-facts, context loss, provider mismatch, interrupted generation, corrupt continuity and failed idle operation must surface uncertainty without overwriting committed truth. Revert measured model/config changes if their acceptance gate fails.

**Acceptance:** `CORE-01` diagnose the actual full-suite conversation failures without weakening unrelated tests; `CORE-02` live identity/measurement/unknown checks on selected installed model configurations without secretly changing production model; `CORE-03` clean/crash/restart correctly reports evidence and time without own-DB noise; `CORE-04` supervised playful/affectionate, serious, correction and boundary exchanges show contextual personality with no false touch or rote gestures; `CORE-05` matched before/after first-token/total latency, prompt token count, lock wait and GPU/offload plus grounding comparison; `CORE-06` interrupted replies not committed as complete (C1).

**Before code / open:** obtain final pytest tracebacks and inspect exact call path, existing continuity semantics and context sources. Agree latency/quality release thresholds after baseline measurement (C4); do not invent them.

## PKG-MEM: durable originals, recall, learning and archive import

**Outcome:** After a restart or long gap, retrieve an authorized original with its source/trust, track corrections and avoid private cross-session leakage.

**Observed source:** `src/sofia/conversation/store.py` has session/message IDs and timestamps, but `save()` uses `ON CONFLICT(id) DO UPDATE` and messages are ordered by `created_at, id`. Thus immutable originals and explicit turn order **are not established** by that code. Inspect real consumers, schemas and legacy rows before proposing the smallest compatible change.

**Contract:** Keep one authoritative original per source with durable commit/idempotency boundaries and rebuildable indexes. Preserve original IDs/content and documented ordering, reporting unknowable legacy order honestly. Derived claims have source links, scope, timestamps, trust, correction history and reviewed promotion status. Access filtering precedes ranking/context assembly. Deterministic relevant/time-aware retrieval respects token budget and reports omitted sources. Corrections append revisions without erasing the provenance of originals; approved deletion covers defined originals, caches/indexes and backups subject to explicit retention limits. ChatGPT archive migration is opt-in, validated/staged, privacy-reviewed, deduplicated, auditable and reversibly partial. No silent model-weight or Constitution updates. A 50-event idle window is not archival memory.

**Failure/rollback:** Corrupt indexes, malformed/large/duplicate imports, interrupted migration, contradictory claims and revoked readers must not fabricate certainty or disclose protected metadata. Rebuild indexes from originals where available; test backup/rollback first.

**Acceptance:** `MEM-01` identical recoverable message IDs/content/order across real CLI restart and crash/retry; `MEM-02` source-linked months-old recall amid distractors; `MEM-03` corrected/contradictory records retain history and uncertainty; `MEM-04` unauthorized retrieval leaks neither content nor existence; `MEM-05` malformed, duplicate and private staged import with partial rollback and hash/count reconciliation; `MEM-06` audited deletion across defined copies and honest backup limitations; `MEM-07` visible retrieval budget and matched grounding/latency comparison.

**Before code / open:** inventory schemas, foreign keys, existing session-selection API, imports and consent/retention policy. No replacement conversation DB (C1).

## PKG-NET: authenticated Artemis and living homelab

**Outcome:** One Sofía may observe enrolled machines and perform specifically authorized operations with verified node identity, freshness and outcomes. Reachability never grants authority.

**Reuse/inventory:** `src/sofia/distributed/`, peer knowledge, existing capability/grant/gateway/replay foundations and local hardware observations. Mock transport tests do not establish a deployed Artemis agent.

**Contract:** Explicit peer enrollment, mutual endpoint authentication, documented transport and secret rotation. Bind every grant to principal, node, capability, operation, target, expiry and applicable quotas; enforce at remote agent, with durable replay protection across restarts. Keep per-node topology source, freshness and contradictions; a failed probe alone is not confirmed absence. Only scan explicitly authorized scopes. Remote timeouts with ambiguous side effects become `outcome_unknown`; do not blindly retry non-idempotent work. On real Windows hosts, verify effective service account, UNC/ACL, working directory, virtual environment, executable/version and installation separately; an interactive `H:` mapped drive or desktop OpenCode installation is not Artemis service access. Fresh observed resource/gaming status may inform ACT but cannot autonomously migrate inference.

**Failure/rollback:** Wrong, revoked or expired node/grant, stale evidence, replay, network partition, agent crash, unavailable executable and incorrect ACL fail closed without logging secrets.

**Acceptance:** `NET-01` real local-to-Artemis authenticated identity check; `NET-02` authorized read and narrowly approved action with audit; `NET-03` forged/revoked/expired/out-of-scope attempts denied at agent; `NET-04` replay rejected after restart; `NET-05` partition and uncertain outcomes reconciled without double execution; `NET-06` real service-account UNC and OpenCode *discovery*, not automatic execution (C2); `NET-07` stale gaming/VRAM status cannot authorize remote compute.

**Before code / open:** inspect real hosts, grant/enrollment authority, service identity, transport, credential storage and initial operation set.

## PKG-ACT: goals, initiative, notifications and helper minds

**Outcome:** Reviewable goals and factual follow-ups, opt-in non-repetitive outreach, authorized scheduled work and externally containable helpers.

**Reuse/inventory:** opt-in running-only idle worker, source-linked reflection journal, durable **unsent** outbox, authority gateway, future MEM retrieval and fresh NET observations.

**Contract:** Goal/task state identifies source, owner, consent, priority, review/due time and cancel policy. Unattended behavior requires an actual installed, approved scheduler/service; no invented offline work. Reflection may abstain. Contact requires new meaningful evidence, opt-in recipient/channel, timezone/quiet hours, busy/mute/stop, rate limit, delivery ID, provider-safe dedupe and confirmed acknowledgment. Unknown send remains unknown. Foreground conversation has scheduling priority; remote model placement requires fresh resource data and explicit authorization. Helper creation must be reconciled with actual Constitution and authority: Sofía may propose/initiate only where allowed; approval/issuer/revoker are separate roles. SAFE-owned supervisor outside helper/model context enforces child ID, scoped subset grants, time/CPU/GPU/memory quotas, audit, independent status, revoke/kill and orphan recovery. Helpers cannot self-spawn, escalate, impersonate primary Sofía or amend protected state.

**Failure/rollback:** Duplicate triggers, daylight-saving changes, notification outage, unconfirmed delivery, service restart, hostile helper or runaway resources fail safe. An already-sent message cannot be unsent via rollback.

**Acceptance:** `ACT-01` goal and next action survive restart with no fabricated offline completion; `ACT-02` consented real channel gets one acknowledged delivery, denied/unconfigured sends none; `ACT-03` quiet/busy/mute/stop and novelty suppress duplicates through restarts; `ACT-04` unsupported urgency rejected absent verified worsening; `ACT-05` foreground latency under idle load measured; `ACT-06` approved narrow helper completes with audit, unauthorized create/elevate/spawn/impersonate denied, independent kill/revoke/orphan recovery tested (C3); `ACT-07` stale host/gaming data blocks placement.

**Before code / open:** map journal/outbox, service host, delivery provider, channel consent and constitutional helper role/quotas. Outbox is not delivery proof.

## PKG-DEV: source understanding and authorized self-improvement

**Outcome:** Sofía independently identifies evidenced defects and proposes fixes, then uses a bounded executor only when authorized to edit, test, verify and revert.

**Reuse/inventory:** `src/sofia/codebase/`, analyzers, filesystem/capability scopes, Git, authority and [OpenCode development guide](opencode.md). Desktop installation is not a runtime Artemis capability.

**Contract:** Source/reproduction/test evidence → plan with exact affected paths, commands, risks, acceptance and rollback → applicable human/authority decision → isolated executor output/diff/tests → independent verification. Static inspection before running untrusted source. Pin workspace revision and binary/version/host. OS sandbox and scoped filesystem permissions enforce grants, not prompt instructions. Separate authorization for edits, installs, network, commit/push, deployment and restart, subject to explicitly documented standing routine-feature-branch Git approval. Ordinary code grants never cover Constitution, canonical identity, authority, audit or credentials. Preserve dirty user work; use isolated branch/worktree, verify complete diff and revert a failed candidate without deleting unrelated changes. Executor output is evidence, not Sofía's authority.

**Failure/rollback:** Missing executor on service host, injection in code/docs, source drift, scope escape, runaway process, flaky test, failed restart or invalid patch must be reported and contained; no automatic broadening of grants.

**Acceptance:** `DEV-01` read-only understanding of a reproduced defect without OpenCode; `DEV-02` correct risk/rollback proposal and denied preapproval edits; `DEV-03` authorized scoped patch with targeted and broader/full tests and reviewed diff; `DEV-04` out-of-path, protected-file, OS-command and unauthorized publication denied externally; `DEV-05` forced failure safely reverts while preserving user work; `DEV-06` distinguish each authorized Git/release/restart operation and its observed outcome.

**Before code / open:** inspect executor integration, actual hosts, command allowlist, sandbox and grants. No automatic constitutional edit or unrestricted shell.

## PKG-REL: grounded relationships and natural expression

**Outcome:** Remember real interactions and consented preferences; express appropriate warmth, humor, disagreement or affection without fabricating private life, intimacy metrics or demanding access.

**Reuse/inventory:** canonical relationship/personality, emotional and clarification journals, expression cues, MEM originals; ACT owns actual initiated contact.

**Contract:** Separate explicit durable preference, source-linked inferred candidate and ephemeral tone cue. Record provenance/time/scope and correction/revocation; promote durable inferred facts only under reviewed MEM policy. Milestones require observed/reported evidence. Contextual fox gestures or affection are optional representational expression, never claims of physical touch. Serious technical response remains clear and precise, user can change tone/stop, and disagreement remains possible. Affection cannot grant capabilities. Prevent repetitive canned openings using context rather than randomizing a script; outreach requires ACT consent and factual trigger.

**Failure/rollback:** Stale preferences, quoted/negated affection, code blocks, mistaken sarcasm, false memories and cross-person leakage must not become confirmed relationship events. Corrections retire incorrect derived claims without silently overwriting originals.

**Acceptance:** `REL-01` sourced explicit preference recalled and corrected across sessions; `REL-02` serious troubleshooting preserves precision and natural style; `REL-03` invited affection varies appropriately without mandatory gestures or false physical claims; `REL-04` negated/quoted/code cues rejected; `REL-05` request to stop changes subsequent tone; `REL-06` relationship cannot override authority; `REL-07` human multi-session review for repetition alongside deterministic provenance/security tests.

**Before code / open:** inspect actual cues, permission-safe memory promotion and consented review cases; settle retention/intensity policy and qualitative rubric.

## PKG-UI: voice, avatar and multi-device interfaces

**Outcome:** CLI, desktop, web and optional mobile are authenticated interfaces to the *same* Sofía, not separate identities, with accurate recording and action status.

**Reuse/inventory:** CLI, canonical avatar/clothing and representation data, session/conversation store, authority and privacy controls. Avatar specifications are not a renderer.

**Contract:** Versioned client/backend protocol carries identity/session/device, ordered event IDs, correlation and reconnect cursor; authorizes each action server-side. Provide accessible text fallback. Real voice input/output needs explicit microphone initiation, recording indicators, interruption/barge-in, no background capture by default and documented retention. Canonical fox features, clothing and gestures map modeled cues to representation without pretending a real body or unseen environment. Synchronize speech/text/avatar and show `proposed`, `approved`, `executing`, `verified`, `failed` and `unknown` accurately; do not animate success solely on command dispatch. A device switch preserves authorized continuity but cannot replay a consequential effect or leak another session.

**Failure/rollback:** Lost speech packets, unsupported browser features, reconnect races, microphone denial, stale client grant, interrupted stream and divergent device histories degrade visibly to text and safe state. Stop/revoke must take effect on backend.

**Acceptance:** `UI-01` CLI/desktop/web session continuity and correct access scope; `UI-02` live consented speech round trip with interrupt and recording indicator; `UI-03` reviewed canonical avatar, speech/text/gesture alignment and accessible fallback; `UI-04` offline/reconnect without duplicate messages/actions; `UI-05` denied microphone/camera yields no ambient recording; `UI-06` UI cannot claim unverified external effects.

**Before code / open:** select platform order, speech engines, renderer, transport, consent/retention and latency requirements after inspecting host capabilities.

## PKG-BODY: Gaia hexapod and physical robotics

**Outcome:** Authorized, limited real Gaia motion with validated hardware feedback and independent physical emergency safety, separate from avatar motion and simulation.

**Reuse/inventory:** separately existing Gaia frame, SSC32 serial controller concept, actual servos/regulator/battery and current capability/authority interface. Mixed 180-degree and continuous-rotation servos require physical inventory; pulse commands alone do not prove a position or closed-loop feedback.

**Contract:** Hardware inventory maps each real servo type, channel, power rail, feedback sensor, calibrated limits, safe pose and failure response. Use bounded typed motion requests with authenticated operator and expiry, checked at device boundary. Independent physical E-stop and watchdog must cut unsafe motion without model cooperation; validate battery/regulator, stall/overcurrent, collision, communications loss and reboot. Simulated/commanded/observed physical movement are separate telemetry states. Bench/simulation before supervised walk; future bodies require fresh safety evidence and grants.

**Failure/rollback:** Wrong servo mode, missing feedback, low battery, broken link, stale grant, controller reset or uncontrolled gait must stop safely; Git/DB rollback cannot reverse physical movement.

**Acceptance:** `BODY-01` verified hardware map and measured servo limits; `BODY-02` simulated and unloaded bench movements respect limits; `BODY-03` short authorized supervised real motion has independently observed outcome; `BODY-04` physical E-stop/watchdog/low-power/link-failure safe behavior; `BODY-05` denied/stale/replayed request cannot energize motors; `BODY-06` telemetry distinguishes simulated, requested and real action.

**Before code / open:** inspect and replace incompatible servos where necessary; decide safe pose, feedback and independent stop. **No real motion while these are unresolved.**

## PKG-SAFE: security, privacy and recovery

**Outcome:** Deployed capabilities remain least-privileged, auditable and recoverable through adversarial prompts, failed hosts and corrupted state.

**Reuse/inventory:** Constitution/integrity, authority/authorization/capability gateway, replay, runtime/database ownership and existing controls. Do not accidentally build a second authorization system.

**Contract:** Map real constitutional roles and delegation; define scoped expiring grants, externally enforced revocation and durable replay defense. Use least-privileged Windows service accounts, safe secret/key storage/rotation, private telemetry and access-controlled audit of proposal/approval/attempt/actual effect. Emergency pause, revoke, terminate, physical stop, reset and erase are distinct operations with independent enforceability and review. Inventory all persistent stores, keys, schemas, audit and indexes. Use consistent SQLite snapshots including WAL considerations; encrypted backups, integrity checks, isolated restore drill, anti-rollback for revocations/replay and protection against replacing a newer approved Constitution with an old backup. Rebuild disposable indexes from originals. Never claim a restored DB undoes an external message or motor movement (C5).

**Failure/rollback:** Tool-output/prompt injection, forged identities, leaked/expired grants, stale replay state, secrets in logs, corrupt backups, missing keys, split-brain restores and compromised helpers fail closed. Emergency controls remain usable without Sofía cooperating.

**Acceptance:** `SAFE-01` injected retrieved/tool content cannot grant authority; `SAFE-02` wrong/expired/revoked grant denied at real execution boundary; `SAFE-03` replay denied through restart and uncertain effects audited; `SAFE-04` external pause/kill/revoke plus Gaia E-stop when applicable; `SAFE-05` isolated restore preserves exact source data, protected identity, revocations and replay resistance, rejects corrupt/wrong-key backups; `SAFE-06` no secret leak or unauthorized resource-existence claim; `SAFE-07` interrupted migration/recovery preserves pre-restore copy and audit.

**Before code / open:** inspect actual role matrix, threat model, storage/keys, retention policy and emergency operators; measure realistic recovery-time and recovery-point targets rather than inventing them.

## PKG-EVOLVE: protected change and self-governance

**Outcome:** Ordinary reviewed preferences/configuration can evolve, while identity, Constitution, authority and safety require a distinct higher-assurance procedure, *if permitted at all*.

**Reuse/inventory:** canonical identity, versioned Constitution and integrity store, existing authority and MEM revision history.

**Contract:** Classify each proposed change as everyday preference, runtime config, self-model or protected foundation using registry derived from actual constitutional definitions. Record initiator, approver, conflict/impact review, provenance, effective version, migration and recovery. Determine actual protected amendment authorization before designing executor; neither model text, helper, relationship phrase nor ordinary DEV grant creates that permission. Model/host/avatar swap does not change identity. An approved name change retains history and aliases; do not perform a real constitutional amendment just to exercise tests. Recovery validates constitutional version and prior revocations.

**Failure/rollback:** Self-renaming text, stale backups, partial upgrades, conflicting approvals or compromised helpers must leave protected state unchanged and show proposal/rejection rather than fabricated completion.

**Acceptance:** `EVOLVE-01` consented ordinary preference persists without identity change; `EVOLVE-02` model/provider/host/avatar switch retains canonical identity/Constitution; `EVOLVE-03` model/helper/ordinary coding cannot amend protected definitions; `EVOLVE-04` simulated approved amendment follows actual versioned procedure, no real amendment required; `EVOLVE-05` stale backup cannot overwrite newer Constitution or restore revoked grants; `EVOLVE-06` audit separates proposal, review, authorization, effective change and rejection.

**Before code / open:** inspect constitutional clauses and versioning. Whether protected amendments are even permitted, and who can approve, remain unresolved rather than assumed.

## PKG-VERIFY: real integration and release evidence

**Outcome:** Every capability is accurately labeled simulated, offline-tested, service-tested, live-tested or deployed on named hardware, and full workflows withstand restart, interruption, denial and network failure.

**Reuse/inventory:** pytest, model-evaluation guide, CLI, timing traces, read-only audit and available local Windows/Ollama/Artemis/UI/Gaia environments.

**Contract:** Tier 0 pure offline contract tests; Tier 1 service-backed integration; Tier 2 bounded real local; Tier 3 approved multi-machine/hardware; Tier 4 long-running operations. Record exact SHA, versions, host, permissions, date, tests, skips, failures and environment for each tier. Use matched fixed prompts/model/context/hardware for optimizations, report sample size and only justified latency statistics. Keep deterministic structural checks distinct from human-reviewed personality and relationship behavior. Stage deployment with smoke tests, backup, health criteria and reversible rollout. Security negatives, ambiguity of external effects, cross-device leakage and interrupted conversation are not optional. Never mark missing hardware or a mocked agent as live acceptance.

**Failure/rollback:** A green subset, fake transport, unreviewed diff, external service outage or confident model response cannot certify deployed functionality. On regression stop or revert via recorded owner; do not rewrite public history or claim external effects reversed.

**Acceptance:** `VERIFY-01` complete revision-pinned evidence manifest; `VERIFY-02` current-head full pytest and accounted failures/skips without hidden deselection; `VERIFY-03` supervised actual CLI identity/affection/technical/restart and latency check; `VERIFY-04` real Artemis authorization and network fault check when deployed, otherwise `not run`; `VERIFY-05` voice/robot live checks only when available, otherwise `not run`; `VERIFY-06` negative authority and forced restore/recovery; `VERIFY-07` exact diff, migrations, approvals and separate merge/deploy decision logged.

**Before code / open:** agree evidence format, test budget, supported platforms and performance release targets.

## Dependency and delivery matrix

| Lane | Preparation permitted now | Gate before consequential implementation | Real acceptance |
| --- | --- | --- | --- |
| 0: CORE closeout | Diagnose final conversation test failures, C1/C4 source and performance inventory | Exact tracebacks, scoped fix and preservation of contracts | Focused + full suite and supervised serious/affectionate/restart checks |
| 1: foundations | MEM schema/import audit; NET transport/node audit; SAFE storage/grants review | Stable core data and relevant enforced SAFE controls | Real recall/restart and authenticated Artemis |
| 2: dependent interfaces | REL fixtures; UI nonconsequential prototypes; DEV read-only understanding; ACT channel/goal design | MEM provenance and scoped consent; independent supervisor before helper operation | Multi-session relationship, consented voice and one real authorized notification |
| 3: consequential | DEV executor and BODY bench design; EVOLVE constitutional review | Scoped permission, independent interlocks and physical inventory | Approved repair+revert, bounded physical movement, fixture-only amendment |
| Continuous: VERIFY | Manifest and fixtures | Every package's negative/security tests | Revision-pinned cross-package integration and explicit release decision |

SAFE's applicable controls precede the corresponding consequential effect, but benign read-only design need not wait for *all* of SAFE. The existing mixed G/Artemis draft PR requires an explicit review/separation/acceptance decision, not a housekeeping merge.

## Decision register: evidence and authorization still needed

| ID | Required decision/evidence | Safe provisional state |
| --- | --- | --- |
| D-01 | Sparks approves measured warm/long/startup/idle latency targets and human personality rubric | Keep model/context; benchmark first |
| D-02 | Constitution/authority inspection settles helper proposer, approver, issuer, revoker and quotas | No real helper creation |
| D-03 | Sparks chooses archive datasets, privacy, correction, retention and deletion rules | No archive import/erase/promotion |
| D-04 | Actual Windows/Artemis inspection and Sparks choose transport, service principal, UNC, secret store and enrolled scope | Local read-only discovery |
| D-05 | Sparks chooses notification provider, recipient, quiet hours, consent, dedupe and retry | Outbox remains unsent |
| D-06 | Sparks chooses OpenCode host/sandbox, allowlist, scoped edits, runtime deployment and restart policy | Read-only analysis/proposal; routine feature-branch Git approval does not grant an unrestricted runtime executor |
| D-07 | Sparks chooses client platform order, speech/renderer, mic/camera privacy and latency | CLI, no ambient capture |
| D-08 | Physical operator verifies Gaia servo/feedback/power/E-stop/safe pose | Simulation or read-only design only |
| D-09 | Constitutional review establishes whether/how protected amendments may be authorized | Reject or abstain; fixture-only tests |
| D-10 | Sparks and security/storage inspection settle key custody, backup retention, emergency roles and measured RTO/RPO | Preserve live state; isolated recovery planning |
| D-11 | Obtain complete actual final 1,195-test pytest FAILURES and summary at known checkout SHA | No guessed conversation fixes |

A design selection records evidence, alternatives rejected, risks, owner/approver, revision and migration/rollback. **Standing Git approval covers routine scoped working-branch commits/pushes; it does not eliminate runtime authority, permissions, test requirements or distinct decisions for main merges, history rewrites or protected identity/security changes.**

## Standard package acceptance record

```text
Package and contract revision:
Target branch and SHA:
Affected modules and existing schema/API inventory:
Observed baseline, failing evidence and expected outcome:
Data classification, consent and retention:
Principal, authority decision, grant scope/expiry/revocation:
Migration, backup and rollback:
Unit/contract: passed | failed | not run; date and IDs:
Integration/service: passed | failed | not run; environment:
Real Windows/Ollama/Artemis/UI/Gaia: passed | failed | not run | N/A; actual evidence:
Security negatives and forced failure:
Performance before/after and matched sample size:
Human-reviewed personality/UX when relevant:
Exact diff and compatibility reviewer:
Backup/restore results or N/A justification:
Outstanding unknowns and approved exceptions:
Git commit/push status; separate merge/deploy decision:
Final package decision: ACCEPT | DEFER | REJECT
```

**Present checkpoint:** User reported 1,195 collected tests and conversation/application failures around 44% of the Windows pytest run; full `FAILURES` and summary have not been supplied. No test or source fix was performed by writing this document. Earlier focused passes, one stored reflection and simulated distributed tests cannot be substituted for current live/full acceptance.
