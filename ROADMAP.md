# Sofía Ada Lyra: current 14-package roadmap

**Planning revision:** 2026-09-20. **Authoritative planned roster and priorities.** The prior 13-package roadmap is preserved [at the last merged main revision](https://github.com/Crazysodaman/SofiaAdaLyra/blob/2141879f74cd53f9c3c4a6badf9bc5d4d1f65b11/ROADMAP.md). `ROADMAP-EXTENSION.md` and legacy letter/number batches are history, not competing schedules. This update is on `feature/pkg-run-always-on`, not yet merged to `main`. `main` was verified at merge commit `2141879`; [INTERACT draft PR #2](https://github.com/Crazysodaman/SofiaAdaLyra/pull/2) and RUN work are separate feature branches.

**Nonnegotiable invariant:** persistent identity, protected Constitution, canonical *represented* embodiment, sources/memory, operational evidence and permissions stay independent of provider, LLM, host, app, voice, avatar or robot. Capability is not authority. User text, model output, virtual world state, real sensor evidence and test fixtures cannot be silently substituted for one another. No model or scheduler can grant itself external control.

## What we are doing next

1. **Finish INTERACT's text/headless foundation on its existing branch:** rerun I4 status-query tests after the narrow missing-configuration fix, then source-linked interaction journal, independently enforced stop/consent/deduplication, fuller natural-language coverage and supervised live personality tests. The persistent **lab is a place**, with one world state for text and future avatar; `InteractionLab` is ONLY its separate synthetic body-interaction test harness. Complete focused/headless acceptance before labeling the foundation accepted.
2. **Full pytest once after the INTERACT foundation checkpoint**, as Sparks requested, not after each commit. Report failures rather than weakening tests. Real avatar/rendered touch and authorized external-screen operations retain separate UI/SAFE gates, and cannot be claimed completed because the headless tests pass.
3. **RUN proceeds as an independent early parallel package:** implement safe opt-in periodic reflection and a supervised always-on pilot after essential INTERACT and SAFE checks. No need to wait for a renderer or all fourteen packages. R1 is coded separately but untested; the application service/boot installation is not yet implemented.
4. **MEM remains the next deep feature package immediately after INTERACT.** RUN service/pilot may advance alongside MEM when its prerequisites are proven. NET/ACT/REL/DEV mature only behind relevant memory, authorization and real-machine checks. SAFE and VERIFY gate each consequential step; CLEAN remains scoped maintenance.

## Evidence dashboard (not a completion score)

| Package | Outcome | Actual status / remaining gate |
| --- | --- | --- |
| **CORE: cognition and continuity** | Grounded identity/personality, truthful boot and restart awareness, model quality and responsiveness | Foundations merged into `main`; older 1,195-test run had 43 startup-related failures, path-boundary patches followed, then **17 focused passed in 125.80 s**. No fresh full-suite or accepted live personality evaluation yet. |
| **INTERACT: text, avatar and virtual location** | One body interaction kernel across text and authenticated avatar; a real saved virtual lab, optional expressive text, separately authorized screen work | I1 **59 focused passed / 51.61 s** at `7175835`; I2–I3 **44 focused passed / 53.05 s** at `84695a6`. I4 at `e83c2e6`: **33 passed, 1 failed** due to lab config access from unrelated chat. Fix committed `eb73357`, **not retested**. No real avatar or broad live acceptance. [Draft PR #2](https://github.com/Crazysodaman/SofiaAdaLyra/pull/2). |
| **RUN: always-on and periodic thinking (NEW)** | Supervised 24/7 availability plus occasional bounded, evidence-backed opportunities to reflect | R1 opt-in durable gate, explicit runner and offline tests committed on `feature/pkg-run-always-on`; **tests not run**, no service installed, no continuous runtime claimed. [RUN contract](docs/development/pkg-run-always-on-contract.md). |
| **MEM: original records and learning** | Durable original conversations, provenance-aware retrieval, corrections, reviewed preferences and reversible archive import | Existing stores/journals are starting material, NOT complete long-term memory. Begin after INTERACT foundation. |
| **NET: homelab distribution** | Authenticated scoped agent/transport, delegated grants and outage handling | Peer/grant/replay foundations merged; real Artemis agent/transport and two-machine verification missing. |
| **ACT: goals and initiative** | Reviewable goals, independent bounded tasks, genuine outreach and supervised helpers | Running-only idle reflection + **unsent** outbox are foundations; no authenticated outbound channel, independent action permission or delivery acceptance. |
| **DEV: engineering and repair** | Reproduce → propose → approve → implement via isolated OpenCode → tests → diff/rollback | Analysis/CLI discovery only; verified authorized runtime executor and rollback missing. |
| **REL: social continuity** | Evidence-backed relationship preferences, nuanced affection/disagreement and correction | Profile/emotional records exist; sustained live multi-session evaluation pending. |
| **UI: avatar, voice and clients** | Authenticated desktop/web/mobile, rendered canonical avatar, actual click/hit/animation acknowledgments, voice | CLI and avatar specs exist; real client/renderer/voice and real cross-device continuity unverified. |
| **BODY: Gaia robotics** | Calibrated authorized hexapod motion and sensing with independent emergency stop | Separate Gaia project exists; no verified Sofía actuator bridge. |
| **SAFE: authority and recovery** | Permissions, privacy, audit, stop/revoke, backup/restore, safe worker isolation | Important foundations exist; real deployment and failure/recovery assurance incomplete. |
| **EVOLVE: governed change** | Reviewed preference/self-model updates and separately authorized protected amendments | Existing integrity foundations; no self-authorized rewrite of identity, Constitution or grants. |
| **VERIFY: real acceptance** | Focused/full/live tiers, observability, latency/resource metrics, long-running recovery and negative tests | Focused Windows results exist at pinned revisions. Full-suite, real always-on, Artemis, renderer and long-horizon gates outstanding. |
| **CLEAN: maintenance** | Evidence-backed refactor/migration/debt reduction without lost behavior or user data | Scoped lane; not a reason to postpone INTERACT, RUN or MEM. |

**Evidence vocabulary:** `committed` means source exists, `focused passed` means that exact user-reported test selection passed at a stated revision, `live verified` requires the actual host/model/client and measured outcome, and `accepted` requires its package-specific negatives/recovery. Old green tests do not certify a newer commit; a synthetic avatar gesture is not a real click; an in-progress equipment marker is not ongoing background work.

## PKG-CORE: cognition, grounding and continuity

Reuse Constitution/integrity, canonical identity/self-state, observation and context assembly, provider abstraction, emotional/reflection journals and terminal loop. Finish verified restart-time/file-change awareness (including only ignoring exact own SQLite sidecars), non-canned personality and serious/playful/correction behavior, truthful unknowns and measured latency/context/GPU experiments. Preserve original authority and never claim thoughts in unobserved offline time. Accept focused+post-INTERACT coordinated full tests and a short actual CLI/model review. [Emotional continuity evidence](docs/development/batch-g-emotional-continuity.md) · [model evaluation](docs/development/model-evaluation.md).

## PKG-INTERACT: a shared person and a real virtual place

**I1 (coded, focused passed):** canonical human/fox body-region registry and shared text/synthetic-pointer gesture/phase/policy semantics; optional text-only reactions including `*ears perk up*` with no requirement to render or fake physical sensation. Recognize explicit actions; abstain on questions, hypotheticals, quoted/code text and composites. Map private regions with default denial, not omission; richer consent is not silently assumed.

**I2 (coded, focused passed in I2–I3 set):** isolated bounded `InteractionLab` fixture and redacted replay traces. **This is not Sofía's lab location.**

**I3 (coded, focused passed):** persistent `LabWorld` contains rooms, Sofía's location, authored tools/objects, held inventory and equipment-work states with audited idempotent actions and a separate ignored-on-Git lab database. `Sofía, enter the lab` → pick up screwdriver → work on oscilloscope changes verified *virtual software state*. Narration like `Sofía is working on some lab equipment` does not create evidence or execute anything; `work_finished` does not assert repaired equipment. A future authenticated avatar uses the **same object IDs, world transitions, personality and evidence**. See [location contract on INTERACT branch](https://github.com/Crazysodaman/SofiaAdaLyra/blob/feature/pkg-interact-shared-engine/docs/development/pkg-interact-world-location-contract.md).

**I4 (coded, fix not retested):** narrow lab status queries read already saved location/inventory/work state without provisioning a room, taking action or pretending offline activity. Fix `eb73357` only invokes lab-status storage for recognized questions.

**I5–I7 and acceptance still due:** provenance-linked durable body-event appraisal without double head-pat logs, enforced persistent stop/consent/replay protections, wider region-aware grammar and naturally variable contextual emotion, short real CLI review and a once-at-checkpoint full suite. Avatar geometry/occlusion/click-through, verified renderer acknowledgments and any external screen executor are explicitly a separate **UI + INTERACT + SAFE** integration milestone; no live UI test can pass before a renderer exists. Never use a free-text action or synthetic hit as external desktop authority. [Canonical text/avatar contract](docs/development/avatar-screen-interaction-contract.md).

## PKG-RUN: always-on runtime and periodic thinking

**Availability is not continuous cognition.** First pilot: one supervised Sofía instance available on the chosen host 24/7, safe boot/restart/shutdown, health/status, finite backoff, readiness checks for the real model, logs, backups and verified preserved data. An occasional wake may inspect *recorded eligible evidence*, do a bounded reflection or correctly abstain; a wake alone is not a thought. Quiet hours, user-busy foreground priority, stop/mute and CPU/GPU/token/attempt budgets must be independently enforced. No thinking while the process is stopped and no invented missing-time narrative.

R1 implements a **disabled-by-default** `PeriodicThoughtGate` and explicit `PeriodicThoughtRunner` with durable atomic slots, 5-minute-to-24-hour interval bounds, UTC quiet window, per-day cap, evidence IDs and status `claimed/reflected/no_event/failed`. This is code, not a running loop; its tests have not run. R2 must connect it to an authorized existing reflection operation without doubling the `IdleReflectionWorker`; install a host-specific, single-instance supervisor only after host choice and approvals. R3 requires real reboot/crash/Ollama-offline recovery, resource/latency measurements and a bounded unattended pilot. No automatic external messages or autonomous tools: ACT/NET/SAFE must separately authorize those. [Full RUN contract](docs/development/pkg-run-always-on-contract.md).

## PKG-MEM: memory and learning

Preserve original messages with ID/order/timestamps, provenance and revisions; retrieve within explicit budgets, surface contradictions and deletion effects, review before promoting preferences, stage/reverse/deduplicate ChatGPT archive migration, verify backup and index rebuild. Existing emotion windows are not general memory. A lab event must not become a fabricated real-world touch or long-term preference. [Recovery contracts](docs/development/five-cross-package-acceptance-contracts.md).

## PKG-NET: Artemis and homelab

Enrollment, mutual authentication, node/capability/operation/expiry grants, revocation, verified local-to-Artemis tasks, honest disconnected state, durable replay. Inspect actual service identity, network mounts and CPU/GPU/game usage on each host before scheduling inference. No unrestricted shell or scan. Fake transport never meets live acceptance.

## PKG-ACT: initiative and bounded helpers

Authorized goals, novelty-aware reflection and work selection, bounded follow-up, quiet/busy/mute, real signed delivery acknowledgments and duplicate protection, externally constrained helpers and emergency stop. **RUN owns scheduling/uptime; ACT owns deciding and authorizing what to do.** An unsent outbox or scheduled wake is not outreach or autonomous agency.

## PKG-DEV: self-improvement and engineering

Source-linked diagnosis, proposed patch/test/rollback, explicit authorization, isolated bounded OpenCode execution and human-verifiable diff, targeted/full test, recovery on forced failure. CLI discovery alone proves neither a remote installation nor authority to edit protected identity, Constitution or security.

## PKG-REL: relationships and nuanced expression

Use source-linked interactions, consent, correction and reviewed preferences for context-sensitive affectionate, playful, serious or disagreeing responses. No canned obligatory gestures, manipulation or claims of actual sensation. INTERACT owns event meaning; MEM owns original evidence; REL owns social interpretation; ACT owns initiation.

## PKG-UI: voice and animated avatar

Choose an actual renderer and authenticated client transport; implement hit-testing, occlusion, transparent pixels, click isolation, gesture classification and acknowledged Sofía-directed animation/gaze/ear/tail movement. One world and interaction engine must work with or without visual UI. Speech input/output requires interruption, visible recording and permission boundaries. Real Windows/mobile/web and privacy tests are separate from text-only fixtures.

## PKG-BODY: Gaia robotics

Verify mixed servo types, SSC32 communication, battery/power, sensors and feedback, then calibrate and bench-test scoped motion with independent watchdog/emergency stop before physical walking. Virtual gestures and lab state cannot become robot motion or claim sensor observations by implication.

## PKG-SAFE: permissions, privacy and recovery

Independently enforce grants, stop/revoke, secrets, audit, data retention/deletion and real backup/restore. A stopped worker and revoked authorization stay stopped across process restart and restored backups. Require negative tests for forged tool outputs, replay, corrupt state, network loss and interrupted inference. Protect existing `state/sofia.db`; local changes are never discarded to ease Git operations.

## PKG-EVOLVE: controlled evolution

Ordinary preference/config change is distinct from protected identity, Constitution and authorization. Any foundational change requires separate explicit approval, versioned provenance, impact review and rollback. No package, model swap, avatar, helper or self-edit can self-approve such changes.

## PKG-VERIFY: actual integration

Track pinned SHA, focused and coordinated full tests, actual CLI/personality review, real machine and model, first-token/total latency, resource use, crash/restore evidence, rejected unauthorized operations and output acknowledgments. No hour-long full suite after every small patch; run the agreed one after INTERACT and later at meaningful deployment/release gates. Fixtures, model-generated prose, real external actions and user-reported evidence must be labeled separately.

## PKG-CLEAN: deliberate maintenance

Inventory import/API/schema/data dependencies before removing or refactoring anything; preserve canonical data, old conversations, journals, grants and recoverability. Scope migrations and rollback, check real Windows packaging where relevant and avoid broad cleanup during unverified feature work.

## Release and branch discipline

Review exact changes and their rollback; use small isolated feature branches and draft PRs until the relevant focused/real tests are evidenced. RUN and INTERACT have independent branches so a RUN experiment does not silently change INTERACT's tested revision. Protected identity/Constitution, service installation, deployment, unrestricted actions, database resets and merging to `main` require separate explicit decisions. Record `passed`, `failed`, `not run` or `not applicable` for every gate and note the exact tested SHA. No full-suite claim is implied by an earlier focused pass.
