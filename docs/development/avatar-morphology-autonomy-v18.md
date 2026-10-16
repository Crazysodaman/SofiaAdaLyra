# Avatar morphology, appearance autonomy, and V18 traceability

**Implementation commits:** on `main`, beginning at `6b8f974` and subsequent AVATAR commits on October 15, 2026.
**State:** source coded, CI and real-host acceptance pending. This document is not a Gate-4 receipt.

## Existing V18 owners, no duplicate task ledger

| Original task | Integration boundary | Implementation and limitations |
| --- | --- | --- |
| CA-504 | One expression decision across face, ears, tail, pose and gesture | Extended revisioned `AppearanceState`; Tk paints supported symbolic poses, eye color, hair sway, blink and surface ornaments. Must still wire a full-expression runtime decision path for autonomous styling. |
| CA-505 | Truthful renderer receipts | Existing Tk renderer callback remains authoritative for painted frames. Don't claim 3D assets, realistic fur or physical movement. |
| CA-507 | Non-authoritative expression intent | New appearance fields are payload only; no new permission issuer or direct device-control path. |
| CA-6008 | Emotional/environmental expression provenance and privacy | Reuse the existing `PresentationAuthority` audience projection and state store; private anatomical details remain outside `AppearanceState` and public snapshot output. |
| CA-1011 | Voice and avatar shared projection | Existing voice/expression coordination is unchanged; full motion/voice timing verification remains outstanding. |
| CA-3112 | Truthful avatar/world/voice contract | Keep semantic/symbolic visuals distinct from actual rigged animation and independently verified audio. |
| CA-901, CA-905 | Tests and supervised live acceptance | Added focused AVATAR tests; CI and real Venus renderer tests still required. |

**Package scope:** PKG-AVATAR owns baseline morphology, public presentation, favorite styles and appearance history. PKG-INTERACT/EMOTION own gesture proposal; PKG-UI owns renderer; PKG-SAFE owns private access; PKG-VERIFY owns gate evidence. The original V18 tasks and their status ledger are intentionally untouched.

## Canonical baseline and change boundaries

The six existing height/weight/torso circumference facts retain their exact original values. Sixteen further named measurements, including limb lengths/circumferences and fox-ear/tail dimensions, are declared with null values and explicit units, not invented figures. New facial detail fields whose values are unknown are `unspecified`. `physical_self.anatomy` specifies two fox ears, one fox tail, and two arms/two legs. Canonical topology values are validated for Sofía's complete fox representation, while legacy partial semantic fixtures can still load.

Extra private morphological details have three optional local design attributes, initialized null. They are deliberately kept out of ordinary `appearance`, the revisioned public appearance snapshot, favorites, renderer payload and deterministic self-description. `PhysicalSelf` omits them from debug repr. **This is not encrypted storage:** production state-root files and backup/export policy still require access controls. The feature never implies consent or changes SAFE authority.

## Independent reversible styling

`AppearanceState` can change hairstyle/hair length/hair design/color; eye color; posture, ear/tail pose and expression; fur styling, freckles, makeup, temporary tattoos and piercings. Fields validate before changes can be proposed. The existing optimistic-revision `PresentationAuthority.propose_appearance` and `PresentationStore.persist_mutation` paths are used for changes. `avatar_appearance_history` logs only settled public appearance/outfit revisions and reasons. `avatar_style_favorites` stores named public cosmetic presets in canonical `sofia.db`. This is **not** automatic self-preference learning: no autonomous appearance generator, owner approval bypass or external UI action has been added.

The optional Tk renderer shows representative hair sway, blink, gaze, eye hue, supported poses, freckles and tattoo/piercing icons; this is not a rigged 3D simulation. Face/bone structure and permanent body proportions are not in mutable appearance state. Limb, ear and tail counts never have an autonomous mutation API.

## Deployment and acceptance

Source seed `src/sofia/embodiment/avatar.json` is used on fresh provisioned homes only. Existing production avatar files remain unchanged until owner-reviewed state-root migration with backup. New SQLite tables are created by the existing PresentationStore on bootstrap; no second DB or runtime writer.

Focused tests: `python -m pytest -q test/test_avatar_morphology_autonomy.py test/test_avatar_presentation.py test/test_avatar_presentation_store.py test/test_avatar_presentation_runtime.py test/test_embodiment.py`.

Before Gate 4: green package CI with exact source SHA, confirmed Venus UI paint/receipt/projection tests, production state migration and restart, private-scope egress checks, and evidence for any claimed physics or animations. Treat advanced hair/eye rigging and AI-selected styles as open integration requirements.
