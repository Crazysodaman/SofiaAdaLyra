# V18 Phase 08 personality and emotion integration

Status: implemented source slice; local verification recorded below; **not Gate 4**.
Pinned CI, independent review, Windows host rendering, microphone/TTS playback,
and live provider dialogue evaluation remain separate acceptance requirements.

## Canonical ownership map

| Concern | Canonical owner | Production path | Authority boundary |
|---|---|---|---|
| Stable identity/personality | `identity`, Constitution, `personality/personality.json` | composition → cognition context → response renderer | Style cannot revise identity, truth, SAFE, or permissions. |
| Short affect | `emotion.EmotionalJournal` plus stateless projection | saved conversation/LIFE evidence → journal → decayed `CurrentEmotionalState` | Confidence only reduces contribution; emotion is never evidence, consent, or authority. |
| Historical episodes | `emotional_events` and append-only revisions in `sofia.db` | explicit scoped history query/reflection | Historical presence does not make an old mood current. |
| Relationship continuity | REL, social principal/audience bindings, conversation history | authenticated session → relationship scope; shared audiences stay exact-audience scoped | Display names and model text are not principals. |
| Tentative user affect | session-local `UserAffectTracker` | validated hidden response envelope → next-turn calibration | Not durable memory; correction clears inference without inventing a replacement. |
| Environment/time | ENVIRONMENT snapshot → `ContinuityInfluence` | current evidence → personality/expression planning | Weather, season, and clock color style; they do not manufacture emotion. |
| Project experience | LIFE `ExperienceRecord` | canonical experience → bounded emotion bridge → exact audience episode | Only typed, evidence-referenced artifact creation/evaluation is eligible. Pause, failure, abandonment, and inactivity do not manufacture negative affect. |
| Personality modulation | `derive_expression_modulation` | Matrix + grounded affect + eligible NEURO workspace + authenticated style preferences | Non-authoritative wording/style weights only. A NEURO winner is not copied into emotion. |
| Expression intent | `ExpressionRuntime` | settled assistant text → one decision with prosody, face/gaze/ears/tail/gesture/pose and evidence refs | `ExpressionIntent.can_authorize` is always false. Intent is not output proof. |
| Voice/avatar execution | TTS receipt listener and desktop avatar callback | backend outcome → independent typed receipt | Only `spoken` and `rendered` receipts acknowledge output; queueing/text do not. |
| Reflection | `ReflectionJournal` and `ThoughtAgent` | selected scoped event → bounded reflection → optional new inferred appraisal | Reflection is a hypothesis and cannot create facts or protected action authority. |

## Task mapping

- CA-501: the existing stable profile/Constitution projection remains canonical;
  Matrix/personality modulation supplies evidence-grounded skepticism, warmth,
  humor, and reciprocity without changing factual claims.
- CA-502/CA-509: real LIFE artifact outcomes can now create idempotent,
  source-linked, audience-private appraisals. ENVIRONMENT and eligible NEURO state
  affect expression only. Optional project failure/inactivity is deliberately inert.
- CA-503/CA-6002: durable episodes and current decayed affect remain separate;
  exact-audience LIFE episodes join principal relationship continuity only for the
  authenticated viewer after restart.
- CA-504/CA-507: one durable expression decision now carries source evidence,
  active signals, voice prosody, and component avatar state with a five-minute
  live intent window.
- CA-505: the existing independent text/TTS/avatar receipt paths are retained;
  component intent cannot claim rendered or spoken output.
- CA-506: the existing provider quality gate detects canned handoffs, repetitive
  self-reports, stacked stage directions, exaggerated physical sensation,
  unsupported activity, and ungrounded temporal emotion claims.
- CA-508: a typed adapter over the existing preference registry supports
  authenticated Sparks overrides for humor, verbosity, and disagreement, scoped
  to one audience and revisioned with evidence.
- CA-6001: this document records the audited source-to-sink integration.
- CA-6003: emotion rows now retain actor, channel, exact social scope, consent
  classification, confidence, correction linkage, and related project IDs.
- CA-6004: existing half-life decay and observed-at absence/reunion logic remain;
  shutdown time creates no backdated emotion.
- CA-6006: user affect remains ephemeral and separate from Sofía's journal;
  explicit corrections remove contradicted inference without diagnosing a new one.
- CA-6009: confidence cannot increase affect, and expression exposes no capability,
  permission, receipt, or authorization operation.

## Local evidence

Baseline before the implementation slice:

```text
109 passed, 3 skipped
```

Focused source-slice verification after implementation:

```text
349 passed, 3 skipped
22 passed (loopback mobile/desktop integration)
43 passed (avatar/UI reconciliation; one loopback case was verified above)
```

The broader non-integration REL/AVATAR/VOICE/SOCIAL marker sweep reached
`2039 passed, 4 skipped, 5 failed`. The five failures are in concurrently landed
avatar batches outside this source slice: three fixtures omit the required
canonical SQLite bootstrap, one generated public wardrobe catalogue is missing a
source category, and one permanent-anatomy request is misrouted to clothing. They
remain current-`main` blockers and are not reported as Phase 08 passes.

The exact final commands and counts are recorded in the completion report for the
commit. These local results do not establish live renderer/audio output, provider
quality, CI acceptance, or Gate 4.
