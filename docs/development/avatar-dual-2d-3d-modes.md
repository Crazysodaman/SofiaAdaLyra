# Sofía: exclusive 2D and 3D avatar modes

**Owner decision:** Both a 2D and a 3D avatar are supported, but only **one renderer is active at a time**. They use the same identity, appearance, memory, emotions, wardrobe IDs and SAFE permissions. Their art assets, animation rigs and GPU budgets remain separate.

## Currently implemented on main

- src/sofia/ui/avatar_mode.py: ExclusiveAvatarRenderer selects exactly one backend, cancels the outgoing animation, clears its visual pixels, blocks stale callbacks and retains honest output receipts.
- src/sofia/ui/avatar_mode_store.py: Selected visual mode is a **UI preference** in canonical sofia.db, not new avatar state.
- src/sofia/ui/desktop.py: 2D/3D mode selector. 2D is wired to existing layered PNG art or safe symbolic fallback. Unavailable 3D is rejected with status message; a fake 3D frame is never reported.
- src/sofia/ui/avatar3d_renderer.py: Typed 3D rig and driver adapter requiring an installed ready host, real frame callbacks and separate supported bone/pose tracks. Does **not** claim to be a working production 3D engine.
- test/test_ui_avatar_modes.py and test/test_ui_avatar3d_adapter.py: Test exclusive selection, STOP/cancellation, stale frames, DB persistence, public-only 3D and unsupported/missing rigs.

**Not yet done:** Actual deployed rigged 3D model, 3D graphics driver, 3D wardrobe meshes and live host verification. A model hash field and a driver protocol do not prove a mesh exists or has been verified on disk.

## Shared vs separate

| Shared canonical source | Mode-specific 2D | Mode-specific 3D |
| --- | --- | --- |
| Same body topology with exactly two ears and one tail | PNG puppet, anchors and sprites | Actual 3D meshes, bones and material textures |
| Same outfit ID and original garment/slot authority | PNG outfit layers and alpha masks | Fitted mesh outfit variants/occlusion |
| Same expression decision, pose and semantic gesture | Blink sprites, hair/ear/tail 2D keyframes | Independent bone tracks, blendshapes, visemes and physics |
| Same SAFE owner/consent boundary | Separate authorized 2D private art, when available | Private 3D rig must independently implement SAFE when available |
| Same output receipt semantics | Actual painted frame callback | Actual GPU-presented frame callback |

Semantic action example: ear-perk tells 2D to animate the illustrated fox ears and 3D to turn ear bones. No duplicated emotional engine or incompatible memory systems. Unsupported 3D gestures are not invented.

## Switching lifecycle

1. Local owner chooses 2D or 3D.
2. Verify real backend availability. Missing 3D means 2D remains active and 3D is not persisted as successful.
3. Invalidate old frame callbacks, call old renderer stop(), clear old canvas pixels and return any outstanding decision ID to the UI for a canceled receipt using the old backend name.
4. Activate exactly one new backend, repaint the *current authorized* appearance and persist the UI preference in canonical sofia.db. Neither canonical outfit revision nor emotion is changed.
5. A late callback from the previous mode is ignored and cannot be counted as new output.
6. Mode choice never bypasses private authorization. 3D public adapter refuses nude/private projections until a separately verified protected implementation exists.

Separate model resource policies: 2D sprite assets may be cheap while gaming, 3D rig/physics may be heavy. The 3D host must release animation/GPU assets when stopped and support restart/recovery.

## Work remaining for actual usable 3D

- Make/install canonical 3D base mesh with matching face, two fox ears and tail, animatable rig and expression blendshapes.
- Bind canonical garment IDs to correctly fitted 3D meshes/materials. A 2D PNG does not become a 3D wearable mesh automatically.
- Add a real verified host driver with exact mesh-content SHA, GPU admission, stop/unload, error handling and covered public fallback.
- Wire the installed verified driver into the desktop controller when the host is ready. Do not register unknown plugins based only on user-supplied paths, untrusted chat or environment text.
- Integrate private wardrobe only through the existing SAFE grants with rechecks before display.
- Run focused tests, package CI and supervised Venus acceptance, including a mid-animation switch, gaming load, 3D crash and 2D recovery.

Focused tests:
    pytest -q test/test_ui_avatar_modes.py test/test_ui_avatar3d_adapter.py

Expected current desktop result: select 3D before installing a real driver => status says unavailable and 2D remains active. No 3D Gate 4 or live Venus completion can be inferred from the adapter code.
