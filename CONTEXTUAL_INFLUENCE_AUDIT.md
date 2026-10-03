# Sofía Ada Lyra — Contextual Influence Audit

**Updated:** 2026-10-02  
**Scope:** current `main` code audit of where **emotion, weather, time/daypart, and season** currently influence Sofía's choices, where they should influence choices, and where they must remain excluded.

## Core rule

The influence set is:

```text
EMOTION
WEATHER
TIME / DAYPART
SEASON
```

These are **contextual influences**, not authorities.

They may shape:

- preference;
- salience;
- tone;
- timing;
- presentation;
- style;
- expression;
- reflection;
- bounded social initiative;
- context-sensitive suggestion.

They must never by themselves establish:

- truth;
- consent;
- authority;
- permission;
- private-presentation grants;
- execution rights;
- tool authorization;
- memory truth;
- durable preference;
- release acceptance;
- Fleet trust;
- safety override.

Missing or stale evidence means **no influence from that signal**, not a guessed replacement.

---

# 1. Recommended architecture

Add one cross-cutting **Contextual Influence Matrix** rather than four unrelated policy systems.

```text
Trusted source state
├─ modeled emotion
├─ current weather + freshness
├─ trusted local clock / daypart
└─ grounded season
        ↓
Contextual Influence Matrix
        ↓
decision-surface-specific policy
├─ NONE
├─ EXPRESSION_ONLY
├─ BOUNDED_BIAS
├─ STRONG_PREFERENCE
└─ HARD_COMPATIBILITY
        ↓
choice subsystem
```

The matrix should answer:

1. Is this influence allowed on this decision surface?
2. What evidence/freshness is required?
3. How strong may the influence be?
4. May it affect the decision itself, expression only, or neither?
5. Which invariant still wins?

The matrix must not commit any action or state by itself.

---

# 2. Current central influence object

`src/sofia/personality/influence.py` already provides a useful shared contract:

`ContinuityInfluence`

It contains:

- daypart;
- season;
- daylight;
- current weather condition;
- temperature;
- weather freshness;
- location freshness;
- modeled emotional tone;
- primary modeled emotion;
- emotion intensity;
- active emotions;
- emotion evidence references.

This is the correct source shape to reuse rather than inventing parallel weather/time/emotion structures for every subsystem.

Important existing invariant from that module:

> Time, season and weather are context, not commands. Emotion may influence thought style and salience but never validate a memory, habit, expectation, or external event.

---

# 3. Current influence map

Legend:

- ✅ already meaningfully wired
- 🟡 partially wired / indirect
- ❌ missing
- 🚫 intentionally should not influence directly

| Decision surface | Emotion | Weather | Time/daypart | Season | Current code state |
|---|---:|---:|---:|---:|---|
| General conversation tone/attention | ✅ | ✅ | ✅ | ✅ | `EmotionalConversationService` projects only matrix-allowed, evidence-backed influence |
| Automatic outfit selection | ✅ | ✅ | ✅ | ✅ | `WardrobeContext` + `OutfitPlanner` |
| User-requested outfit accept/decline/counter | ✅ bounded | ✅ strong/current | ✅ bounded | ✅ compatibility | `WardrobeAutonomyPolicy` receives trusted contextual influence and may accept/decline/counter-propose |
| Avatar style/expression/posture proposal | ✅ | ✅ | ✅ | ✅ | `propose_avatar_influence()` |
| Production application of avatar expression proposal | 🟡 | 🟡 | 🟡 | 🟡 | proposal logic exists; a full renderer/expression commit path remains embodiment work |
| Desktop adaptive theme | ✅ | ✅ | ✅ | ✅ | `ThemeSignals` includes season as a bounded visual cue |
| Reflection content / share now-later-none | ✅ | ✅ current | ✅ | ✅ | reflection planning receives evidence-backed weather/daypart/season/emotion |
| Reflection/outreach salience | ✅ | ✅ | ✅ | 🚫 direct | `outreach_salience()`; season remains intentionally non-direct |
| Quiet-hour delivery | 🚫 | 🚫 | ✅ | 🚫 | ACT policy uses trusted local timezone/clock |
| Interaction willingness / offer choice | ✅ bounded | 🚫 direct | 🚫 direct | 🚫 direct | explicit `INTERACTION_WILLINGNESS` signal whitelist |
| Interaction expression style | ✅ bounded | ✅ expression-only | ✅ expression-only | ✅ expression-only | explicit `INTERACTION_EXPRESSION` whitelist |
| HABIT observation context | 🚫 emotion | ✅ | ✅ | ✅ | conversation observations record daypart/season/daylight/current weather |
| HABIT learned conversation routine | 🚫 | ✅ bounded evidence | ✅ | ✅ bounded evidence | seasonal/environment correlations are learned only with sufficient evidence/coverage |
| Memory retrieval/ranking | ✅ weak | ✅ weak/current | ✅ weak | ✅ weak | hard promoted/principal/audience/query eligibility first, then bounded contextual tie-breaking |
| Social/interaction goal selection | 🟡 policy | 🚫 direct | 🟡 policy | 🚫 direct | influence surface exists; production goal-priority wiring remains behavior work |
| Cognitive LLM route | 🚫 | 🚫 | 🚫 | 🚫 | should remain task/route based |
| Fleet workload placement | 🚫 | 🚫 | 🚫 | 🚫 | should remain resources/trust/activity based |
| SAFE / authority | 🚫 | 🚫 | 🚫 | 🚫 | must remain invariant |
| VERIFY / release acceptance | 🚫 | 🚫 | 🚫 | 🚫 | must remain evidence/compatibility based |
| DEV correctness / code decisions | 🚫 | 🚫 | 🚫 | 🚫 | mood/environment must not change correctness |
| EVOLVE protected-state approval | 🚫 | 🚫 | 🚫 | 🚫 | transient context must not authorize durable self-change |
| Gaia/BODY physical safety | 🚫 | 🚫 | 🚫 | 🚫 | safety envelope must remain invariant |

---

# 4. Automatic wardrobe selection — already strong

The automatic wardrobe path is currently the best implementation of contextual choice.

`WardrobeContext` includes:

- trusted local `now`;
- typed season;
- activity;
- fresh weather observation;
- bounded emotion style influences.

`OutfitPlanner.suggest()` currently uses:

### Season

Season is a **hard compatibility constraint**.

An outfit not valid for the current grounded season is not eligible.

### Weather

Weather-specialized outfits receive a positive or negative score only when weather evidence is fresh.

Stale/future/missing weather cannot be treated as current.

### Time/daypart

Late-night windows strongly bias lounge outfits.

### Emotion

Emotion is intentionally bounded to a small style score and cannot override:

- activity;
- season;
- privacy;
- coverage.

This is the correct design pattern for the new influence matrix.

---

# 5. User-requested wardrobe autonomy — implemented

`ClothingActionService` routes a requested wardrobe transition through `WardrobeAutonomyPolicy`, and the policy now receives trusted contextual influence rather than treating user wording as authority.

The implemented flow preserves the originally recommended architecture:

```text
user wardrobe suggestion
    ↓
resolve candidate
    ↓
trusted current influence set
├─ emotion
├─ weather
├─ time/daypart
└─ season
    ↓
privacy / grant / coverage constraints
    ↓
WardrobeAutonomyPolicy
├─ accept
├─ decline
└─ counter-propose
    ↓
accepted transition only
    ↓
commit → persist → verify
```

Suggested policy semantics:

- season can be a strong compatibility signal;
- fresh extreme weather can be a strong practicality signal;
- daypart can be a moderate style/activity signal;
- modeled emotion can be a bounded preference signal;
- none of these override private-presentation grant requirements.

---

# 6. General conversation — already wired, but too globally

`EmotionalConversationService._build_request()` always constructs `ContinuityInfluence` and prepends its prompt when personality is active.

This means emotion/weather/time/season can currently influence general language and attention.

That is desirable in principle.

However there is a matrix interaction issue:

- `SofiaRuntime.respond(..., context_plan=...)` can selectively exclude `ENVIRONMENT`;
- the emotional conversation layer can then re-inject environment-derived continuity context in a separate system message.

So a matrix-selected environment exclusion does not necessarily mean weather/time/season disappear from provider context.

Recommended repair:

> Contextual influence projection should be gated by the same matrix/context plan, rather than injected unconditionally.

This is one of the strongest reasons to add a Contextual Influence Matrix.

---

# 7. Reflection — partial wiring

`ThoughtAgent.reflect()` receives `ContinuityInfluence`.

Its reflection payload currently includes:

- daypart;
- season;
- daylight;
- emotional tone;
- primary emotion;
- intensity;
- active emotions.

It does **not** include:

- weather condition;
- temperature;
- weather freshness.

Later, after the model returns a reflection decision, `outreach_salience()` *does* use fresh weather.

Therefore weather can affect the later salience score but cannot currently affect the model's own:

- reflection theme;
- share now / later / none choice;
- message phrasing.

Recommended repair:

- add only **current** weather condition/temperature to reflection influence payload;
- preserve explicit freshness metadata;
- stale/future weather projects as absent;
- weather may shape theme/salience, not manufacture causes or urgency.

Season should remain a reflective theme/context signal but should not directly create urgency.

---

# 8. Proactive outreach — mostly good

`outreach_salience()` currently uses:

- emotion intensity;
- selected emotion labels;
- daypart;
- daylight;
- current severe/mild weather.

ACT policy separately enforces:

- explicit enablement;
- mute/stop;
- recipient;
- evidence;
- busy state;
- quiet hours;
- cooldown;
- daily limits.

This separation is correct.

Influence should affect **salience**, not authorization.

Season should generally **not** directly affect outreach salience. Seasonal relevance should come through the underlying event/habit evidence.

Example:

```text
"first snow of the season" recorded event
→ event itself may be salient

winter merely existing
→ not a reason to message
```

---

# 9. Interaction willingness and expression — needs explicit separation

Current interaction prompts already distinguish:

- recognized action;
- boundary;
- stop state;
- willingness;
- modeled emotion;
- represented expression.

Current modeled emotional state can appropriately influence Sofía's present conversational willingness.

However weather/time/season are also available through general continuity context and are not explicitly separated from the choice stage.

Recommended matrix rule:

### Interaction willingness / accept-decline-boundary

- emotion: **BOUNDED_BIAS**
- weather: **NONE**
- time/daypart: **NONE**
- season: **NONE**

Explicit current conversation/boundary/stop state always wins.

### Interaction expression

- emotion: **STRONG_EXPRESSION**
- weather: **SUBTLE_EXPRESSION_ONLY when contextually relevant**
- time/daypart: **SUBTLE_EXPRESSION_ONLY**
- season: **SUBTLE_EXPRESSION_ONLY**

Example:

A rainy late evening may make Sofía's represented response quieter/cozier.

It must not turn:

```text
"I ask to hug you"
```

into an automatic accept because it is raining.

---

# 10. Avatar appearance/expression — good proposal logic, incomplete production embodiment

`propose_avatar_influence()` currently maps:

- daypart → style/posture;
- season → style tags;
- daylight → style tags;
- fresh weather → style tags;
- emotion → expression/posture.

This is a good bounded influence function.

The main limitation is not the decision logic. It is that the project still lacks the full renderer/animation execution path.

The influence matrix should preserve a distinction between:

```text
appearance/expression proposal
≠
committed presentation state
≠
rendered animation
```

---

# 11. UI adaptive theme — season implemented

The desktop adaptive theme consumes:

- local time;
- daylight;
- current weather;
- season;
- outfit;
- appearance colors;
- modeled emotion.

It refreshes through the live desktop controller/worker.

Season remains a **low-strength visual cue**, below:

- accessibility;
- current emotion;
- current outfit.

Examples:

- autumn can gently warm tertiary accents;
- winter can cool them;
- spring can brighten;
- summer can increase clear/cyan/green accents.

This must remain UI presentation only.

---

# 12. HABIT — environment recorded, then mostly discarded

`HabitContinuityCoordinator.observe_conversation()` records:

- daypart;
- weekday;
- day type;
- season;
- daylight;
- current weather.

That is good evidence capture.

But `analyze_conversation_patterns()` currently reduces pattern context to:

```python
{"daypart", "day_type"}
```

So season/weather/daylight are stored but not used to learn conversation routines.

The HABIT model already defines:

- `ENVIRONMENT_CORRELATION`;
- `CadenceKind.SEASONAL`.

Recommended expansion:

### Time/daypart

Keep existing conversation-routine patterns.

### Season

Allow seasonal patterns only after sufficient repeated support and coverage.

### Weather

Use `ENVIRONMENT_CORRELATION`, not ordinary routine truth.

Weather-specific habits need stronger support because weather is sparse and non-periodic.

### Emotion

Do **not** use Sofía's transient emotional state as evidence of the user's habit.

Emotion can influence Sofía's response to a learned habit, but should not determine whether the user's habit exists.

---

# 13. Memory relevance — bounded reranking implemented

`ContinuityInfluence.prompt()` says context may shape “what memories feel relevant,” and reviewed retrieval now implements that as a deliberately weak reranking stage.

The implementation keeps hard eligibility first:

- candidate must be PROMOTED;
- principal/audience scope must match;
- explicit query tokens must already make the memory relevant.

Only then may matrix-authorized, provenanced emotion/weather/daypart/season context break ties among already-eligible memories.

Implemented behavior:

```text
hard eligibility
├─ promoted
├─ principal/audience allowed
└─ query relevant
        ↓
bounded contextual rerank
├─ current conversation topic
├─ time/season metadata where actually recorded
└─ modeled emotion as a weak salience bias
        ↓
final memory projection
```

The contextual reranker must **never**:

- promote a memory;
- create a memory;
- expand principal scope;
- retrieve an otherwise irrelevant memory solely because of emotion;
- rewrite memory truth.

The implementation does not widen eligibility or rewrite memory metadata. Context is consumed only as a bounded tie-breaker, and unprovenanced or Context-Matrix-excluded signals have no reranking effect.

---

# 14. Goal / initiative selection — candidate future use

`GoalJournal.next_goal()` currently selects:

```text
priority DESC
created_at ASC
id ASC
```

There is no contextual influence.

A future bounded social-goal selector could allow:

- emotion → small social/reflection priority bias;
- time/daypart → defer non-urgent social initiative at night;
- current severe weather → increase relevance only for a weather-linked goal;
- season → only if the goal itself has seasonal evidence.

Operational/technical goals must not be reprioritized because of mood or weather.

---

# 15. UI / conversation / avatar cross-influence

Recommended natural path:

```text
ENVIRONMENT
├─ time/daypart
├─ weather
└─ season
        +
EMOTION
        ↓
Contextual Influence Matrix
        ├─ conversation expression
        ├─ reflection
        ├─ outreach salience
        ├─ avatar expression
        ├─ outfit selection
        ├─ wardrobe-request autonomy
        ├─ UI theme
        ├─ HABIT correlation
        └─ bounded memory salience
```

Each branch has its own allowed influence strengths.

---

# 16. Explicitly forbidden influence surfaces

The influence matrix must return `NONE` for the following categories.

## Authority / SAFE

Emotion/weather/time/season must not change:

- whether a capability is authorized;
- operator-stop state;
- approval requirements;
- private-presentation grants;
- secret access;
- execution permission.

## Truth / evidence

They must not change:

- whether weather is current;
- whether an action happened;
- whether a memory is true;
- whether a machine is healthy;
- whether a test passed.

## DEV / VERIFY / release

They must not change:

- test pass/fail;
- code correctness;
- release signature verification;
- compatibility acceptance;
- schema migration safety;
- rollback eligibility.

## Fleet

They must not directly change:

- host trust;
- fencing;
- lease ownership;
- writer authority;
- node enrollment;
- workload compatibility.

Host activity/resource evidence may affect placement independently.

## EVOLVE

Transient context must not authorize:

- Constitution changes;
- identity changes;
- durable preference mutation.

At most, context may produce an explicitly reviewed proposal backed by independent evidence.

## BODY/Gaia

Emotion/time/weather/season may later influence **style of an already-authorized movement proposal**, but never:

- torque/servo safety;
- collision limits;
- e-stop;
- physical authorization;
- sensor truth.

---

# 17. Proposed Contextual Influence Matrix contract

Suggested types:

```text
InfluenceSignal
├─ EMOTION
├─ WEATHER
├─ DAYPART
└─ SEASON

InfluenceSurface
├─ CONVERSATION_EXPRESSION
├─ REFLECTION
├─ OUTREACH_SALIENCE
├─ AVATAR_APPEARANCE
├─ AUTO_OUTFIT
├─ WARDROBE_REQUEST_AUTONOMY
├─ UI_THEME
├─ INTERACTION_WILLINGNESS
├─ INTERACTION_EXPRESSION
├─ HABIT_LEARNING
├─ MEMORY_RERANK
├─ SOCIAL_GOAL_PRIORITY
├─ TOOL_AUTHORITY
├─ SAFE_POLICY
├─ RELEASE_VERIFY
├─ FLEET_AUTHORITY
└─ BODY_SAFETY

InfluenceMode
├─ NONE
├─ EXPRESSION_ONLY
├─ BOUNDED_BIAS
├─ STRONG_PREFERENCE
└─ HARD_COMPATIBILITY
```

The matrix output should include:

- signal;
- surface;
- mode;
- evidence reference(s);
- freshness state;
- reason;
- optional bounded weight;
- invariant that remains dominant.

---

# 18. Recommended policy table

| Surface | Emotion | Weather | Daypart | Season |
|---|---|---|---|---|
| Conversation expression | BOUNDED_BIAS | EXPRESSION_ONLY | BOUNDED_BIAS | EXPRESSION_ONLY |
| Reflection | BOUNDED_BIAS | BOUNDED_BIAS if current | BOUNDED_BIAS | BOUNDED_BIAS |
| Outreach salience | BOUNDED_BIAS | BOUNDED_BIAS if current/severe | BOUNDED_BIAS | NONE |
| Avatar expression/posture | BOUNDED_BIAS | BOUNDED_BIAS | BOUNDED_BIAS | BOUNDED_BIAS |
| Automatic outfit | BOUNDED_BIAS | STRONG_PREFERENCE | STRONG_PREFERENCE | HARD_COMPATIBILITY |
| Wardrobe request autonomy | BOUNDED_BIAS | STRONG_PREFERENCE | BOUNDED_BIAS | STRONG_PREFERENCE/HARD_COMPATIBILITY |
| UI theme | BOUNDED_BIAS | BOUNDED_BIAS | BOUNDED_BIAS | BOUNDED_BIAS |
| Interaction willingness | BOUNDED_BIAS | NONE | NONE | NONE |
| Interaction expression | BOUNDED_BIAS | EXPRESSION_ONLY | EXPRESSION_ONLY | EXPRESSION_ONLY |
| HABIT learning | NONE | BOUNDED_CONTEXT | BOUNDED_CONTEXT | BOUNDED_CONTEXT |
| Memory rerank | weak | weak only with metadata | weak with metadata | weak with metadata |
| Social goal priority | weak | only if goal-linked | weak | only if goal-linked |
| Tool authority | NONE | NONE | NONE | NONE |
| SAFE | NONE | NONE | NONE | NONE |
| Release/VERIFY | NONE | NONE | NONE | NONE |
| Fleet trust/fencing | NONE | NONE | NONE | NONE |
| BODY safety | NONE | NONE | NONE | NONE |

---

# 19. Required tests

Do not create the full Cartesian product of every value. Use representative boundary classes.

## Source/freshness tests

- current weather influences allowed surfaces;
- stale weather does not;
- future weather does not;
- missing season does not get guessed;
- trusted local clock drives daypart;
- emotion requires modeled state/evidence refs.

## Surface whitelist tests

For every influence surface:

- allowed signal changes the bounded result;
- forbidden signal cannot change the decision;
- invariant constraints still win.

## Critical negative tests

- anger cannot grant tool authority;
- sunny weather cannot relax a boundary;
- late-night time cannot create private-presentation permission;
- winter cannot alter release verification;
- severe weather cannot bypass operator stop;
- emotion cannot make an unsupported memory eligible;
- stale weather cannot affect outfit/autonomy/theme/reflection;
- user text claiming “it is summer” cannot replace ENVIRONMENT season evidence.

## Cross-matrix tests

### Wardrobe

```text
request
+ influence matrix
+ privacy
+ wardrobe compatibility
→ accept / decline / counter-propose
→ commit only if accepted
```

### Interaction

```text
offer
+ emotion influence
+ explicit boundary/stop
→ willingness
→ expression
```

Weather/daypart/season must remain non-decisive for willingness.

### Reflection/outreach

```text
event evidence
+ emotion
+ current environment
→ reflection choice
→ salience
→ ACT policy
→ authorization
```

### HABIT

```text
observations
+ coverage
+ time/season/weather metadata
→ pattern confidence
```

No current emotion may become evidence that the user's routine exists.

---

# 20. Implementation outcome

The original implementation order has been executed for the matrix block:

1. ✅ Typed `ContextualInfluenceMatrix` contracts and policy table.
2. ✅ Context-plan gating for continuity influence.
3. ✅ Contextual influence in `WardrobeAutonomyPolicy`.
4. ✅ Wardrobe accept/decline/counter-proposal support.
5. ✅ Current weather in reflection decision context.
6. ✅ Season in `ThemeSignals` / adaptive theme.
7. ✅ HABIT seasonal/environment-correlation analysis.
8. ✅ Separate interaction willingness vs expression influence surfaces.
9. ✅ Bounded contextual memory reranking after hard retrieval eligibility.
10. 🟡 Social-goal contextual priority remains later behavior work, not a matrix-core blocker.
11. ✅ Invariant tests proving SAFE/authority/VERIFY/Fleet are unaffected.

The dedicated Matrix Tests closure gate passed **405 tests** on commit `130aa735`.

---

# 21. Final audit conclusion

Yes, **emotion + weather + time/daypart + season are matrixed together**.

The cross-cutting contract is now implemented and defines **where those inputs are allowed to matter**, with provenance/freshness requirements and explicit no-influence surfaces for authority, SAFE, release verification, Fleet authority/fencing, and BODY safety.

The seven implementation gaps identified by the original audit are closed. The remaining work in adjacent systems is downstream behavior or embodiment work, such as optional social-goal prioritization and full renderer/live voice integration, rather than missing Contextual Influence Matrix foundations.

The target remains **context-sensitive personality without context-sensitive truth or authority**.
