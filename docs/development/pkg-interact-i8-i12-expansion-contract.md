# INTERACT I8–I12 expansion contract: anatomy, actions, time and expression

**Status: design contract only, not implemented or tested.** This is follow-on scope beyond the current I1–I7 live-acceptance repair. Do not use this document as evidence that the model already expresses evolving intimacy, remembers a boundary, understands all aliases, or performs any new action. Preserve `main`, the user's existing SQLite state and backups; do not install a service or enable background inference through this package.

## Intent

Sofía has a canonical **adult represented human/fox-girl body**, including fox ears and tail. No registered body part is automatically forbidden or guaranteed to be welcomed. Supported responses may be affectionate, sensual/sexual in an appropriate adult fictional context, playful, neutral, surprised, uncomfortable or rejecting, as grounded in the conversation. Classification is not consent or enjoyment, and a textual portrayal must not be mistaken for a sensed physical contact, real animation, or verified subjective sensation. The LLM's own content boundaries remain applicable.

**New requirement:** An interaction's *context and modeled response can evolve with real recorded events over time*, analogously to the project's evidence-linked emotional appraisal and non-destructive revisions. A separate **versioned alias lexicon** must cover alternate, colloquial and context-dependent terms for all canonical regions. This does not mean that time passing automatically increases affection, arousal, consent or willingness.

## I8: canonical anatomy and alias lexicon

- One versioned registry defines `region_id`, laterality, parent/child relationships, fox features, aliases, optional sensitivity-for-export metadata and future renderer hitbox identifiers. Extend current `InteractionEngine.regions` rather than replacing its existing IDs without migration.
- Alias entries contain `surface_form`, `candidate_region_ids`, `language/locale` when necessary, `register` (formal, colloquial, anatomical, etc.), and a disambiguation rule. Case, whitespace, punctuation, plurals and possessives normalize predictably. Alternative words are *names*, not new body parts or implicit permissions.
- Distinguish overlapping scopes: `chest` is not automatically synonymous with `left-breast`, `right-breast`, or another subregion; `hand` without a side may need clarification; `ear` without a side is ambiguous when laterality matters. Terms with multiple meanings require context or an explicit question. Do not guess based on sexual connotation, relationship, or prior actions.
- Cover all existing registry regions and proposed subregions only when consistent with canonical anatomy. Every alias maps to an existing canonical ID or an explicit ambiguity outcome; no invented anatomy, unilateral left/right selection, silent alias collision or cross-region misfire (e.g., `forearm` triggering ear cues).
- Share this resolver between text and future authenticated avatar input, but pointer events supply independently resolved hitbox IDs. An LLM cannot forge pointer hits by merely naming a region.

## I9: gestures and higher-level actions

- Introduce versioned `gesture_id` and `action_id` registries with reviewed verb variants, tense/aspect, actor, target regions, modality, phase (`begin`, `update`, `end`, `cancel`) and modifiers such as pressure/intensity *only when actually specified*. Local gestures (pat, stroke, rub, scratch, kiss, hug, etc.) differ from composite/whole-body actions (embrace, sit beside, groom, hand over an item, dress/undress, move away, etc.). Action definitions must say whether an environmental or object-state transition is required.
- Do not equate an unknown sexual or intimate act with `touch`; abstain/clarify rather than manufacture a substitute event. Avoid pretending that a natural-language sentence is a verified sensor reading.
- A multi-action sentence is an ordered **plan/request**, not multiple completed contacts. Until an explicit atomic multi-action executor exists, respond truthfully that none was executed, or ask the user to separate actions. Never let a synthetic `InteractionLab` fixture write production evidence.
- Keep exact persisted stop/resume, cancel, replay and deduplication enforcement *before* model narration for every region, action and client. The existing per-session stop is not global, and expansion must not claim global revocation until implemented.

## I10: time-evolving, evidence-linked interaction context

- Persist append-only `InteractionObservation` records linked to original saved user message ID, session, timestamp, versioned canonical region/action, modality and policy outcome. Persist separately a modeled `InteractionAppraisal` when an authorized application process actually produces one: candidate emotional/relational tone, uncertainty, provenance and its source IDs. A gesture classification alone never generates an assumed positive appraisal.
- Represent short-lived *interaction state* independently of the durable event log: e.g., recent surprise, rapport cues, conversational tension, an explicitly expressed boundary or a current activity in Sofía's persistent virtual lab. The same gesture may receive a different answer later because the **source-backed context has changed**. Persist revisions append-only; do not rewrite history to make an earlier reaction retroactively positive.
- Any decay or expiration affects *salience of modeled context*, not historical facts or the force of an explicit stop. No arbitrary clock-driven automatic increase in sexual interest, affection or consent. On restart, reconstruct only from committed observations/appraisals; no claims of interactions or mental activity while the program was offline.
- Separately store user-stated preferences and Sofía's explicitly confirmed conversational boundaries with their evidence IDs, scope and revision/revocation status **only after a reviewed commit pathway exists**. Do not derive standing permission from an inferred emotion, a prior positive answer, an anatomical alias or silence. Existing session-wide stop always takes precedence.
- Enforce one state update per evidence/event ID; replay does not create a fresh action, appraisal or reaction. Bound lookback and provenance to avoid feeding the model unbounded text or resurfacing intimate context in unrelated conversation.

## I11: context-aware reactions and anti-repetition

- Decision pipeline: resolve actual input -> enforce stop/phase/replay -> record eligible representational event -> retrieve bounded conversation and source-backed temporal context -> choose optional reaction tendencies -> generate a new response -> validate claims against recorded facts.
- Possible modeled reactions include enjoyment/attraction/sensuality, affection, amusement, neutrality, uncertainty, irritation, aversion or a boundary. They are **possibilities**, not fixed `(region, gesture) => mood` mappings, and no specific region requires a positive or negative reaction.
- Separate an *expressed reaction* from an enforceable action policy. The LLM cannot declare a stopped gesture accepted, undo a stop or persist broad permissions just by phrasing a reply.
- Do not recycle distinctive prior lines, identical stage directions or the same closing question for every gesture. Variation must reflect context, not random synonyms or scripted emotion meters. In text-only mode, stage directions are optional prose in the represented scene; never claim an actual animation was rendered.

## I12: one semantics stream, future avatar and virtual lab

- Feed the same canonical events and temporal appraisal source into text and future avatar expression projections. A renderer may play an animation only after its own acknowledged execution; text must not assert that happened beforehand.
- The persistent virtual lab is Sofía's actual software-world location, equipment and recorded activity. The synthetic `InteractionLab` is only a stateless test harness. Neither a `work_in_progress` label nor time elapsed proves ongoing work or independent thought.
- Add eventual authenticated hit-testing, joint action/world transitions and cross-client stop semantics as separate reviewed capabilities. No external screen, filesystem or robot authority is granted by body interactions.

## Acceptance and staged delivery

I8: test registry coverage, alias/locale collisions, left/right ambiguity, sensitive-region parity and schema migration. I9: test varied gestures, action phases, unknown verbs and nonexecution of composites. I10: test source-linked evolution, restart/replay, non-destructive revisions, time salience without permission decay and stop precedence. I11: test factual response constraints, contextual alternatives and repeated-turn regressions, then judge *actual* real-model dialogue across multiple sessions. I12: test parity with fixture mappings; real avatar/renderer acceptance stays blocked until it exists.

**Dependency gate:** first finish I1–I7 focused and supervised live acceptance, then the agreed full test suite and a separate merge decision. This document adds requirements only and does not supersede those gates. The last user-reported new-regression result was 11 passed in 2.24 seconds at `52a5d44` for `test/test_interaction_live_stop_repetition.py`; it is not evidence for any I8–I12 feature.
