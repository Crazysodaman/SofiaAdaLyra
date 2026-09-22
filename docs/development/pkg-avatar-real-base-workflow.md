# PKG-AVATAR | Real-base modeling reset

**2026-09-22 | draft PR #7 | design and external authoring workbench only.** The previous procedural A0/A1 GLBs and dressed 94-part prototype are **rejected as visual art**. Preserve their measurement and GLB import tests as technical fixtures only. Do not advertise them as polished, approved, the canonical Sofía sculpt, or runtime-ready.

## Modeling foundation

- Use [Blender](https://www.blender.org/download/) and the [MakeHuman Community MPFB Blender extension](https://extensions.blender.org/add-ons/mpfb/) to create and customize an **existing genuine adult female human mesh**, rather than assembling primitives. MPFB can generate a human, adjust body parameters and offer rigging workflows; it does not automatically make Sofía or verify anatomical correctness.
- MPFB's **bundled core graphical assets are CC0** according to the [upstream license](https://github.com/makehumancommunity/mpfb2/blob/master/LICENSE.md); the code is GPLv3. Independently downloaded models/clothing have separate licenses and require individual review. Do not commit an unverified third-party asset or assume all MPFB community downloads are CC0.
- Existing `src/sofia/data/avatar.json` is the source for 67-in adult human standing height; 33-in bust, 30-in underbust, 26-in waist and 37-in hips. Weight 135 lb and 30C are reference metadata, not automatic mesh geometry. Use the user-approved Sofía character turnaround for appearance and silhouette **only**, not as a calibrated orthographic image.
- The agreed complete external adult female authoring anatomy, separate fox ears, and a tail root near the posterior tailbone require actual artist sculpt, inspection, topology and rig review. No garment slot, interaction target or physical sensation follows from an anatomical landmark.

## Workbench handoff generated in this chat

The separate downloadable **`sofia_real_base_blender_workbench.zip`** contains `sofia_mpfb_workbench.py`, a target measurement JSON, instructions and Sofía turnaround art. The script runs *inside Blender after the artist creates/selects a real MPFB human*. It checks an actual evaluated mesh's standing Z span, organizes separate authoring and five wardrobe layer collections, creates provisional labeled fit anchors, and hides the authoring mesh from ordinary renders. It does **not** create/modify a human body, produce anatomy, calculate actual girths, install MPFB, rig, skin, generate clothes, or grant private previews. The workbench script is not committed to this GitHub branch; the ZIP is the handoff source. Its syntax and AST were checked outside Blender only; Blender/MPFB execution is **NOT RUN**.

## Acceptance sequence

1. Acquire and verify Blender and MPFB locally, choose only traceable/authorized art and record versions/licenses.
2. Create the real adult female human; customize shape; inspect front, side, rear and three-quarter. Save the actual `.blend` in controlled authoring storage, recording source and version.
3. Measure true body-only horizontal mesh cross-section perimeters at repeatable bust, underbust, natural waist and maximum hip planes; measure crown-to-sole height without ears/hair/shoes. Record target, actual, signed error, plane height and evidence. Do not confuse bounding-box width with circumference.
4. Sculpt and visually review Sofía-specific face, hair, fox ears and tail, agreed adult external anatomy, fingers and feet. Ensure normal human anatomy remains independent of tail root. A2 visual approval requires review of actual rendered geometry against the art, not approximate numeric compliance alone.
5. Rig the same body and separately movable ears/tail; bind provisional garment anchors to bones/deformation and verify poses. Fit and license underwear/base layers, complete engineer attire, lounge attire and a clothed fallback to that exact body. Test tail clearance, transparency, clipping and missing asset behavior.
6. Verify Blender export/import, source and artifact SHA, runtime privacy, actual display receipts, Windows and full repository acceptance before asking for a merge or deployment decision.

**Status:** No real human asset, Blender `.blend`, anatomically complete sculpt, fitted clothing or final rig has been created or verified here. `main`, INTERACT, protected identity/Constitution and the production database are untouched. This roadmap reset changes no release gates.
