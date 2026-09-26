# PKG-AVATAR headless completion gate — 2026-09-25

**Branch:** `feature/pkg-avatar-headless-completion`  
**Base:** current `main` after CORE/INTERACT live-regression gate documentation  
**Scope:** AVATAR software/state completion that does not require Blender or a renderer.

## Implemented on this branch

### Authoritative presentation state

- revisioned current presentation independent from protected identity;
- clothed and explicit adult/private **nude** attire states;
- current outfit ID and garment IDs;
- hairstyle;
- hair color;
- tail color;
- style tags;
- source reason;
- pending/replay/stale-revision protection;
- snapshots and restore.

Nude is a private presentation state, **not** a sexual mode, consent signal, attraction/desire/arousal signal, or permission grant.

### Public/default fallback rule

The public/default fallback is the **last successfully committed daily clothed outfit**.

- A private/nude presentation never replaces the public daily fallback.
- Entering a private state leaves the last daily outfit intact.
- If no daily history exists, AVATAR bootstraps from `engineer.signature`.
- Unknown/public cognition receives only the public-safe projection.
- Future SOCIAL integration may request the private projection only after independently authenticated private audience evidence.

### Presentation persistence

`PresentationStore` atomically stores settled state at:

`state/avatar-presentation.json`

The snapshot preserves current state and last daily public fallback separately. Pending transitions cannot be snapshotted as settled.

Application startup loads or bootstraps this state and attaches it to the runtime. Shutdown saves the settled state.

### Deterministic direct self-facts

Direct questions about current outfit, hair color, tail color, current look, representational form/avatar, and the reviewed tonight-outfit candidate are resolved from typed AVATAR/embodiment state **before LLM inference**.

This exists because supervised Qwen testing showed that provider-visible grounding alone was not sufficient: the model repeatedly denied the canonical representational body and clothing despite receiving the correct state.

The deterministic route is intentionally narrow. Unrelated style discussion and open-ended conversation still go through cognition. This prevents the model from overruling authoritative self-facts without turning AVATAR into a general canned-response engine.

### Current cognition grounding

The runtime projects a trusted `CURRENT AVATAR PRESENTATION` section into cognition.

For current-wear questions, the AVATAR projection outranks static canonical clothing design as the CURRENT state. Static canonical clothing remains an available wardrobe baseline.

Until SOCIAL supplies authenticated audience identity, cognition deliberately receives only the public-safe projection.

### Context-driven daily wardrobe

The existing planner now supports:

- trusted local time;
- time-of-day lounge window;
- season;
- activity;
- fresh weather observation;
- reviewed Sofía preferences;
- reviewed Sparks preferences;
- recent verified wear history;
- **bounded modeled-emotion style influence**.

Emotion influence is capped as a soft style bias. It cannot override privacy, coverage, activity compatibility, or hard seasonal constraints and does not infer emotion from user text.

`HeadlessPresentationRoutine` performs one explicit daily evaluation and can commit a changed daily outfit in text-fallback mode. RUN remains responsible for scheduling future automatic evaluations.

If a private-only/nude presentation is active, automatic daily rotation defers rather than replacing the private state.

### Mutable canonical defaults

The avatar data now explicitly supplies mutable presentation defaults for:

- long layered hairstyle;
- deep crimson hair / `#8B1E3F`;
- dark-violet tail / `#3A245C`.

These are presentation properties, not protected identity.

## Salvaged from stale PR #7

The branch ports the non-Blender AVATAR foundation from the old draft onto current `main`:

- body/fit contract;
- wardrobe metadata/layering;
- starter wardrobe and lounge variation;
- shared wardrobe state;
- style context and separated user/Sofía preferences;
- scene semantics;
- INTERACT bridge scaffolding;
- time/weather wardrobe context;
- existing offline tests/docs.

The old branch should not be merged wholesale after this replacement branch is accepted.

## Still requires Blender / renderer later

This headless gate does **not** claim:

- final body mesh;
- face/hair/fox-ear/tail geometry;
- rigging/skinning;
- fitted clothing meshes;
- actual nude/clothed visual assets;
- deformation and clipping proof;
- verified geometry coverage;
- material/shader proof;
- animation;
- renderer hit-testing;
- authenticated renderer receipts;
- screenshot/render acceptance.

Those become the visual AVATAR gate after the headless software state is accepted.

## Focused acceptance targets

Run:

```powershell
python -m pytest -q `
  test/test_avatar_body_contract.py `
  test/test_avatar_scene.py `
  test/test_avatar_shared_wardrobe_state.py `
  test/test_avatar_starter_user_preferences.py `
  test/test_avatar_style_context.py `
  test/test_avatar_wardrobe_catalog.py `
  test/test_avatar_wardrobe_metadata.py `
  test/test_avatar_wardrobe_routine.py `
  test/test_avatar_presentation.py `
  test/test_avatar_presentation_store.py `
  test/test_avatar_presentation_routine.py `
  test/test_avatar_runtime_projection.py
```

Then run surrounding application/cognition/embodiment regressions and the full repository suite.

## Live acceptance target

After this branch and the CORE/INTERACT live fixes are both integrated, replay the pinned supervised CLI conversation including:

- current feeling;
- affectionate/cuddle context;
- “what outfit do you have on or want to change?”;
- body gestures.

For outfit/current-appearance turns, Sofía must answer from AVATAR presentation state instead of denying her canonical representational body or clothing.

## Deferred dependencies

- **SOCIAL:** authenticated private audience / Sparks principal.
- **RUN:** periodic scheduling of presentation reevaluation.
- **MEM:** richer durable preference maturation/history.
- **UI/renderer:** exact visual synchronization and receipts.
- **VERIFY:** live visual/privacy/restart/renderer evidence.
