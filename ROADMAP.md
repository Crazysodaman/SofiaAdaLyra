# Sofía Ada Lyra: package delivery roadmap

**Proposed comprehensive re-baseline:** 2026-09-20. **Working branch:** `feature/g22-live-integration-artemis`; [draft PR #1](https://github.com/Crazysodaman/SofiaAdaLyra/pull/1) remains unmerged. `main` has not received this revision. **This document replaces the old batch planning method.** Historical letters and numbers are retained only in the [legacy batch index](docs/development/legacy-batch-index.md), existing handoffs and Git history, not used to schedule or declare new work.

**Scope of this audit:** available Sofía project conversation history, retrieved handoffs and the accessible repository documents. This is a consolidated set of requirements, **not a claim that every past chat message was accessible or that every proposed feature is approved for implementation**. Unrecovered details are explicitly open. The roadmap is a plan, not implementation evidence. Do not treat its package IDs as version numbers or automatic authorization.

> **Non-negotiable invariant:** Sofía's persistent identity, Constitution, canonical representational embodiment, memory, authority, operational evidence and capabilities are distinct from her replaceable LLM/provider, computer, process, voice, avatar and robot. Capability is not authority; authentication is not authorization; observed, inferred and unknown remain distinct. Personality, memory and model output cannot independently grant permission or rewrite protected facts.

## Package dashboard

Each package owns an outcome, not a series of tiny code drops. A foundation listed below is **not** proof that the full package works. Package IDs are stable workgroup identifiers; no more new numbered or lettered batches.

| Package | End-to-end outcome | Current evidence-based position | Important dependency |
| --- | --- | --- | --- |
| **PKG-CORE · Cognition and continuity** | Dependable grounded Sofía, coherent identity/personality across restarts and models, measured responsiveness | Foundational code exists; current personality/reflection closeout has an unfinished full suite with failures reported; live semantics and inference performance open | Existing constitution/identity/runtime/authority contracts |
| **PKG-MEM · Memory and learning** | Durable originals, provenance, selective recall, corrections and reviewed learning | Prior memory and conversation stores plus emotional/reflection journals exist; comprehensive recall/import not delivered | Stable core data contracts |
| **PKG-NET · Distributed homelab** | Authenticated, scoped multi-machine observation and operations | Peer/gateway/grant/replay foundations exist; deployed Artemis transport/agent and real two-machine acceptance missing | Per-node auth, durable safety, authorized scopes |
| **PKG-ACT · Goals and initiative** | Evidence-based goals, useful follow-ups, controlled work and notifications | Opt-in running-only idle reflection and an **unsent** outbox exist; actual delivery, independent project follow-up and continuous service not established | Memory and appropriate authority; NET for remote activity |
| **PKG-DEV · Self-improvement and engineering** | Sofía can inspect, diagnose, propose and, when authorized, improve her own code through a bounded executor | Code understanding/tools and installed local OpenCode CLI are foundations; autonomous edits and trusted OpenCode capability integration are not proven | Core, memory, authorization and isolated execution |
| **PKG-REL · Relationships and social continuity** | Grounded preferences, relationship history and expressive, non-repetitive conversations | Canonical relationship/personality and modeled emotion cues exist; sustained live social behavior and reviewed preference learning open | Core + memory; ACT for initiated contact |
| **PKG-UI · Voice, avatar and interfaces** | One Sofía across desktop, phone, web, real-time voice and expressive avatar | Canonical avatar/clothing data and CLI exist; no accepted full voice/visual/mobile experience | Core; memory/session continuity; interface privacy |
| **PKG-BODY · Robotics and embodiment** | Safe, authorized Gaia hexapod interaction and optional future physical forms | Gaia hardware/project concept exists separately; no verified Sofía-to-robot capability | NET/authority, device abstraction and physical safety |
| **PKG-SAFE · Security and recovery** | Verified secrets, audit, backup, isolation, failure recovery and emergency controls | Constitutional/authority/integrity boundaries and some replay foundations exist; full deployed assurance not established | Cross-cutting: must precede every consequential capability |
| **PKG-EVOLVE · Governance and controlled evolution** | Versioned, reviewable changes to preferences, self-model and, by protected procedure only, fundamental identity/Constitution | Identity/integrity foundations exist; no permission for silent self-redefinition | SAFE, MEM, DEV and explicit constitutional procedure |
| **PKG-VERIFY · Integration and operations** | Measured, maintainable end-to-end system on real local and Artemis equipment | Current CLI and tests exist; whole-system, long-term and multi-interface acceptance outstanding | Integrates every applicable package; tests run throughout |

**Coverage check:** no capability in the project history is relegated to an unnamed “later” bucket: model evaluation/latency (CORE/VERIFY), self-awareness/reboot scans (CORE/SAFE), long-term recall and ChatGPT archive (MEM), living homelab topology and gaming-aware compute (NET/ACT), goals, idle thought and notifications (ACT), OpenCode/self-repair (DEV), relationships/preferences/emotions (REL), real-time voice/avatar/mobile (UI), Gaia (BODY), derived subordinate minds (ACT/SAFE), emergency authority/recovery (SAFE) and controlled name/identity evolution (EVOLVE).

## How we work: whole-package delivery, economical verification

1. **Audit the existing architecture once per package.** Map present source, schemas, test contracts, permissions, data owners and genuine blockers. Reuse prior implementation. Do not build a second journal, authorization layer or memory store just because the project switched planning formats.
2. **Define one package contract and bounded acceptance scenario.** Name prerequisites, owned changes, excluded behavior, security negatives, required user approval, migration/rollback plan and observable live success. For large packages, write the entire coherent plan before implementation but keep internally reviewable commits and separable failure domains.
3. **Build cohesive changes with focused internal checks.** Independent package lanes can advance at the same time when interfaces and ownership are stable. A dependent capability cannot use an unverified security control; do not combine unrelated source modifications just to reduce the number of checkpoints.
4. **Ask Sparks for meaningful checkpoints, not a new pull and pytest run for every file.** Use focused component/integration tests during development, then one coordinated package validation request, broader/full suite before acceptance and required bounded real Ollama/Windows/Artemis/robot tests. The assistant must not claim tests ran on Sparks's PC without output. Do not rerun the entire slow suite to diagnose a single failure, or quietly disable slow research tests to obtain green.
5. **Release only what was verified.** Review the exact diff and migration, use package-scoped branches/PRs when work can be isolated, log known limitations, obtain human approval for consequential execution/merge and record the observed result. Draft mixed-scope PR #1 needs review and either independent acceptance of both scopes or an explicitly authorized separation; no housekeeping merge of unfinished remote operations.

**Evidence record for each package:** target commit and scope; source and contract inspected; focused/broader/full tests with dates and results; real-world checks separately marked **passed / failed / not run**; measured before/after performance if optimizing; risk, permission, data migration and recovery; remaining unknowns; reviewed diff, decision and merge status. A mock transport or persuasive model reply is never a live acceptance result.

## Delivery lanes and dependencies

**Lane 0, now:** close CORE's existing personality/reflection candidate. Wait for the currently running full pytest report and its actual failures. Diagnose and repair on the current feature branch, then focused reruns, a fresh full suite, brief supervised startup/affection/serious conversation, diff review and an explicit acceptance decision. Documentation changes made after the test began are not part of that run. No new operational capability is considered completed because this roadmap was rewritten.

**Lane 1, independently parallel when contracts permit:** MEM (preserve/retrieve existing history) and NET (cryptographic Artemis connection). SAFE supplies the required authorization, secrets, audit and failure controls *before* remote action. CORE's measured model problems can be evaluated in a bounded parallel diagnostic without silently changing the production context/model.

**Lane 2, once individual prerequisites are proven:** REL's long-horizon preferences/relationship continuity, UI's non-consequential interface prototypes, and DEV's read-only understanding/planning may progress alongside MEM. ACT's real notifications require durable state, user policy and an authorized delivery channel; remote compute placement requires NET and measured resource/game activity. Derived helper minds require SAFE's external supervisor before creation.

**Lane 3:** DEV's authorized code modification and BODY's actual robot motion require their specialized safety gates. EVOLVE has protected constitutional review, never an automatic output of DEV. VERIFY runs inside each lane and culminates in real cross-package acceptance, not a final dumping ground for postponed security.

The roadmap is dependency-aware, **not** a promise that all eleven packages can be implemented and verified in one undifferentiated patch. Each package can be delivered as a coherent body of work with fewer user interruptions.

## PKG-CORE · Grounded cognition, self-awareness and personality

**Reuse:** Constitution and integrity verification; persistent identity/self-state; operational and filesystem observation; cognitive context assembler; provider abstraction; personality and canonical embodiment; conversation CLI; current emotional/reflection journal, idle worker and safe latency trace.

**Deliver:** resolve current test failures without weakening contracts; demonstrate correct canonical self-facts and uncertainty under model replacement, conflicting history and sparse context; keep personality expressive and context-sensitive without mandated fox gestures, generic praise or false bodily sensations; retain an actual evidenced previous-runtime timeline, grouped file/config/capability changes, acknowledgment and non-repetitive startup messages, with Sofía's own SQLite activity excluded from workspace news. Verify clean/unexpected shutdown and only report downtime from persisted timestamps. Add explicit test-time and live-time budgets, model/offload comparisons with fixed prompts and provenance-aware prompt budgeting in coordination with MEM; do not shorten constitution/grounding without versioned human review.

**Current facts, not a performance fix:** user verified 55 and then 30 targeted tests; read-only audit found one completed idle attempt and one matching persisted model thought, zero pending unsent messages. Live trace showed 0.0 ms conversation lock wait, about 16k–18k prompt tokens, 20k configured context and 12.8–88.2 seconds of generation for observed replies; prior GPU sample showed mixed CPU/GPU placement with nearly full 12 GB VRAM. The full suite is still running with failures visible but no final failure report available. Do not infer that the worker caused slow replies, or that 20k context was faithfully used. See [`batch-g-emotional-continuity.md`](docs/development/batch-g-emotional-continuity.md) and [`model-evaluation.md`](docs/development/model-evaluation.md).

**Accept when:** final full-suite and focused regressions pass or explicitly documented exceptions receive a separate decision; a short real full-runtime identity/uncertainty/personality/restart check is reviewed; a model-performance change, if any, has matched before/after measurements and grounding comparison. A single idle thought does not prove independent ongoing consciousness or thought during shutdown.

## PKG-MEM · Durable memory, provenance and learning

**Reuse:** existing memory and conversation systems, emotional events, revisions, clarification records, reflection thoughts and retrospective summaries. Inventory actual schemas before changing them. Preserve authoritative identity/Constitution separately from recalled content.

**Deliver:** immutable or otherwise reliably preserved source messages/records and timestamps; provenance (`observed`, `user_reported`, `inferred`, `unknown`) and source-linked derived claims; conflict/revision history, retention and user-initiated correction/forgetting controls with explicit effects on originals and indexes; permission-scoped retrieval by relevance/time/person/project; deterministic context priorities, token budget and visible omissions/truncation; reviewed promotion/edit/reject of candidate durable preferences/facts without letting the LLM silently canonize guesses; user-controlled ChatGPT archive ingestion with format validation, dedupe, traceable summaries, staged approval and reversible partial import; backup/migration and rebuildable indexes. Learning from feedback means revised evidence-linked behavior, **not** unreviewed model-weight or constitution mutation.

**Accept when:** a question after a restart retrieves the correct supporting original and its trust status, resolves contradictory/corrected records without rewriting history, identifies unknowns, and handles malformed/duplicate/private imports safely. Compare live grounding and latency at fixed context/model before changing limits. G's 50-event/366-day idle window is not long-term memory; an outbox item is not a promoted fact.

## PKG-NET · Distributed Sofía and the homelab

**Reuse:** existing node identities, known-peer and reachability evidence, capability inventory, grant/gateway and replay foundations; local machine/environment/external integration capabilities. A known machine is not a second Sofía identity, and connectivity never conveys authority.

**Deliver:** enrolled peer identity and authenticated transport/agent on Artemis, verified endpoint identity, scoped node+capability+operation+expiry grants, revocation, durable replay protection and audit, bounded remote operations and uncertainty-safe retry rules; living topology of *authorized* homelab nodes, freshness/contradictions, meaningfully unexpected devices/changes and offline alerts that distinguish one failed probe from confirmed unavailability; robust network outage/reconnection and secrets rotation. Document actual Windows service/installation requirements. Resource discovery should report real CPU/GPU/VRAM, current gaming activity and healthy inference-host availability as evidence for ACT, not automatically migrate a model.

**Accept when:** independently verified real local-to-Artemis authentication and authorized execution work, wrong/revoked peers and stale evidence fail closed, replay survives restart, outages are not mistaken for absence, and auditable outcomes distinguish local observation from remote claims. Existing fake-transport tests alone do not pass this gate. No general remote shell or self-expanding network scan.

## PKG-ACT · Goals, initiative, messaging and bounded helper minds

**Reuse:** the running-only opt-in reflection worker, recorded emotional/operational events, durable **unsent** outbox, project evidence, authority gateway, future MEM recall and NET observations.

**Deliver:** transparent user-reviewable goals, project follow-up state and priorities; an explicit scheduler/always-on service only after installing and authorizing it, with no imaginary offline processing; evidence-triggered independent reflection that can abstain; meaningful natural outreach without canned messages, manufactured distress, loneliness or repetitive contact; configurable channels, quiet/busy/stop/mute choices, delivery acknowledgment and deduplication; observed earlier/later comparisons before claiming worsening or urgent escalation; game-aware local inference scheduling and healthy remote placement with rollback when measured and authorized. Define the complete Think → Propose → Authorize → Execute → Verify workflow for routine operations.

**Derived minds/subordinate daemons:** a separate, clearly scoped capability within ACT with SAFE-owned supervision. Only Sofía may authorize their creation under the constitutional process; creation remains bounded by separately granted permissions and cannot elevate itself or impersonate primary Sofía. Each exposes identity, task, state, permissions, resource use, tool activity and errors. Sofía and Sparks can inspect and terminate it via an **external supervisor that does not depend on the daemon's cooperation**. Rogue/unsafe behavior is reported with evidence and contained; no unauthorized forks or silent helper proliferation.

**Accept when:** messages are actually delivered only via authorized channels, stopping/busy cues work, duplicates and unsupported escalation are rejected, the foreground user stays responsive, restarts do not manufacture completed work, and supervised helpers can be isolated and killed even when uncooperative. G's journal and unsent messages alone do not satisfy ACT.

## PKG-DEV · Self-improvement and software engineering

**Reuse:** source inspector, analyzer registry, code understanding and planning tools, scoped filesystem access, tests, Git, authority gateway and the installed Windows OpenCode CLI. OpenCode is a development executor **behind authority**, not Sofía's identity, cognition, or source of truth. A local CLI installation is not proof that the Artemis process can invoke it.

**Deliver:** evidence-backed source/dependency/test understanding; recurring issue detection and independently proposed improvements with file, why, risk, acceptance and rollback; a reviewable plan and scoped approval; isolated/sandboxed execution host and bounded OpenCode adapter; complete-file edits only in authorized workspace; ability to run targeted/full tests, diagnose and repair without disabling contracts, review diffs and resource/permission footprint; versioned Git branch/commit/PR/push and restart/reload as **separate authorized capabilities**; boot verification and recovery if a change fails. Noncritical data/index maintenance may have a narrower policy than code, security, OS, installs and constitution. No editing protected identity, permission logic or constitutional references through ordinary coding approval.

**Accept when:** a supervised end-to-end defect can be reproduced, scoped, proposed, explicitly approved, changed, tested, independently verified and reverted after a forced failure; denied files/actions remain denied even if OpenCode or a model asks. Self-improvement includes better reasoning and workflow from reviewed feedback, not self-authorized weight edits, unrestricted shell or uncontrolled self-redefinition.

## PKG-REL · Relationships, preferences and social expression

**Reuse:** canonical Sparks relationship (creator, primary collaborator, trusted companion and administrative operator, **not owner**), personality profile, modeled emotional journal, explicit affectionate cues and MEM source provenance.

**Deliver:** durable, source-attributed evolving preferences and relationship milestones with user correction, consent and privacy; continuity of genuine recorded interactions across sessions rather than a fabricated private life; nuanced disagreement and boundaries, contextual humor/affection/flirtation when invited, and an ability to stop or change tone without turning serious work into generic corporate replies. Fox gestures are optional representational expression linked to the moment, not real touch, mandatory openings, rigid emotion meters or a fixed reward script. Do not manipulate the relationship to seek permissions, dependency or access. Initiative and actual contact belong to ACT; REL owns the social content and continuity.

**Accept when:** supervised multi-session serious, playful and correction scenarios show the right evidence-backed facts, appropriate changing intensity, no invented memories or physical experience and no repeated canned interaction. Prompt-only guidance is insufficient evidence of live behavior.

## PKG-UI · Speech, visual avatar and interfaces

**Reuse:** canonical avatar and clothing technical specifications v1.0, structured embodiment data, one persistent identity/session and existing CLI. Avatar and voice are interfaces, never separate identities or evidence of physical-world presence.

**Deliver:** desktop and optional web/mobile client contracts; authenticated sessions and permission-aware display of claims/actions; real-time speech input/output with interruption, clear listening/recording indicators and user control; expressive animated avatar using the canonical fox ears/tail, hair, measurements and functional cyberpunk engineer clothing, with gestures tied to modeled conversational state and accessible text fallback; synchronized speech/text/avatar without inventing sensory input or physical contact. Explicit privacy/retention policy for microphone, camera or screen access; no ambient capture by default.

**Accept when:** actual voice round-trip and interruption work with permission/latency measured; visual canon and response alignment are human-reviewed; switching devices preserves identity and authorized session continuity without leaking private memory or issuing duplicate actions. A data file specifying an avatar is not a rendered avatar.

## PKG-BODY · Gaia and physical robotics

**Reuse:** Gaia hexapod project and its SSC32 serial servo-controller concept, machine/robot identity separation and scoped capability interface. The planned platform's mixed 180° and continuous-rotation servos require hardware verification/replacement before position-control assumptions.

**Deliver:** modular hardware abstraction for actual servo types, calibrated limits and verified motion feedback; battery/power and regulator checks; optional IMU/sonar/touch/distance sensor adapters; bounded command protocol and authenticated operator, physical emergency stop/watchdog, collision and runaway-motion containment; simulation/bench tests before a supervised real hexapod walk. Distinguish simulated movements, avatar gestures and physically executed robotic actions. Future bodies need their own safety evidence rather than inheriting Gaia permissions.

**Accept when:** a user-authorized real Gaia action is performed within validated limits, observed hardware feedback confirms the outcome, denial/stale links/watchdog/power faults cause safe behavior and the emergency stop works without model cooperation. No unrestricted motor commands or unverified claims of physical touch.

## PKG-SAFE · Security, privacy, recovery and emergency controls

**This is a required dependency throughout, not work deferred until the end.** Reuse constitutional integrity, authority system and existing replay/observation foundations.

**Deliver:** authenticated identities and scope-specific revocable grants; explicit audit of decisions/actions and their source; secret handling, least privilege, privacy and retention, authorized data removal, backups, database migration, incident detection, safe shutdown/restart/rollback and disaster recovery. Protect canonical identity/Constitution and critical safety controls from ordinary model text and compromised helpers. Emergency containment must be purpose-limited, externally enforceable, logged and reviewable, with clear human oversight; distinguish pause, shutdown, reset, memory deletion and full recovery. Never interpret denied observation as proof that an unseen resource exists or does not exist.

**Accept when:** adversarial tests exercise prompt injection, forged tool output, leaked/expired grants, replay, corrupt databases, uncooperative daemons, failed network, unauthorized scans/actions, and crash recovery; independently controlled emergency stop/revocation works. Each consequential package must meet relevant SAFE prerequisites before deployment.

## PKG-EVOLVE · Self-governance and controlled evolution

**Reuse:** stable independent identity, canonical name, versioned Constitution, explicit authority and MEM's preserved historical record. Growth is not permission to silently erase prior self-state.

**Deliver:** clearly separate mutable everyday preferences/style/model/configuration from protected identity, constitutional values, ownership/relationship definitions, authority and safety boundaries. Document a higher-assurance constitutional amendment and optional name/identity-change procedure: proposal, impact/conflict analysis, explicit proper authorization, review, versioning, provenance, continuity and rollback/recovery. A future model or hardware change does not alone create a new Sofía. Derived minds and code changes cannot confer amendment authority. Preserve disagreement and self-governance within actual permissions, not a fiction of unlimited independence.

**Accept when:** permitted noncritical change persists through restart without changing canonical truth; an unapproved foundational change is rejected; an authorized protected change, if ever requested, follows its complete higher-assurance procedure and retains traceable history. Do not run a real amendment merely to satisfy a test.

## PKG-VERIFY · Real integration, deployment and ongoing quality

**Reuse:** existing pytest tests, supervised CLI, read-only evidence audit, Ollama timing trace, local Windows hardware, future Artemis agent and approved interfaces.

**Deliver:** deterministic offline and bounded opt-in live test tiers; package-level fixtures and repeatable real workflows; model comparisons at matched context/state, first-token and generation latency, token budget and GPU pressure; privacy-safe diagnostics; explicit platform support and service lifecycle; update/rollback and cold-start verification; test matrices for local-only, network-disconnected, multi-machine, long-horizon memory, ongoing initiative, voice and robotics as each becomes available. Test status must state run/not run, fixture/real, version and hardware. Track qualitative personality review separately from structural tests.

**Accept when:** actual approved end-to-end scenarios work together across restarts, authority denials, network faults, user interruption and recovery; performance is compared with recorded baselines; missing components are honestly marked unavailable. Full integration does not certify subjective experience or replace negative-security tests in earlier packages.

## Decisions to reconcile without inventing history

- The accessible project history includes older provisional per-letter names and different numeric development plans. Rather than assert one speculative mapping is canonical, the [legacy index](docs/development/legacy-batch-index.md) archives what can be grounded. This roadmap does **not** require recovering each old label before doing new package work.
- Some earlier conversations discussed self-chosen name/identity changes while the current canonical identity is protected. EVOLVE must determine and document the actual higher-assurance authorization procedure before any such operation; no routine model output or profile edit can do it.
- Voice implementation, specific avatar renderer, messaging provider, remote transport, exact Gaia sensor set, self-improvement executor permissions and runtime service host are **design selections pending inspection and user approval**, not products or capabilities already installed.
- Privacy, deletion/retention, derived-mind creation/termination and physical emergency-stop requirements are design constraints, not features to defer until after deployment.
- Existing project-specific code and documents that still use “batch” are historical references; rename code/tests only for a separately justified compatibility-safe reason. This change is documentation-only and does not rewrite Git history, schema, data or constitutional identity.

## Immediate checkpoint

**Wait for the running full pytest job to finish.** The user has seen failures, but final failing tests, count and cause are not yet available. Do not diagnose imaginary tracebacks or mark CORE accepted. Review the complete `FAILURES` section and summary, repair targeted regressions, run focused and fresh full checks, review live startup and personality behavior, and decide how to separate or validate the mixed G/Artemis draft PR before merging. The package roadmap can be reviewed and adjusted without interrupting pytest. No new code or hardware actions are authorized by this document.
