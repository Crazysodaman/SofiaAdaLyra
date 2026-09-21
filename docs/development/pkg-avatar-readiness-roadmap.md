# PKG-AVATAR | branch readiness roadmap

**2026-09-21 | draft PR #7 | baseline head `1f1d523d57be54983c72296a4413058195b5a75a`.** Proposed package, not yet part of authoritative main roster. Read `pkg-avatar-offline-review.md` and PR #4's `pkg-avatar-embodiment-wardrobe-objects.md` / `ROADMAP-AVATAR.md`. Preserve canonical `src/sofia/data/avatar.json` (appearance and fox ear/tail) and do not fabricate mesh/art assets.

## What exists and what was actually tested

Headless wardrobe metadata/layering/covered-default policy and versioned virtual-object proposal/acknowledgement state machine. **58 focused AVATAR tests passed on equivalent isolated Linux source**, 96 alongside UI fixtures. A simulated acknowledgement is not an authenticated renderer receipt. There is **no actual nude adult base mesh, garment art, rig, live renderer, geometry/age verification, full coverage check or persisted scene**.

## A0–A5 development and test gates

1. **A0 canonical-to-asset map:** pin avatar JSON SHA and source fields, approved adult characterization, units, proportions and rights/license; list where art/rig anatomy is intentionally unspecified. Select 2D/3D renderer via actual hardware, accessibility, offline capability, modifiability and VRAM/CPU measurements, not brand assumption. Unknown details go to review; identity/Constitution untouched.
2. **A1 base/rig:** author approved adult unclothed modeling/fit base **as controlled authoring asset**, skeleton, deformation, hands/face/ears/tail, canonical region IDs, facial channels and grip sockets. Restricted previews remain local/disabled by default, normal public mode clothed; verify no screenshots, thumbnails, cache, missing-texture or fallback expose restricted geometry. Art existence is never an interaction consent grant.
3. **A2 wardrobe:** complete practical default canonical engineer ensemble with vetted base layers from underwear to outerwear, socks/boots/gloves/accessories; explicit slots/layers, garment coverage, fox ear/tail openings and fit under sitting/gestures. Other optional clothes need design approval/license. Test actual deformation, clipping, skin exposure, privacy fallback, missing/invalid assets, dress/undress state and restore.
4. **A3 real renderer:** isolate process from chat, use versioned typed avatar hit tests and supported animations through INTERACT/SAFE/UI. Proposed → approved → started → actually acknowledged/failed are distinct; stale/forged receipts denied. Tests include real pointer hit and stop/cancel, animation-on/off, crash, reduced motion and low GPU cost while chat stays responsive. Never claim physical touch or an animation that did not render.
5. **A4 joint virtual props:** source-linked mug/notebook/desk/tools with holder, ownership, audience, revision and rollback; actual Sparks offer → Sofía accept/decline → renderer acknowledgement → persisted object transition. Test replay, concurrent holds, scene restore, private object previews and UI notes. A virtual multimeter or lab tool is simulated without independently verified sensor data.
6. **A5 expansion:** approved outfit presets (including accessories/overwear), animation coordination, import/export with provenance/sandboxing, accessible privacy controls and optional later multi-client scope. General multi-user remains deferred. No robot/real desktop capabilities through virtual props.

## Decisions for the avatar review

Approve fine art/anatomy not canonically specified, mesh/rig source and license, renderer and asset format, wardrobe categories/appearance, private-preview eligibility/visibility and capture rules, collision/LOD budgets, scene ownership/persistence and whether Sofía can propose clothing/prop choices from approved options. No automatic restricted-mode or adult eligibility inference from affectionate text.

**Exit:** isolated schema/scene tests only; geometry, renderer, live receipts, privacy screens, Windows/full suite and asset provenance acceptance NOT RUN. No merge/deployment.
