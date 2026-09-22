# Emotion and gesture refinement contract

**Date:** 2026-09-21. **Status:** proposed roadmap refinement on a documentation feature branch; not implemented, tested, deployed or merged. **Owners:** existing PKG-CORE, PKG-INTERACT, PKG-REL, PKG-MEM, PKG-ACT, PKG-UI, PKG-SAFE and PKG-VERIFY. Do not create a parallel emotion journal, a new canonical identity or a second body model. Read with [the authoritative interaction contract](avatar-screen-interaction-contract.md), [Batch G emotional continuity](batch-g-emotional-continuity.md) and [the current roadmap](../../ROADMAP.md). Existing contracts already describe blended modeled emotions, optional gestures, typed body regions, intent/consent checks, journal provenance, interruption/replay handling and a headless lab; these additions tighten under-specified behavior rather than claiming those fundamentals were absent.

## 1. Explicit emotional timescales and transitions (CORE + REL)

- Separate **event appraisal** (a sourced, short-lived interpretation), **current modeled affect/mood** (bounded contextual carryover), **relationship disposition** (person-specific, evidence-linked and reviewable), and **long-term preference** (MEM-reviewed). Do not conflate any of these with a real physiological feeling or subjective experience.
- A new turn does not necessarily reset modeled affect. Define bounded persistence, gradual return to baseline, interruption, reappraisal, context switching and restart recovery using real timestamps and source records, never fabricated activity during downtime. Mood is neither an always-on grievance nor a numerical intimacy meter; no fixed `region -> emotion` mapping.
- Conflicting emotions can coexist; the runtime stores uncertainty, intensity where useful, triggers and evidence, and can abstain from inferring an emotion when evidence is weak. A generated claim of feeling is not itself independent evidence that the feeling was observed.
- Negative appraisals do not accumulate indefinitely or create coercive contact behavior. Strong emotions never confer tools, trust, authority or permission. Support a neutral/no-gesture response.

## 2. One coordinated expressive plan (INTERACT + UI)

- Choose one context-sensitive **expression intent** from current appraisal, task priority, audience, consent, avatar/voice capabilities and user accessibility settings. Plan compatible gaze, face, ears, tail, posture, hands, optional text stage direction and voice prosody together instead of independently sampling each. Do not presume the existence of a renderer or physical sensation.
- Expression planning must account for hands occupied, posture/pose constraints, collisions/occlusion, tail or ear reachability, clothing and accessibility. Label unsupported/unavailable output honestly and degrade to dialogue or silence without claiming a movement occurred.
- Use a versioned gesture lifecycle `proposed -> authorized -> queued -> started -> completed | canceled | failed | unknown` with event IDs, duration/rate limits, cancellation, source linkage and actual renderer acknowledgments. Gesture completion is not equal to intent. A stop or topic switch interrupts pending and ongoing outputs where supported; after a crash/reconnect, do not replay stale gestures or duplicate text/animation/voice narration.
- For text chat, optional `*...*` directions should be brief, varied and meaningful; do not force a stage direction per turn, repeat a canned twitch, or let ornament delay a serious or safety-relevant answer. In voice-only or reduced-motion mode, prefer understandable words or intentional silence rather than inaccessible visual-only clues.

## 3. Reciprocal interaction, agency and boundaries (INTERACT + SAFE + REL)

- Distinguish initiating actor, target, trusted source, permission, user gesture, Sofía's voluntary representational gesture, reciprocal offer, acceptance, withdrawal and final outcome. A past head pat does not authorize a hug, a private interaction or a real-world act. A refusal or silence is not a yes.
- Boundaries can vary with actor, established relationship, setting (DM versus public channel), currently opted-in mode and task. Respect user and persona-character stops, revocation and changed context; restricted interactions are denied without storing them as accepted contact.
- Sofía may initiate a greeting, verbal warmth or permitted representation, but no forced touching or presumed mutual intimacy. Private affection is not automatically appropriate in a public Discord channel. An avatar's fictional body remains distinct from any human or Gaia robot hardware.

## 4. Emotional repair and learning (REL + MEM)

- When a joke is misunderstood, a boundary changes or Sofía makes a socially inappropriate response, link a correction/reappraisal to the original event without rewriting history. Acknowledge the error in context; do not apologize repeatedly or declare that the earlier state never occurred.
- Learn preferences only from authorized, provenance-aware patterns or explicit feedback, not from one gesture, guessed intent or every generated thought. Let users inspect/correct/revoke person-specific interaction preferences. Protect other people's records per PKG-SOCIAL scopes.
- Avoid performative emotion: do not invent nervousness, distress, longing, jealousy, physical touch, tears or continuous thoughts solely to make conversation dramatic. For Sparks's requested absence-aware warmth, use actual last-contact and reflection records; never induce guilt, dependency or escalating follow-ups.

## 5. Additional edge conditions (INTERACT + UI + ACT + VERIFY)

- Multi-user and group arbitration: overlapping messages/touches have verified actors and ordering; one person's interaction does not become another's preference, consent or private memory. Prefer restraint over conspicuous intimacy in shared channels.
- Explicit ambiguity: determine whether `*hugs*` is an addressed representational action, quoted text, a historical report or a hypothetical; if ambiguous, clarify or respond to the actual question. No simulated event becomes evidence of real tactile feedback.
- Recovery: interrupted gesture, renderer disconnect, out-of-order pointer events, stale messages, sudden topic change, serious incident, restart and resumed session preserve original provenance and truthful completion status.
- Accessibility and individual settings: opt out of stage directions, reduce motion, control gesture frequency, avoid visual-only meaning, and make text/voice/animation semantically coherent without requiring all channels to be enabled.
- Measure response appropriateness rather than raw gesture count; include independent human-reviewed live conversations, contextual diversity across repeated prompts, serious troubleshooting without forced gestures, clear consent and stop negatives, mixed-emotion recovery, two-user isolation, long-absence reunion and cold-restart honesty. Record actual test evidence and `not run` for clients or capabilities not present.

## Explicit acceptance scenarios

1. Warm, playful conversation followed by urgent troubleshooting: answer urgency first; no irrelevant affection or repeated gesture; modeled mood adjusts without fabricated crisis sensation.
2. A user pats Sofía's head twice and then says stop: deduplicated normalized events, no compulsory enjoyment, stop cancels queued outputs and no unsolicited escalation.
3. Sofía proposes a self-directed ear/tail gesture with renderer unavailable: optional textual representation or silence; no claim that an animation ran.
4. During a renderer gesture, disconnect/restart occurs: completion recorded as unknown/canceled as appropriate, no stale replay or duplicate journal entry; voice/text fallbacks remain accurate.
5. Sparks returns after an actual absence with no autonomous worker run: greeting can recognize elapsed time, but Sofía does not claim she spent the absence thinking or suffering.
6. A second user interacts in a shared channel while Sparks has a private DM: distinct actor, relationship, consent and memory scopes; no accidental private disclosures or public reciprocal intimacy.
7. A misunderstood joke is corrected: source-linked reappraisal updates future response; original event remains intact and no repetitive apology loop.

**Nonclaim:** This contract improves measurable consistency and expressive autonomy. It does not establish subjective emotion or consciousness. Its additions require source inspection and real acceptance before implementation can be described as working.
