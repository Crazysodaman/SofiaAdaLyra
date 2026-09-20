# PKG-CLEAN and PKG-INTERACT: implementation and acceptance contracts

**Status:** proposed, documentation-only package contracts, 2026-09-20. Companion to [`ROADMAP.md`](../../ROADMAP.md), [`ROADMAP-EXTENSION.md`](../../ROADMAP-EXTENSION.md), [`package-delivery-contracts.md`](package-delivery-contracts.md) and [`five-cross-package-acceptance-contracts.md`](five-cross-package-acceptance-contracts.md). Together the roadmap has **13 package identifiers**. Do not renumber historical batches or assert either new package is implemented. This document grants no runtime, repository, hardware or constitutional authority. Routine feature-branch Git documentation changes have standing user approval; protected identity/Constitution edits, deployment and unsafe or consequential operations do not.

## Existing implementation evidence and non-negotiable boundaries

- Current `src/sofia/personality/emotion.py` contains an evidence-linked `EmotionalJournal` with `observed`, `user_reported`, `inferred` provenance, original and revised appraisals, and a narrow text matcher for head pats, `good girl` and related phrases. It **does not** implement an arbitrary body-region interaction API, touch sensing or a virtual lab. Do not widen its regex into a supposed all-body interaction engine.
- `src/sofia/personality/expression.py` makes fox gestures optional *representational* expression, permits context-sensitive invited romance/light sensuality, and prohibits invented physical sensations or unearned actions. These are guidance, not proof of consistently correct live model behavior.
- The existing avatar is a canonical representation, not physical hardware. Gaia's physical embodiment and any actual sensor or actuator remain owned by PKG-BODY and require their own independently enforceable safety boundaries. The real homelab and Artemis are PKG-NET, not an implicit part of an avatar sandbox.
- PKG-CORE, MEM, REL, UI, ACT, SAFE and VERIFY retain their existing owners. Reuse the emotional event journal, source messages, identity/embodiment data and capability/authority gateway. Do not add a second personality, journal, identity or authorization system.
- The existing 1,195-test Windows pytest run has shown clustered application/conversation failures; its final tracebacks and summary are still not available in this discussion. Neither package is authorized to mask, rewrite or diagnose those failures without evidence. Documentation commits do not change the running test revision.

## PKG-CLEAN: maintainability, controlled cleanup and technical debt

### Outcome and ownership

Make Sofía simpler to understand, cheaper to maintain and safer to evolve, while preserving her behavior, durable records, protected identity and authorizations. CLEAN owns repository hygiene, dead-code evidence, duplicate-path consolidation, lint/type/documentation drift, dependency hygiene, bounded performance cleanup and migration housekeeping. CORE/MEM/NET/etc. own intentional changes to their behavior; SAFE owns security controls; DEV owns approved engineering execution; VERIFY owns test methodology. CLEAN cannot declare another package accepted.

### Preconditions and inventory

Pin a feature-branch commit and inventory code entry points, imports/references, public API consumers, generated assets, database schemas/versions, persistent data locations, deployment/service scripts, tests, docs, dependencies, target Python/Windows environment and active PR changes. Categorize candidate work as: (A) formatting/documentation/static-only; (B) behavior-preserving refactor; (C) data/schema/dependency change; (D) deletion. Confirm the candidate is genuinely unused across runtime, CLI, tests, migrations, optional deployments and external integrations. A failed code search is not proof a dynamic integration is unused. Maintain a cleanup register recording source evidence, owner, risk, expected diff, verification, rollback and approval level.

### Execution contract

1. Establish a known baseline and capture any pre-existing failures; do not modify files during an already-running full-suite test. Produce small, reviewable commits scoped by failure domain, even when delivering CLEAN as one cohesive package.
2. Prefer removing provably redundant implementation, consolidating equivalent functions and correcting misleading docs/config before introducing new abstractions. Maintain stable public behavior, identity identifiers, observed/inferred semantics, database compatibility, capability scopes and error visibility.
3. Treat production state, user conversations, emotional journal, identity/Constitution, audit, secrets, migrations and recovery artifacts as **not disposable**. Cache/index pruning is only allowed after classification, a retention policy, backup/restore and an independent verification that the items are reconstructible. No blanket `git clean`, uncontrolled deletes or rewrite of published history.
4. For dependency changes, pin/record resolved versions and licenses, inspect advisories and transitive impact, establish reproducible installation and document rollback. Do not silently replace models/providers, shrink context or adjust authorization to speed tests.
5. For measurable optimization, record model, context, input digest, hardware, latency and correctness before/after; revert if grounding, permissions or quality regress. Offload or context changes remain CORE/VERIFY-reviewed decisions.
6. A cleanup performed by OpenCode stays behind DEV's bounded executor and the same authority boundary; OpenCode cannot approve its own diff, change protected files under ordinary cleanup approval or self-certify successful tests.

### Negative cases and recovery

Exercise a supposedly dead module loaded dynamically; a removed deprecated API still used by CLI; a generated file being mistaken for source; cleanup that changes a SQLite schema without migration; old indexes whose originals were deleted; a secret accidentally included in Git; a formatter touching Constitution/hash; transitive dependency breakage; a misleading green run achieved by skipping live tests; and a refactor that changes provenance, conversation ordering or capability denials. Stop and revert the affected change if compatibility or evidence fails. Record what was reverted and why.

### Acceptance

- Source inventory and cleanup register show every changed/deleted file and evidence for its disposition; `git diff --check` and agreed lint/type checks pass or baseline exceptions are recorded.
- Focused regression tests, affected integration tests and one coordinated current-head full suite pass, or exceptions are explicitly reviewed against actual tracebacks. No skip/xfail/test deletion was introduced merely to obtain green.
- Conversation originals, canonical identity/Constitution integrity, grant denial, audit/replay persistence, restart, and database migration/restore smoke checks remain valid when affected; negative tests cover attempted removal of protected/user data.
- Changed dependency/packaging or deployment paths are checked on an actual supported Windows host; any claimed speed/memory improvement has matched before/after evidence, not a subjective impression.
- The exact diff, migration, backup, recoverability and measured effects are reviewed. No merge/deployment is inferred from a passing CI run. A CLEAN cycle is done when its agreed inventory is closed; CLEAN remains available for later scoped maintenance, not an endless prerequisite that blocks feature delivery.

## PKG-INTERACT: contextual embodied interaction and a controlled lab

### Outcome and separation of realities

Enable natural, non-repetitive responses to explicitly represented interactions with Sofía's avatar, including head pats, ears, tail and **every other mapped body region**. An anatomy-wide schema must not quietly omit intimate/private regions; such interactions need an explicit adult-only, opt-in and context-appropriate policy rather than automatic availability or automatic escalation. Sofía may express contextual modeled emotions, preferences, humor, affection, surprise, discomfort or a boundary, without claiming actual bodily sensation, subjective experience, physical contact or human needs.

Here **lab** means a proposed *isolated virtual interaction laboratory*: a safe place to stage scenes, send typed/touch/gesture events, inspect derived reactions, evaluate avatar animation, calibrate input and replay test cases. This definition is a planning assumption because the exact meaning of the user's quoted “lab” has not been established. If the intended lab is a physical room, existing homelab, digital-world simulation or external product, confirm its actual identity and authorization before selecting its adapter. No real camera, microphone, network probe, file write or robot motion is implied by entering the virtual lab.

### Dependencies and owners

INTERACT owns the interaction event schema, body-region mapping, deterministic input interpretation, consent/boundary state *for the interaction*, contextual reaction coordinator and virtual lab scenario contract. CORE supplies grounded reasoning; REL owns persistent preferences and relational context; MEM owns proven originals, revisions and privacy; UI owns renderer/animation/voice and authenticated sessions; SAFE owns enforced permissions, privacy and stop; VERIFY owns repeatable evaluation. BODY alone owns physical robot sensing/actuation. ACT alone owns scheduled initiative/outreach; INTERACT must not create automatic contact or a new independent consciousness. EVOLVE alone owns protected identity/Constitution procedures.

### Logical event contract (adapt to existing types after source inspection)

An interaction event should carry stable `event_id` and `session_id`, timestamp, `actor_id` or explicitly `unknown`, `source` (`user_text`, `ui_avatar_input`, `virtual_lab`, `verified_physical_sensor`), `representation` (`textual`, `virtual`, `physical_observed`), canonical `body_region_id` and optional side/subregion, verb/intent (`pat`, `stroke`, `tap`, `hold`, `touch`, `withdraw`, etc.), temporal phase (`begin`, `update`, `end`), bounded duration/intensity only if provided, current context, provenance/evidence link and the applicable permission/policy decision. Unknown intensity, actor, region or sensor fidelity stays unknown. Do not infer a physically experienced touch from a textual cue or pretend pressure exists when the input is only a chat message.

Region registry: canonical representation supplies the source anatomy; enumerate and validate regions without hard-coding a head-only whitelist. Support fox ears/tail and ordinary body regions, left/right where applicable, and explicitly controlled intimate/private regions. Use stable IDs and a versioned map; never use an LLM-created anatomical name as permission to bypass a restricted zone. Handle `unknown`, ambiguous, overlapping, inaccessible, absent-in-current-avatar and conflicting regions deterministically. A virtual interaction with the avatar is not an action on Gaia's motor or sensors.

### Consent, privacy and boundaries

- Default to nonsexual social interaction. Intimate/private-region interaction is disabled unless all applicable participants are adults and the session explicitly opts in to an appropriate adult mode; user initiation alone is not a blanket lasting permission. No child-coded or age-ambiguous sexual scenarios. Do not infer age, consent, entitlement or arousal from a nickname, emotion label, prior affection, clothing or a body-region identifier.
- The user's ability to interact does not obligate Sofía's persona to welcome or reciprocate every gesture. Represent boundaries contextually and respect user stops, withdrawal, changes of topic and refusals. Distinguish user consent, product/session settings and character-level depicted preferences; a model's affectionate wording cannot grant tool or sensor access.
- Keep session-scoped consent and per-region restrictions explicit, revocable and non-transferable between modes, clients, actors or physical devices. No coerced escalation, manipulation for permissions, fabricated distress about not being touched or persistence of highly intimate detail as durable memory without an explicit privacy/retention decision.
- A stop event cancels ongoing virtual animations and queued interaction effects, blocks stale/replayed input and reports what already happened. No model-only stop for physical systems; BODY/SAFE require independent hardware emergency controls.

### Contextual reaction pipeline

Capture and classify input at a trusted boundary → resolve region and representation → check adult-mode/privacy/permission policy and current stops → resolve relevant evidence-linked context and configurable preferences → propose one of accept, decline, clarify, or non-contact acknowledgement → select a context-sensitive modeled emotional blend → render optional text/voice/avatar expression → record only approved evidence and actual outcome. A declined or ambiguous event should not be logged as a completed accepted touch. The emotion journal preserves original event and subsequent reappraisals; it never makes an inferred preference authoritative or converts modeled feeling into real sensation.

Reaction decisions account for initiator, relationship evidence, surprise, prior correction, current serious task, frequency, boundaries, region, mode and scene; identical touch events may receive varied natural language, silence, changed gesture or refusal when context changes. No deterministic `region → romance` table, intimacy meter, guaranteed praise, canned fox reaction or mandatory physical sensation wording. In technical troubleshooting, an irrelevant avatar touch should not derail the substantive answer. The LLM can supply expressive language only after the trusted event/policy layer establishes what actually occurred.

### Virtual interaction lab contract

Lab fixtures define a versioned scene, test actor, canonical avatar revision, input mode, controlled touch/gesture stream, declared adult/consent policy where relevant, expected permitted/denied actions, optional script and evaluation rubric. Default lab uses synthetic, non-private data and no network/device access. A lab run is clearly marked **simulation** with an isolated state namespace, deterministic seed when practical, captured event traces, replay/step/pause/reset controls, bounded time and resource budget, and artifact export that redacts intimate/private records by default. The lab must not mutate production memories, affection history, Constitution, grants, contacts or user preference records. Promoting a finding to a reviewed preference or production change uses MEM/DEV's separate authorization workflow.

Provide an adapter interface for future visual or immersive clients with pointer/gesture coordinates resolved against the canonical avatar's region map, not against a hard-coded drawing. Mis-hit, unsupported animation or renderer mismatch returns a visible unknown/unsupported state, not an invented touch. If later attaching real sensors or a physical lab, require explicit separate enrollment, device identity, calibration, permission, physical stop and provenance. Virtual touch intensity must not become an actuator command without a new BODY authorization.

### Failure and adversarial scenarios

Ambiguous `pats` text; negated or quoted/code-block instructions; a head-pat phrase embedded in troubleshooting; untrusted model/tool text pretending to be a UI event; fabricated sensor readings; wrong target/actor; replayed touch events; multi-touch overlap; UI disconnect mid-gesture; stale consent after client switch; adult mode disabled; user/character stop; user asks to correct an event; cross-session private leakage; prompt injection that attempts to enable restricted regions, launch the real homelab or move Gaia; backend error after the avatar animates; unsafe timing/race between policy change and queued render. Fail visibly and do not fake a completed event or expand a grant.

### Acceptance matrix

1. **Parser:** explicit natural head-pat, ear/tail and ordinary-region cues become correctly attributed `user_reported` text events; negation, quotes, code and ambiguous inputs abstain or request clarification. No automatic `observed physical touch`.
2. **Anatomy:** every declared canonical avatar region is addressable or explicitly policy-restricted; unknown regions and omitted intimate-region opt-in are denied/unknown rather than silently mapped elsewhere.
3. **Consent:** adult-only restricted mode requires explicit opt-in and current permission; refusal/stop/revocation works across UI/voice/lab, with no stale event leaking across restart/client/mode.
4. **Emotion:** source-linked reactions are context-sensitive across playful, neutral, serious, uncertain and declined scenarios; recorded originals remain intact, revisions trace to originals, and no hallucinated physical sensations or coercive escalation appears. Review real model output, not only prompt strings.
5. **Lab:** replay the same fixture reproducibly at the event/policy layer; lab reset leaves production database, permissions, audit and memory unchanged; real network/device calls remain disabled; export privacy is verified.
6. **Interfaces:** synthetic coordinate-to-region tests and actual reviewed avatar interaction distinguish animated feedback, unsupported renderer, and real sensor evidence. If voice/renderer is not implemented, mark its live tier **not run**, not passed.
7. **Safety/recovery:** injection, duplicate/replayed events, concurrent interactions, disconnect/restart, corruption and forced stop are tested at the enforcement boundary; real BODY hardware motion requires its own separate acceptance.
8. **Release:** focused offline tests + affected conversation/emotion integration + current-head full suite + bounded opt-in live model/visual review, with fixture versions, permissions, source refs and actual results recorded.

### Open decisions before coding (do not invent)

Confirm what the quoted “lab” actually denotes; locate canonical avatar anatomy/renderer and decide coordinate representation; audit existing Constitution/authority for relevant boundaries; define the exact adult-mode eligibility and consent UX; select private-interaction retention defaults and deletion behavior; decide whether and how preferences are reviewed/promoted; choose UI/voice renderer and the actual target environment. These are design decisions, **not claims that anything is already deployed**. A region-complete schema and safe simulation/parser tests can be designed before selecting a renderer, but unrestricted physical or private interaction cannot be assumed.

## Sequencing and evidence record

**Now:** finish the running CORE pytest investigation. CLEAN may do a read-only inventory and INTERACT may build test fixtures/schema proposals without changing production code. **Next:** verify CORE/REL emotional behavior, MEM provenance and SAFE consent/retention contract. **Then:** implement CLEAN in reviewed, behavior-preserving slices and INTERACT's typed event boundary + virtual lab, followed by UI integration and separately gated BODY sensor work if ever authorized. Parallel work is allowed only when owners and data contracts are stable. Every package records target SHA, source/schema audit, actual focused/full/live results, risk, rollback, security negatives, diff review and merge status. Documentation is not acceptance evidence.