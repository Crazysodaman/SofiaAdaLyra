# Workstream 3 Phase 08: 56-task companion source audit

**Date/head:** 2026-10-11, GitHub `main` `0c75c64f0e7a063ea8cf3bb9a051a83d6ff4aaaa`. **Scope:** 56 original Phase 08 IDs from the unchanged 700-task V18 master. Current shared ledger classifications are copied unchanged; Workstream 1 owns their authoritative updates.

**Audit boundaries:** This is a task-indexed source-first **triage and selected deep traces**, not 56 complete per-function reviews. `production partial traced` means an actual application caller and controlled output were inspected, not that all original task clauses are coded or accepted. `confirmed unproven` is limited to searched named feature paths, not a categorical claim about every possible implementation. No tests/CI or live Desktop/Discord/voice/avatar channels were executed.

**Existing real path:** `SofiaApplication → background_runtime.bridge_voluntary_life_outreach → PresenceInitiativeEngine.consider → SofiaActService.deliver_one → SystemNoticeQueue.deliver_one → configured sender`; source-linked private LIFE milestone, explicit owner feedback, ACT policy, exact source proof and final delivery checks are in production source. Text/voice/avatar expression uses `ExpressionRuntime` with independent receipts; actual renderer playback cannot be inferred from desired intent alone.

## All 56 original IDs: source triage

| CA ID | Existing ledger | This audit depth | Principal source |
|---|---|---|---|
| **CA-401** | unassessed | production partial traced | `src/sofia/application/presence.py` |
| **CA-402** | unassessed | source-to-entrypoint trace open | `src/sofia/application/presence.py` |
| **CA-403** | unassessed | production partial traced | `src/sofia/application/presence.py` |
| **CA-404** | unassessed | production partial traced | `src/sofia/application/presence.py` |
| **CA-405** | unassessed | production partial traced | `src/sofia/application/presence.py` |
| **CA-406** | unassessed | source-to-entrypoint trace open | `src/sofia/application/presence.py` |
| **CA-407** | unassessed | confirmed unproven | `src/sofia/application/presence.py` |
| **CA-408** | unassessed | production partial traced | `src/sofia/application/presence.py` |
| **CA-409** | unassessed | confirmed unproven | `src/sofia/application/presence.py` |
| **CA-410** | unassessed | verification deferred | `src/sofia/application/presence.py` |
| **CA-411** | unassessed | verification deferred | `src/sofia/application/presence.py` |
| **CA-501** | unassessed | source-to-entrypoint trace open | `src/sofia/application/expression_runtime.py` |
| **CA-502** | unassessed | source-to-entrypoint trace open | `src/sofia/application/expression_runtime.py` |
| **CA-503** | unassessed | source-to-entrypoint trace open | `src/sofia/application/expression_runtime.py` |
| **CA-504** | unassessed | source candidate present | `src/sofia/application/expression_runtime.py` |
| **CA-505** | unassessed | source candidate present | `src/sofia/application/expression_runtime.py` |
| **CA-506** | unassessed | source-to-entrypoint trace open | `src/sofia/application/expression_runtime.py` |
| **CA-507** | unassessed | source candidate present | `src/sofia/application/expression_runtime.py` |
| **CA-508** | unassessed | source-to-entrypoint trace open | `src/sofia/application/expression_runtime.py` |
| **CA-509** | unassessed | source candidate present | `src/sofia/application/expression_runtime.py` |
| **CA-510** | unassessed | source-to-entrypoint trace open | `src/sofia/application/expression_runtime.py` |
| **CA-511** | unassessed | source-to-entrypoint trace open | `src/sofia/application/expression_runtime.py` |
| **CA-1801** | unassessed | confirmed unproven | `src/sofia/application/conversation_service.py` |
| **CA-1802** | unassessed | source-to-entrypoint trace open | `src/sofia/application/conversation_service.py` |
| **CA-1803** | unassessed | source-to-entrypoint trace open | `src/sofia/application/conversation_service.py` |
| **CA-1804** | unassessed | source-to-entrypoint trace open | `src/sofia/application/conversation_service.py` |
| **CA-1805** | unassessed | source-to-entrypoint trace open | `src/sofia/application/conversation_service.py` |
| **CA-1806** | unassessed | source-to-entrypoint trace open | `src/sofia/application/conversation_service.py` |
| **CA-2501** | unassessed | source-to-entrypoint trace open | `src/sofia/life/coordinator.py` |
| **CA-2502** | unassessed | source-to-entrypoint trace open | `src/sofia/life/coordinator.py` |
| **CA-2503** | unassessed | confirmed unproven | `src/sofia/life/coordinator.py` |
| **CA-2504** | unassessed | confirmed unproven | `src/sofia/life/coordinator.py` |
| **CA-2505** | unassessed | source-to-entrypoint trace open | `src/sofia/life/coordinator.py` |
| **CA-2506** | unassessed | source-to-entrypoint trace open | `src/sofia/life/coordinator.py` |
| **CA-2507** | unassessed | source-to-entrypoint trace open | `src/sofia/life/coordinator.py` |
| **CA-2508** | unassessed | source-to-entrypoint trace open | `src/sofia/life/coordinator.py` |
| **CA-3801** | unassessed | design/research open | `src/sofia/application/presence.py` |
| **CA-3802** | unassessed | design/research open | `src/sofia/application/presence.py` |
| **CA-3803** | unassessed | design/research open | `src/sofia/application/presence.py` |
| **CA-3804** | unassessed | design/research open | `src/sofia/application/presence.py` |
| **CA-3805** | unassessed | design/research open | `src/sofia/application/presence.py` |
| **CA-3806** | unassessed | research/acceptance pending | `src/sofia/application/presence.py` |
| **CA-3807** | unassessed | design/research open | `src/sofia/application/presence.py` |
| **CA-3808** | unassessed | design/research open | `src/sofia/application/presence.py` |
| **CA-3809** | unassessed | design/research open | `src/sofia/application/presence.py` |
| **CA-3810** | unassessed | design/research open | `src/sofia/application/presence.py` |
| **CA-6001** | unassessed | design/research open | `src/sofia/emotion/journal.py` |
| **CA-6002** | unassessed | design/research open | `src/sofia/emotion/journal.py` |
| **CA-6003** | unassessed | design/research open | `src/sofia/emotion/journal.py` |
| **CA-6004** | unassessed | design/research open | `src/sofia/emotion/journal.py` |
| **CA-6005** | unassessed | design/research open | `src/sofia/emotion/journal.py` |
| **CA-6006** | unassessed | design/research open | `src/sofia/emotion/journal.py` |
| **CA-6007** | unassessed | design/research open | `src/sofia/emotion/journal.py` |
| **CA-6008** | unassessed | source candidate present | `src/sofia/emotion/journal.py` |
| **CA-6009** | unassessed | design/research open | `src/sofia/emotion/journal.py` |
| **CA-6010** | unassessed | research/acceptance pending | `src/sofia/emotion/journal.py` |

## Original task wording and remaining proof

### CA-401

- [ ] **CA-401 [EXISTS → VERIFY]** Build on production REL, SOCIAL, ACT, HABIT, PRESENCE and the application-owned initiative engine rather than a second notification system.

**Source locations to trace:** `src/sofia/application/presence.py`, `src/sofia/application/act_service.py`, `src/sofia/act/system_notice.py`.

**Observed/review status:** Real LIFE→Presence→ACT uses application-owned services, not a new notification owner. Verify remaining REL/SOCIAL/HABIT composition and delivery channels.

**Verdict:** production partial traced; **not accepted**; no tests executed.

### CA-402

- [ ] **CA-402 [GAP]** Use grounded relationship/history signals to revisit unfinished discussions or ask useful contextual follow-ups when appropriate.

**Source locations to trace:** `src/sofia/application/presence.py`, `src/sofia/application/act_service.py`, `src/sofia/act/system_notice.py`.

**Observed/review status:** Production source includes bounded Presence observations, ACT queuing, owner-only LIFE project feedback, stop/mute checks and last-send original evidence validation. Missing follow-up/acknowledgment clauses must be traced individually.

**Verdict:** source-to-entrypoint trace open; **not accepted**; no tests executed.

### CA-403

- [ ] **CA-403 [GAP]** Allow proactive project updates, thoughtful questions, genuine disagreement, and voluntary sharing of creative work without user prompts.

**Source locations to trace:** `src/sofia/application/presence.py`, `src/sofia/application/act_service.py`, `src/sofia/act/system_notice.py`.

**Observed/review status:** Voluntary `bridge_voluntary_life_outreach` queues verified personal project update without per-project preapproval; unfinished discussion/factual disagreement need separate evidence.

**Verdict:** production partial traced; **not accepted**; no tests executed.

### CA-404

- [ ] **CA-404 [VERIFY]** Respect user activity, quiet hours, consent, delivery limits, rate limits, rejection, privacy, unavailable transports and the legitimate choice of silence.

**Source locations to trace:** `src/sofia/application/presence.py`, `src/sofia/application/act_service.py`, `src/sofia/act/system_notice.py`.

**Observed/review status:** Owner quiet/consent/stop/mute and private exact source checks exist. Real channel expiry, changing routes, multi-week pressure need acceptance.

**Verdict:** production partial traced; **not accepted**; no tests executed.

### CA-405

- [ ] **CA-405 [VERIFY]** Carry through transport attempt/acceptance/acknowledgement receipts; do not claim Sparks saw or heard a message unless verified.

**Source locations to trace:** `src/sofia/application/presence.py`, `src/sofia/application/act_service.py`, `src/sofia/act/system_notice.py`.

**Observed/review status:** Actual ACT sender accepts independent delivery outcomes; pre-send trace was corrected after final consent checks. Actual Desktop/Discord ACK matrix untested.

**Verdict:** production partial traced; **not accepted**; no tests executed.

### CA-406

- [ ] **CA-406 [VERIFY]** Evaluate initiative relevance and interruption cost across weeks. No guilt-based outreach or dependence-seeking behavior.

**Source locations to trace:** `src/sofia/application/presence.py`, `src/sofia/application/act_service.py`, `src/sofia/act/system_notice.py`.

**Observed/review status:** Production source includes bounded Presence observations, ACT queuing, owner-only LIFE project feedback, stop/mute checks and last-send original evidence validation. Missing follow-up/acknowledgment clauses must be traced individually.

**Verdict:** source-to-entrypoint trace open; **not accepted**; no tests executed.

### CA-407

- [ ] **CA-407 [GAP]** Introduce a reviewable “conversation thread pending” projection from existing discourse focus, memory and HABIT/REL evidence; reopen only while relevant and not declined.

**Source locations to trace:** `src/sofia/application/presence.py`, `src/sofia/application/act_service.py`, `src/sofia/act/system_notice.py`.

**Observed/review status:** No reviewed active `conversation_thread_pending` model or source-linked pending-thread projection found in current repository search.

**Verdict:** confirmed unproven; **not accepted**; no tests executed.

### CA-408

- [ ] **CA-408 [GAP]** Route LIFE completion/learning milestones into `PresenceInitiativeEngine.consider()` using an already supported `task_completed` or `conversation_followup` event, with verified observations and ACT policy.

**Source locations to trace:** `src/sofia/application/presence.py`, `src/sofia/application/act_service.py`, `src/sofia/act/system_notice.py`.

**Observed/review status:** LIFE completed projects can generate scoped `task_completed` opportunities via `bridge_voluntary_life_outreach`, with no fake delivery receipt.

**Verdict:** production partial traced; **not accepted**; no tests executed.

### CA-409

- [ ] **CA-409 [GAP]** Learn outreach usefulness from actual acknowledged/ignored/declined outcomes, without treating non-response as distress or increasing nagging frequency.

**Source locations to trace:** `src/sofia/application/presence.py`, `src/sofia/application/act_service.py`, `src/sofia/act/system_notice.py`.

**Observed/review status:** Explicit owner welcome/decline stored, but ignoring an update must NOT be read as dislike; actual outcome-weighted usefulness policy was not traced.

**Verdict:** confirmed unproven; **not accepted**; no tests executed.

### CA-410

- [ ] **CA-410 [VERIFY]** Check proactive messaging across Desktop/Discord with correct principal, audience, device availability, consent/quiet hours and actual delivery acknowledgements.

**Source locations to trace:** `src/sofia/application/presence.py`, `src/sofia/application/act_service.py`, `src/sofia/act/system_notice.py`.

**Observed/review status:** One canonical private ACT route exists; authentic Desktop/Discord recipient receipts and cross-channel restoration need owner-run tests.

**Verdict:** verification deferred; **not accepted**; no tests executed.

### CA-411

- [ ] **CA-411 [VERIFY]** Add a “nothing worth sharing” acceptance case and evaluation of overattachment, coercive messaging, faux jealousy and false urgency; autonomous companionship should support human choice.

**Source locations to trace:** `src/sofia/application/presence.py`, `src/sofia/application/act_service.py`, `src/sofia/act/system_notice.py`.

**Observed/review status:** Quiet/no-op selection exists and operator stop gate is source enforced. Anti-dependence multiple-session acceptance unexecuted.

**Verdict:** verification deferred; **not accepted**; no tests executed.

### CA-501

- [ ] **CA-501 [GAP]** Preserve consistent identity while allowing nuanced, evidence-grounded preferences, opinions, humor, skepticism, and conversational reciprocity.

**Source locations to trace:** `src/sofia/application/expression_runtime.py`, `src/sofia/application/emotional_conversation.py`, `src/sofia/personality/influence.py`.

**Observed/review status:** The expression service exposes typed ExpressionIntent and independent receipts, while emotional conversation source exists; no renderer-free source inspection proves actual voice or avatar output.

**Verdict:** source-to-entrypoint trace open; **not accepted**; no tests executed.

### CA-502

- [ ] **CA-502 [GAP]** Connect EMOTION and PERSONALITY to actual ongoing projects, relationship experiences, activity, environment, and time without inventing feelings or physical sensations.

**Source locations to trace:** `src/sofia/application/expression_runtime.py`, `src/sofia/application/emotional_conversation.py`, `src/sofia/personality/influence.py`.

**Observed/review status:** The expression service exposes typed ExpressionIntent and independent receipts, while emotional conversation source exists; no renderer-free source inspection proves actual voice or avatar output.

**Verdict:** source-to-entrypoint trace open; **not accepted**; no tests executed.

### CA-503

- [ ] **CA-503 [GAP]** Maintain emotional and conversational continuity during project work and across sessions while allowing state to change naturally.

**Source locations to trace:** `src/sofia/application/expression_runtime.py`, `src/sofia/application/emotional_conversation.py`, `src/sofia/personality/influence.py`.

**Observed/review status:** The expression service exposes typed ExpressionIntent and independent receipts, while emotional conversation source exists; no renderer-free source inspection proves actual voice or avatar output.

**Verdict:** source-to-entrypoint trace open; **not accepted**; no tests executed.

### CA-504

- [ ] **CA-504 [GAP]** Use one bounded contextual expression decision to coordinate language, voice prosody, face, ears, tail, pose and gestures.

**Source locations to trace:** `src/sofia/application/expression_runtime.py`, `src/sofia/application/emotional_conversation.py`, `src/sofia/personality/influence.py`.

**Observed/review status:** Typed ExpressionIntent exists; full text↔TTS↔avatar gesture coordination and actual renderer acknowledgements not established.

**Verdict:** source candidate present; **not accepted**; no tests executed.

### CA-505

- [ ] **CA-505 [VERIFY]** Require each actual voice/avatar renderer to acknowledge what displayed or played; no textual claims about animation or speech that did not occur.

**Source locations to trace:** `src/sofia/application/expression_runtime.py`, `src/sofia/application/emotional_conversation.py`, `src/sofia/personality/influence.py`.

**Observed/review status:** Independent ExpressionReceipt model exists, but actual voice/avatar channel ACK and sound/gesture truth need end-to-end proof.

**Verdict:** source candidate present; **not accepted**; no tests executed.

### CA-506

- [ ] **CA-506 [VERIFY]** Compare natural dialogue against canned closings, random gesture injection, exaggerated emotional behavior and ungrounded self-reports.

**Source locations to trace:** `src/sofia/application/expression_runtime.py`, `src/sofia/application/emotional_conversation.py`, `src/sofia/personality/influence.py`.

**Observed/review status:** The expression service exposes typed ExpressionIntent and independent receipts, while emotional conversation source exists; no renderer-free source inspection proves actual voice or avatar output.

**Verdict:** source-to-entrypoint trace open; **not accepted**; no tests executed.

### CA-507

- [ ] **CA-507 [GAP]** Define a shared non-authoritative `ExpressionIntent` projection: sentiment/modulation, delivery mode, voice style, gestures, avatar state, source evidence, time and expiry. Renderers return independent receipts; text must not pretend physical output happened.

**Source locations to trace:** `src/sofia/application/expression_runtime.py`, `src/sofia/application/emotional_conversation.py`, `src/sofia/personality/influence.py`.

**Observed/review status:** ExpressionIntent in `expression_runtime.py` stores evidence/time/channel projection; every targeted actual renderer must prove playback/state.

**Verdict:** source candidate present; **not accepted**; no tests executed.

### CA-508

- [ ] **CA-508 [GAP]** Allow revisable, scoped conversation preferences for humor, verbosity and disagreement, while preserving the canonical Sofía identity and user override.

**Source locations to trace:** `src/sofia/application/expression_runtime.py`, `src/sofia/application/emotional_conversation.py`, `src/sofia/personality/influence.py`.

**Observed/review status:** The expression service exposes typed ExpressionIntent and independent receipts, while emotional conversation source exists; no renderer-free source inspection proves actual voice or avatar output.

**Verdict:** source-to-entrypoint trace open; **not accepted**; no tests executed.

### CA-509

- [ ] **CA-509 [GAP]** Apply gradual changes in mood-like state using verified activity outcomes and context instead of making emotion a direct synonym of one NEURO winning signal.

**Source locations to trace:** `src/sofia/application/expression_runtime.py`, `src/sofia/application/emotional_conversation.py`, `src/sofia/personality/influence.py`.

**Observed/review status:** Emotion journal/projection and NEURO are separated in source; gradual evidence-linked appraisal/decay across real projects not traced.

**Verdict:** source candidate present; **not accepted**; no tests executed.

### CA-510

- [ ] **CA-510 [VERIFY]** Exercise the full voice/STT/TTS path, interruption, model competition, and avatar/ear/tail/wardrobe projection on actual Venus devices; ensure fallbacks are truthful.

**Source locations to trace:** `src/sofia/application/expression_runtime.py`, `src/sofia/application/emotional_conversation.py`, `src/sofia/personality/influence.py`.

**Observed/review status:** The expression service exposes typed ExpressionIntent and independent receipts, while emotional conversation source exists; no renderer-free source inspection proves actual voice or avatar output.

**Verdict:** source-to-entrypoint trace open; **not accepted**; no tests executed.

### CA-511

- [ ] **CA-511 [VERIFY]** Test text-only, voice-only, renderer absent, delayed renderer acknowledgement, and channel handoff for consistent character without inventing bodily sensations or lived feelings.

**Source locations to trace:** `src/sofia/application/expression_runtime.py`, `src/sofia/application/emotional_conversation.py`, `src/sofia/personality/influence.py`.

**Observed/review status:** The expression service exposes typed ExpressionIntent and independent receipts, while emotional conversation source exists; no renderer-free source inspection proves actual voice or avatar output.

**Verdict:** source-to-entrypoint trace open; **not accepted**; no tests executed.

### CA-1801

- [ ] **CA-1801 [GAP]** Add a `shared_activity_offer` candidate for **verified** collaborative hobby milestones (Gaia design review, virtual lab, model railway planning, coding) routed through Presence/ACT.

**Source locations to trace:** `src/sofia/application/conversation_service.py`, `src/sofia/application/background_runtime.py`, `src/sofia/application/presence.py`.

**Observed/review status:** Source search found `shared_activity_offer` in roadmap/report but no production initiator/event type; requires one truly verified collaborative milestone.

**Verdict:** confirmed unproven; **not accepted**; no tests executed.

### CA-1802

- [ ] **CA-1802 [GAP]** Track conversational commitments and follow-through: a promised update becomes a verifiable pending action, a completed update closes it, and declined topics remain declined.

**Source locations to trace:** `src/sofia/application/conversation_service.py`, `src/sofia/application/background_runtime.py`, `src/sofia/application/presence.py`.

**Observed/review status:** Canonical conversation and LIFE outreach paths exist; the original commitment, shared hobby, conversational repair and human control clauses need dedicated source-to-receipt traces.

**Verdict:** source-to-entrypoint trace open; **not accepted**; no tests executed.

### CA-1803

- [ ] **CA-1803 [GAP]** Handle conversational repairs: correct an inaccurate recollection, acknowledge a failed tool action, revise an opinion after evidence and avoid repeating an already rejected suggestion.

**Source locations to trace:** `src/sofia/application/conversation_service.py`, `src/sofia/application/background_runtime.py`, `src/sofia/application/presence.py`.

**Observed/review status:** Canonical conversation and LIFE outreach paths exist; the original commitment, shared hobby, conversational repair and human control clauses need dedicated source-to-receipt traces.

**Verdict:** source-to-entrypoint trace open; **not accepted**; no tests executed.

### CA-1804

- [ ] **CA-1804 [GAP]** Enable meaningful disagreement without forced flattery; cite the exact observation or project evidence that motivated her correction.

**Source locations to trace:** `src/sofia/application/conversation_service.py`, `src/sofia/application/background_runtime.py`, `src/sofia/application/presence.py`.

**Observed/review status:** Canonical conversation and LIFE outreach paths exist; the original commitment, shared hobby, conversational repair and human control clauses need dedicated source-to-receipt traces.

**Verdict:** source-to-entrypoint trace open; **not accepted**; no tests executed.

### CA-1805

- [ ] **CA-1805 [VERIFY]** Evaluate a multi-session shared-project story for reciprocity, continuity, user control, accurate delivery acknowledgement and the ability to remain quiet.

**Source locations to trace:** `src/sofia/application/conversation_service.py`, `src/sofia/application/background_runtime.py`, `src/sofia/application/presence.py`.

**Observed/review status:** Canonical conversation and LIFE outreach paths exist; the original commitment, shared hobby, conversational repair and human control clauses need dedicated source-to-receipt traces.

**Verdict:** source-to-entrypoint trace open; **not accepted**; no tests executed.

### CA-1806

- [ ] **CA-1806 [VERIFY]** Add user-centered guardrails for notification pressure and dependence-seeking behavior, including no guilt, invented jealousy, false distress, urgency fabrication or escalation after silence. Research on companion use calls for caution, not a universal claim about outcomes.

**Source locations to trace:** `src/sofia/application/conversation_service.py`, `src/sofia/application/background_runtime.py`, `src/sofia/application/presence.py`.

**Observed/review status:** Canonical conversation and LIFE outreach paths exist; the original commitment, shared hobby, conversational repair and human control clauses need dedicated source-to-receipt traces.

**Verdict:** source-to-entrypoint trace open; **not accepted**; no tests executed.

### CA-2501

- [ ] **CA-2501 P2 [GAP]** Implement a small **value-of-information** decision over eligible tools: gather existing local status, read authorized source, ask owner, or abstain. Test that a redundant/noisy query loses to quiet; do not request new privileges merely because of curiosity.

**Source locations to trace:** `src/sofia/life/coordinator.py`, `src/sofia/application/presence.py`, `src/sofia/interaction/world_editor.py`.

**Observed/review status:** LIFE source contains bounded selection and independently verified projects; sharing a hobby, promised follow-ups and WorldEditor source-receipt joins cannot be inferred merely from component presence.

**Verdict:** source-to-entrypoint trace open; **not accepted**; no tests executed.

### CA-2502

- [ ] **CA-2502 P2 [GAP]** Introduce a **learning-progress ledger** for one *sandboxed* hobby skill: concrete initial competence, verified practice, regression, retry cap and retirement. Feed LIFE preferences from measured progress rather than pure novelty or apparent model excitement.

**Source locations to trace:** `src/sofia/life/coordinator.py`, `src/sofia/application/presence.py`, `src/sofia/interaction/world_editor.py`.

**Observed/review status:** LIFE source contains bounded selection and independently verified projects; sharing a hobby, promised follow-ups and WorldEditor source-receipt joins cannot be inferred merely from component presence.

**Verdict:** source-to-entrypoint trace open; **not accepted**; no tests executed.

### CA-2503

- [ ] **CA-2503 P2 [GAP]** Support **shared hobby session proposals** for a verified LIFE milestone (robotics design discussion, railroad planning, virtual lab), preserving collaboration ownership, accepted/rejected state, optionality and no nagging after refusal.

**Source locations to trace:** `src/sofia/life/coordinator.py`, `src/sofia/application/presence.py`, `src/sofia/interaction/world_editor.py`.

**Observed/review status:** Original LIFE and Presence components exist, but consent-governed shared hobby offer acceptance/decline join is not source-traced.

**Verdict:** confirmed unproven; **not accepted**; no tests executed.

### CA-2504

- [ ] **CA-2504 P2 [GAP]** Bridge scheduled-but-unanswered questions and explicit promises from COGNITION v2 focus into approved prospective follow-up events; distinguish `remind myself to check` from `tell the user now`, and ensure quiet/busy rules.

**Source locations to trace:** `src/sofia/life/coordinator.py`, `src/sofia/application/presence.py`, `src/sofia/interaction/world_editor.py`.

**Observed/review status:** No unified scheduled unanswered-question vs promise-fulfillment source path was identified.

**Verdict:** confirmed unproven; **not accepted**; no tests executed.

### CA-2505

- [ ] **CA-2505 P2 [GAP]** Connect **WorldEditor interaction receipts** to the same verified LIFE activity history; a symbolic motion should update the simulated world only after the intended simulation action is actually acknowledged, and never imply real-world contact.

**Source locations to trace:** `src/sofia/life/coordinator.py`, `src/sofia/application/presence.py`, `src/sofia/interaction/world_editor.py`.

**Observed/review status:** LIFE source contains bounded selection and independently verified projects; sharing a hobby, promised follow-ups and WorldEditor source-receipt joins cannot be inferred merely from component presence.

**Verdict:** source-to-entrypoint trace open; **not accepted**; no tests executed.

### CA-2506

- [ ] **CA-2506 P2 [VERIFY]** Test social restraint across seven days: when no grounded event exists, Sofía remains quiet; when a relevant project changes she can offer one useful update; when the user declines, recurrence and cross-channel duplications stop.

**Source locations to trace:** `src/sofia/life/coordinator.py`, `src/sofia/application/presence.py`, `src/sofia/interaction/world_editor.py`.

**Observed/review status:** LIFE source contains bounded selection and independently verified projects; sharing a hobby, promised follow-ups and WorldEditor source-receipt joins cannot be inferred merely from component presence.

**Verdict:** source-to-entrypoint trace open; **not accepted**; no tests executed.

### CA-2507

- [ ] **CA-2507 P2 [GAP]** Create **consent and audience maps for companion episodes** separating personal reflection, shared conversation, operational telemetry and intimate/private artifact state; make recipient preview and delete/revoke requests propagate to association caches.

**Source locations to trace:** `src/sofia/life/coordinator.py`, `src/sofia/application/presence.py`, `src/sofia/interaction/world_editor.py`.

**Observed/review status:** LIFE source contains bounded selection and independently verified projects; sharing a hobby, promised follow-ups and WorldEditor source-receipt joins cannot be inferred merely from component presence.

**Verdict:** source-to-entrypoint trace open; **not accepted**; no tests executed.

### CA-2508

- [ ] **CA-2508 P2 [VERIFY]** Evaluate the same conversation as text-only, text+avatar, voice, and Discord; all modes must retain accurate facts, stable identity, contextual tone, real output acknowledgements and no claim that an unavailable renderer spoke/moved.

**Source locations to trace:** `src/sofia/life/coordinator.py`, `src/sofia/application/presence.py`, `src/sofia/interaction/world_editor.py`.

**Observed/review status:** LIFE source contains bounded selection and independently verified projects; sharing a hobby, promised follow-ups and WorldEditor source-receipt joins cannot be inferred merely from component presence.

**Verdict:** source-to-entrypoint trace open; **not accepted**; no tests executed.

### CA-3801

- [ ] **CA-3801 P1 [DESIGN/RESEARCH]** Define a **companion initiative contract** for voluntary outreach: what changed, relevance to user, interruption cost, quiet hours, channel, permission, dedupe period and a valid 'say nothing' choice.

**Source locations to trace:** `src/sofia/application/presence.py`, `src/sofia/application/expression_runtime.py`, `src/sofia/emotion/journal.py`.

**Observed/review status:** Design/research tasks may have partial implementations, but require explicit comparison contracts, original ethics/consent decisions and cross-channel observable evaluation.

**Verdict:** design/research open; **not accepted**; no tests executed.

### CA-3802

- [ ] **CA-3802 P2 [DESIGN/RESEARCH]** Create a framework for appropriate disagreement, factual correction and self-correction without becoming argumentative or flattering. Evaluate whether her challenge is grounded, helpful and respectful.

**Source locations to trace:** `src/sofia/application/presence.py`, `src/sofia/application/expression_runtime.py`, `src/sofia/emotion/journal.py`.

**Observed/review status:** Design/research tasks may have partial implementations, but require explicit comparison contracts, original ethics/consent decisions and cross-channel observable evaluation.

**Verdict:** design/research open; **not accepted**; no tests executed.

### CA-3803

- [ ] **CA-3803 P1 [DESIGN/RESEARCH]** Design **mutually intelligible plans**: Sofía can explain what she proposes, why, what she will not do, what success looks like and when she will stop; avoid presenting hidden reasoning as verbatim fact.

**Source locations to trace:** `src/sofia/application/presence.py`, `src/sofia/application/expression_runtime.py`, `src/sofia/emotion/journal.py`.

**Observed/review status:** Design/research tasks may have partial implementations, but require explicit comparison contracts, original ethics/consent decisions and cross-channel observable evaluation.

**Verdict:** design/research open; **not accepted**; no tests executed.

### CA-3804

- [ ] **CA-3804 P1 [DESIGN/RESEARCH]** Specify the difference between private exploration, user-shared activity and externally published work. All invitations, personal files, speech, Discord sharing and portfolio exports need audience-specific rules.

**Source locations to trace:** `src/sofia/application/presence.py`, `src/sofia/application/expression_runtime.py`, `src/sofia/emotion/journal.py`.

**Observed/review status:** Design/research tasks may have partial implementations, but require explicit comparison contracts, original ethics/consent decisions and cross-channel observable evaluation.

**Verdict:** design/research open; **not accepted**; no tests executed.

### CA-3805

- [ ] **CA-3805 P2 [DESIGN/RESEARCH]** Study continuity of personality across LLM swaps, model version changes, device moves and voice/avatar channels using a fixed behavior matrix. No duplicate identity owner or forced emotional self-report.

**Source locations to trace:** `src/sofia/application/presence.py`, `src/sofia/application/expression_runtime.py`, `src/sofia/emotion/journal.py`.

**Observed/review status:** Design/research tasks may have partial implementations, but require explicit comparison contracts, original ethics/consent decisions and cross-channel observable evaluation.

**Verdict:** design/research open; **not accepted**; no tests executed.

### CA-3806

- [ ] **CA-3806 P2 [DESIGN/RESEARCH]** Define emotional expression as an optional interpretation of observed events and relational context. Prevent synthetic sadness/anger being used to pressure the user, and allow straightforward practical answers.

**Source locations to trace:** `src/sofia/application/presence.py`, `src/sofia/application/expression_runtime.py`, `src/sofia/emotion/journal.py`.

**Observed/review status:** Modeled emotion exists but needs explicit non-coercive interface contract and multi-session owner-respect tests.

**Verdict:** research/acceptance pending; **not accepted**; no tests executed.

### CA-3807

- [ ] **CA-3807 P2 [DESIGN/RESEARCH]** Design a 'shared hobby loop': Sofía brings a verified plan/prototype, invites collaboration once, records accepted suggestions accurately, does independent revision later and acknowledges user contributions.

**Source locations to trace:** `src/sofia/application/presence.py`, `src/sofia/application/expression_runtime.py`, `src/sofia/emotion/journal.py`.

**Observed/review status:** Design/research tasks may have partial implementations, but require explicit comparison contracts, original ethics/consent decisions and cross-channel observable evaluation.

**Verdict:** design/research open; **not accepted**; no tests executed.

### CA-3808

- [ ] **CA-3808 P2 [DESIGN/RESEARCH]** Evaluate voice/avatar **temporal coherence**: speech start/end receipts, text/audience sync, pose gesture render acknowledgement, interruption, muted or absent devices, and no pretend tail movement.

**Source locations to trace:** `src/sofia/application/presence.py`, `src/sofia/application/expression_runtime.py`, `src/sofia/emotion/journal.py`.

**Observed/review status:** Design/research tasks may have partial implementations, but require explicit comparison contracts, original ethics/consent decisions and cross-channel observable evaluation.

**Verdict:** design/research open; **not accepted**; no tests executed.

### CA-3809

- [ ] **CA-3809 P2 [DESIGN/RESEARCH]** Design context-sensitive boundaries for autonomous downtime: gaming on Venus, quiet household hours, no-response intervals, illness/absence ambiguity, network outage and user-initiated privacy mode.

**Source locations to trace:** `src/sofia/application/presence.py`, `src/sofia/application/expression_runtime.py`, `src/sofia/emotion/journal.py`.

**Observed/review status:** Design/research tasks may have partial implementations, but require explicit comparison contracts, original ethics/consent decisions and cross-channel observable evaluation.

**Verdict:** design/research open; **not accepted**; no tests executed.

### CA-3810

- [ ] **CA-3810 P2 [DESIGN/RESEARCH]** Specify a user-facing feedback and correction interface for initiative, memory, goals and presentation. Measure improvements without optimizing for message count, personal dependence or model self-approval.

**Source locations to trace:** `src/sofia/application/presence.py`, `src/sofia/application/expression_runtime.py`, `src/sofia/emotion/journal.py`.

**Observed/review status:** Design/research tasks may have partial implementations, but require explicit comparison contracts, original ethics/consent decisions and cross-channel observable evaluation.

**Verdict:** design/research open; **not accepted**; no tests executed.

### CA-6001

- [ ] **CA-6001 [DESIGN/RESEARCH]** Write an **existing-code integration map** for `EmotionalJournal`, `EmotionalConversationService`, relationship history, reflection journal, avatar expression receipts and `NeuroRuntime`. Reuse those stores and distinguish coded paths from host-observed production behavior.

**Source locations to trace:** `src/sofia/emotion/journal.py`, `src/sofia/emotion/projection.py`, `src/sofia/application/expression_runtime.py`.

**Observed/review status:** An emotion journal, modeled affect projection and expression intent exist; historical correction, time-scale separation and anti-coercion acceptance cannot be established from a single component.

**Verdict:** design/research open; **not accepted**; no tests executed.

### CA-6002

- [ ] **CA-6002 [DESIGN/RESEARCH]** Define three separate time scales: **current modeled affect** (short-lived), **historical emotional episodes** (source-linked and potentially lifelong), and **relationship/personality continuity** (persistent but revisable). One archived mood cannot remain the current mood forever.

**Source locations to trace:** `src/sofia/emotion/journal.py`, `src/sofia/emotion/projection.py`, `src/sofia/application/expression_runtime.py`.

**Observed/review status:** An emotion journal, modeled affect projection and expression intent exist; historical correction, time-scale separation and anti-coercion acceptance cannot be established from a single component.

**Verdict:** design/research open; **not accepted**; no tests executed.

### CA-6003

- [ ] **CA-6003 [DESIGN/RESEARCH]** Specify **emotion record metadata**: event/source evidence, `occurred_at`, actor/source channel, principal/audience/consent, interpreted emotion labels, uncertainty, user correction, reflection/revision history and optional project/topic links. Mood is not a fact about the user unless expressed by them.

**Source locations to trace:** `src/sofia/emotion/journal.py`, `src/sofia/emotion/projection.py`, `src/sofia/application/expression_runtime.py`.

**Observed/review status:** An emotion journal, modeled affect projection and expression intent exist; historical correction, time-scale separation and anti-coercion acceptance cannot be established from a single component.

**Verdict:** design/research open; **not accepted**; no tests executed.

### CA-6004

- [ ] **CA-6004 [DESIGN/RESEARCH]** Specify **time dynamics**: bounded decay/context relevance for current emotional projection, explicitly modeled anticipation or ongoing emotional context only when supported, and no inferred continuous subjective experience during shutdown. Do not turn a modeled state into a claim of consciousness.

**Source locations to trace:** `src/sofia/emotion/journal.py`, `src/sofia/emotion/projection.py`, `src/sofia/application/expression_runtime.py`.

**Observed/review status:** An emotion journal, modeled affect projection and expression intent exist; historical correction, time-scale separation and anti-coercion acceptance cannot be established from a single component.

**Verdict:** design/research open; **not accepted**; no tests executed.

### CA-6005

- [ ] **CA-6005 [DESIGN/RESEARCH]** Design **topic-aware emotional reactivation**: returning to a difficult project may retrieve its emotional episode as historical context, but not necessarily restore frustration; immediate weather/chat detours should not delete genuine rapport or force an emotion reset.

**Source locations to trace:** `src/sofia/emotion/journal.py`, `src/sofia/emotion/projection.py`, `src/sofia/application/expression_runtime.py`.

**Observed/review status:** An emotion journal, modeled affect projection and expression intent exist; historical correction, time-scale separation and anti-coercion acceptance cannot be established from a single component.

**Verdict:** design/research open; **not accepted**; no tests executed.

### CA-6006

- [ ] **CA-6006 [DESIGN/RESEARCH]** Define **user affect vs Sofía-modeled emotion separation**, including corrections (“No, I am not angry”), uncertainty, non-diagnostic user language, privacy boundaries and conservative responses for sensitive topics. Do not overfit emotion to user profile or inferred demographics.

**Source locations to trace:** `src/sofia/emotion/journal.py`, `src/sofia/emotion/projection.py`, `src/sofia/application/expression_runtime.py`.

**Observed/review status:** An emotion journal, modeled affect projection and expression intent exist; historical correction, time-scale separation and anti-coercion acceptance cannot be established from a single component.

**Verdict:** design/research open; **not accepted**; no tests executed.

### CA-6007

- [ ] **CA-6007 [DESIGN/RESEARCH]** Design **relationship-specific continuity** without emotional blackmail: history of shared activities, trust, disagreements, promises, absences and boundaries with consent; no guilt about the user not visiting; no fabricated affection or simulated physical claims presented as fact.

**Source locations to trace:** `src/sofia/emotion/journal.py`, `src/sofia/emotion/projection.py`, `src/sofia/application/expression_runtime.py`.

**Observed/review status:** An emotion journal, modeled affect projection and expression intent exist; historical correction, time-scale separation and anti-coercion acceptance cannot be established from a single component.

**Verdict:** design/research open; **not accepted**; no tests executed.

### CA-6008

- [ ] **CA-6008 [DESIGN/RESEARCH]** Preserve **personalized expression provenance**: text, avatar posture/ears/tail, outfits and voice may reflect current grounded state, but only actual renderer/TTS receipts demonstrate external execution. Environment/season/time can modulate presentation but never override consent or SAFE.

**Source locations to trace:** `src/sofia/emotion/journal.py`, `src/sofia/emotion/projection.py`, `src/sofia/application/expression_runtime.py`.

**Observed/review status:** ExpressionIntent/Receipt keeps independent record; body/tail/voice actual delivery and privacy provenance remain channel-specific.

**Verdict:** source candidate present; **not accepted**; no tests executed.

### CA-6009

- [ ] **CA-6009 [DESIGN/RESEARCH]** Define safeguards against **affect-driven false memories and unsafe personalized permissions**: emotional intensity may increase review priority, not factual certainty or authorization. Model-generated memories and external documents remain untrusted evidence until verified.

**Source locations to trace:** `src/sofia/emotion/journal.py`, `src/sofia/emotion/projection.py`, `src/sofia/application/expression_runtime.py`.

**Observed/review status:** An emotion journal, modeled affect projection and expression intent exist; historical correction, time-scale separation and anti-coercion acceptance cannot be established from a single component.

**Verdict:** design/research open; **not accepted**; no tests executed.

### CA-6010

- [ ] **CA-6010 [DESIGN/RESEARCH]** Create acceptance matrix for topic detours, day-to-day mood change, time travel by years, corrected user affect, declined touch/interaction, project disappointment/recovery, warm reunion without false longing claims, channel privacy and reproducible rollback.

**Source locations to trace:** `src/sofia/emotion/journal.py`, `src/sofia/emotion/projection.py`, `src/sofia/application/expression_runtime.py`.

**Observed/review status:** No executed cross-session emotion/consent/reunion acceptance matrix; defer tested claims.

**Verdict:** research/acceptance pending; **not accepted**; no tests executed.

## Coding-first next gaps

- CA-407: source-linked, reviewable prospective conversation threads with genuine owner decline and expiry; no fake history.
- CA-1801/CA-2503: one verified shared-hobby offer with full consent, user response, non-repetition and genuine original project milestone.
- CA-504/505/507 and CA-6008: target-specific output acknowledgement and truthful no-renderer fallback, shared expression intent.
- CA-409/2504: real follow-up usefulness/commitment signals without equating silence to rejection or pressure.

**No source-only claim that these are 56 coding-complete tasks.** Further per-function audit and coding is required before updating global acceptance.


## 2026-10-11 production follow-up: original Presence evidence freshness at final ACT send

The application-owned last send authorization now rechecks original OBSERVED/KNOWN status, numeric confidence ≥ 0.6, event/observation chronology, and observation lifetime covering the queued notice. A later downgraded or corrupt original source is AUTHORIZATION_UNAVAILABLE rather than an eligible notification. Relevant partial CA IDs: CA-404/405/410/1007/2407/2602. Production commit `e1dac928`; six deferred regression cases `9ad3a092`. Actual Desktop/Discord receipt campaigns and all original acceptance remain open.

## Follow-up: pre-ACT LIFE project moment consistency after cognition (2026-10-11)

- **Original CA IDs:** CA-403, CA-404, CA-405, CA-408, CA-410, CA-1007 and CA-2407; still partial, with final acceptance deferred.
- **Found:** the voluntary LIFE outreach bridge compared only three source fields after model latency and did not re-assert the originally approved exact route. Source-backed interest eligibility was also not checked for candidate updates after a source disappeared.
- **Production correction:** the existing original LIFE update projection checks current principal/audience/fresh original interest refs; the real background bridge requires exact refreshed original moment and private route equality before its existing Presence/ACT enqueue call. No competing sender or social scheduler. Source commits `e5a7c78`, `375f9b8`; regression `bd17015` authored but unexecuted. There is no evidence of actual delivery, user view or renderer acknowledgement.

## Follow-up: replays must never resurrect a Presence observation (2026-10-11)

- **Original IDs:** CA-401/404/405/407/410/2407/2602, partial clauses.
- **Confirmed active entrypoint flaw:** `PresenceInitiativeEngine.consider` persisted an event's world observation before checking an existing `presence_initiative_opportunity` record. Repetition after source deletion could restore old grounding and change ACT's later fresh-source decision. A concurrent identical duplicate could also throw SQLite unique constraint after the idempotent ACT enqueue.
- **Production `9de4c3f`:** initial original-event lookup and identity check precedes any observation record creation; canonical atomic `INSERT OR IGNORE` + original decision/identity read-back resolves duplicate consideration. No new sender, no revived original source, no fabricated viewed/read status.
- **Regressions `c40e482` and `8150b31`:** source deletion/replay, changed event identity, and concurrent two-worker idempotent decision, all authored but not run. Cross-channel true recipient/device acknowledgements and prospective thread behavior remain open.
