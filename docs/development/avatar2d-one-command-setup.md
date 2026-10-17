# Sofía 2D-first setup: complete public waist-up avatar

**Current target:** Work on the 2D VTuber until it is actually usable. Keep the 3D interface separate and unavailable until verified 3D art and a real host are installed. Only one backend can render at a time.

## What is real on main

- Independent source-verified public PNGs: wardrobe base/body; actual clothing from canonical wardrobe presets; separate left/right eye sprites, brows, mouth, hair back/front, two fox ears and one tail.
- Shared canvas: 320×400 RGBA transparent PNGs, with canonical wardrobe slot/layer ordering. Illustrative procedural starter art, **not** the finished-quality manually approved anime sprites.
- The live desktop's optional TkLayered2DRenderer loads a public outfit pack plus a separate character manifest, validates hashes and dimensions, and paints actual PNG layers. Supported gestures include blink/wink, tail-flick, ear-perk and ear-flick with independent frame receipts, not fabricated experience or sensation.
- The UI's 2D/3D selector stays on 2D while 3D assets/driver are unavailable. No duplicate canonical Sofia runtime/memory/wardrobe database.
- An unavailable or corrupted sprite pack drops to the safe public Tk symbolic renderer. The public path never loads private/art-only assets.

## First-run on Venus (Windows, installed source checkout)

In PowerShell within Sofía's existing Python environment, run:

    $Art = Join-Path $env:LOCALAPPDATA "SofiaAdaLyra\Avatar2D\Public"
    python -m sofia.avatar.vtuber_public_setup --output "$Art"

This uses the existing **day.default** public outfit and generates all modular head/fox variants. It does **not** write/change sofia.db. It writes a sibling temporary staging folder, validates real PNGs, hashes, wardrobe slot coverage and character group completeness, then promotes the complete art folder in one step. It refuses to overwrite a reviewed or existing folder.

For all currently approved PUBLIC outfit presets, instead run (with a **fresh** output path):

    $Art = Join-Path $env:LOCALAPPDATA "SofiaAdaLyra\Avatar2D\Public-All"
    python -m sofia.avatar.vtuber_public_setup --output "$Art" --all-public

Do not use Public-All and Public interchangeably unless the environment setting is pointed at the exact intended root. For a new version of the artwork use a distinct versioned directory rather than overwriting existing art.

Launch Sofía with the installed 2D pack:

    python -m sofia

The desktop automatically discovers an existing public pack under `%LOCALAPPDATA%\\SofiaAdaLyra\\Avatar2D\\Public-V2`, `Public-All`, or `Public` (in that priority order), if it contains the default outfit and character manifests. This is read-only startup discovery, not automatic image generation or artwork approval. The renderer still verifies actual PNGs and hashes and falls back safely if art is missing or corrupted. No private artwork is searched.

To select a custom versioned directory, explicitly override discovery in the same PowerShell session:

    $env:SOFIA_AVATAR2D_PUBLIC_ROOT = "$Art"
    python -m sofia

The environment override is temporary; installed default pack discovery works on later launches without it. In the desktop select **2D**. **3D** currently reports unavailable and leaves 2D running; it does not pretend a 3D model is installed.

Expected root:

    Public\
      outfits\
        day.default\
          manifest.json
          base\body.png
          garments\day.technical_top.png
          garments\day.engineer_jacket.png
          ...
      character\
        manifest.json
        face\neutral.png
        freckles\off.png
        eye_left\open.png
        eye_left\closed.png
        eye_right\open.png
        eye_right\closed.png
        brow_left\neutral.png
        brow_right\skeptical.png
        mouth\smile.png
        hair_back\long_layered.png
        hair_front\long_layered.png
        ear_left\perked.png
        ear_right\perked.png
        tail\flick.png

## Verify separately

Run the new headless end-to-end regression group in CI or on an installed test environment:

    python -m pytest -q test/test_avatar2d_public_setup.py test/test_ui_avatar2d_live_parts.py test/test_avatar2d_character_selection.py

Expected evidence:
1. All intended PNG layers are present, hash-checked and compositable against actual outfit cells.
2. Rendered 2D blink frames really change the eye PNG bytes (open, closed, open).
3. The final success receipt only follows the scheduled display acknowledgement.
4. STOP invalidates an in-flight animation and produces no late success receipt.
5. A damaged head/fox asset is rejected without mixing unchecked PNG with verified clothing.
6. No private garments, nude source, private session credentials or production database modifications are introduced by the public setup command.

The targeted workflow '.github/workflows/avatar2d-public-setup-tests.yml' runs these checks and builds a downloadable complete public pack as a 30-day GitHub Actions artifact.

## Open work (do not claim Gate 4)

- Polish each garment and face/fox sprite to final illustrated reference quality, with **full source-description fidelity** and human review. The earlier 295 catalog items and 244 public draft images are not fully artist-approved sprite rigs.
- Basic periodic idle blinking is implemented with real left/right eye sprites, a 12-second default interval, no fabricated chat/expression receipt, hidden-window throttling and STOP/mode-switch cancellation. **Gaze tracking, measured voice-driven lipsync, higher frame rate/ear/tail physics, garment deformation and wearable accessories** still need dedicated production work and resource measurements.
- Real desktop pointer/click bridge into INTERACT with canonical hit masks and explicit consent is not yet live.
- An actual private 2D renderer and assets need owner-authenticated per-frame grant checks, protected file paths and STOP; public setup cannot confer private access.
- A Windows supervised Venus screenshot, startup/restart acceptance and GPU/CPU profile are still needed. Headless/CI tests do not prove production artwork appearance.
