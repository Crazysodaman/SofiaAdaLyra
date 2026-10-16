# Sofía waist-up VTuber: actual public garment sprites and first-run deployment

**Code source on main:** src/sofia/avatar/vtuber_starter_art.py, src/sofia/avatar/vtuber_asset_bundle.py, src/sofia/avatar/vtuber_layer_stack.py, src/sofia/ui/avatar2d_renderer.py, src/sofia/ui/desktop.py.

**Status:** Source and targeted tests committed; exact-SHA CI and supervised Venus screenshot/asset acceptance remain separate gates. Generator produces functional, deliberately simple procedural 2D character/clothing layers, not professional hand-painted Live2D assets.

## Repository inventory recheck (2026-10-15)

Under src/sofia/avatar/wardrobe_data/: 295 defined garments in JSON (51 marked private_only) and 23 selected outfit records (20 public, 3 private). The catalog also supplies a small number of canonical built-in items and a covered fallback preset. The source inventory **already exists**, so **do not duplicate it**.

Existing approved daily public outfit ID: day.default; actual selected pieces include base.bralette, base.briefs, day.technical_top, day.utility_trousers, day.engineer_jacket, day.work_socks, day.work_boots, day.fingerless_gloves and day.utility_belt.

Other normal samples: night.lounge, outfit.light_lab_tech, outfit.cozy_evening and outfit.circuit_casual. For each visible torso/shoulder/hand/neck/waist/ear/tail slot, the art generator uses the **real garment ID and Layer**. Garments outside the waist-up crop stay in the canonical outfit even though they do not require on-screen pixel layers.

## Real transparent PNG generation (Windows/PowerShell)

First install/run Sofía's repository in an existing approved environment. No production credentials or canonical DB changes are necessary to generate these public-only images.

    $ArtRoot = Join-Path $env:LOCALAPPDATA 'SofiaAdaLyra\Avatar2D\Public'
    python -m sofia.avatar.vtuber_starter_art --output "$ArtRoot" --outfit all

That generates a separate fully layered, transparent RGBA PNG bundle under each public outfit directory (plus the preset-covered fallback):

    Public\
      outfits\
        day.default\
          manifest.json
          base\back.png
          base\body.png
          base\face.png
          base\front.png
          garments\base.bralette.png
          garments\day.technical_top.png
          garments\day.engineer_jacket.png
          garments\day.utility_belt.png
          ...

For reusable pieces independently of an outfit, generate the public waist-up sprite library:

    python -m sofia.avatar.vtuber_starter_art --output "$ArtRoot" --library

That creates Public\library\items.json plus one transparent sprite for **every publicly reviewed garment with at least one visible waist-up slot**. It deliberately does not generate off-camera shoes, lower-body underwear/pants without visible waist regions, or any private-only item. The item manifest records original garment ID, slots, garment layer and SHA256.

**No overwrite:** Generation refuses to replace existing artwork/manifest files. This protects future manually refined layers from getting silently replaced by procedural starter graphics. Choose a fresh output root to regenerate, verify before promoting it. A partial failed scratch output should be reviewed rather than blindly merged into a known-good art folder.

## Enable in desktop (opt-in)

In the PowerShell session that launches Sofía:

    $env:SOFIA_AVATAR2D_PUBLIC_ROOT = $ArtRoot
    python -m sofia

The desktop now selects the optional TkLayered2DRenderer for **public** projections, verifies actual outfit/PNG hashes and canonical slot coverage, then draws the base and garments in actual garment layer order:

1. Rear ears/tail/hair
2. Canonical torso and arms
3. UNDERWEAR (10), BASE (20), MID (30), OUTER (40), ACCESSORY (50)
4. Face and expression
5. Front hair and overlays

The current 2D MVP draws the starter illustrations, **not** the polished concept image. The renderer uses Tk's native PNG support and scales the shared 320x400 image layers to fit the workbench. Existing symbolic animation remains a fallback when art is unavailable or invalid. Text chat continues with no requirement to enable any art.

Setting the path is a public sprite opt-in, **not** an authorization to access private garments or nude state. The private gateway remains a separately protected API and is deliberately NOT selected by the normal desktop variable.

## Sanity checks

Before owner-host acceptance, execute focused and package tests:

    pytest -q test/test_avatar2d_starter_art.py test/test_avatar2d_layer_stack.py test/test_avatar2d_asset_bundle.py test/test_ui_avatar2d_renderer.py
    pytest -q -m "pkg_avatar and not integration"
    pytest -q -m "pkg_ui and not integration"

Verify exact GitHub commit tests and then manually:

- Daily engineer look has the technical top, jacket, gloves and appropriate visible garment layers, including actual source IDs.
- Switching to an authored public lounge outfit uses its new artwork when a matching pack exists.
- Missing/invalid art triggers Tk fallback rather than a dishonest rendered-2D claim.
- No private artwork is loaded, cached or exported by the public desktop backend.
- Public visibility continues while the canonical current presentation is private, through the approved last-daily covered fallback.
- A garment sprite can be reused in multiple saved outfits; avatar face and proportions do not change when clothing does.
- Startup, close, restart, memory/CPU load, screen scaling, background/gaming pressure and private-mode rollback must be observed on real Venus before Gate 4.

## Private wardrobe / adult implementation boundary

Only metadata and policy/asset-loader groundwork exists for the protected private version. That version needs authenticated, explicit current owner opt-in; durable private_chat/adult_avatar authority; any applicable FIDO2 security-key approval; and independent STOP/revocation checks. Private artwork lives in its own protected local root. The standard generator **refuses** private outfit IDs and never makes a nude image.

Do not confuse the optional protected asset interface with a completed private art pack or deployable private renderer. New private artwork should be reviewed and installed through that protected pipeline when available. The public generator and this document never authorize private loading or disclose private assets.

## Remaining production work

Refine starter sprites using an approved coherent character layer sheet; add voice-driven eyes/mouth and ear/tail deformation, common item-library lookup for dynamically created outfits, authenticated UI hit/event routing, and supervised private asset rendering under the existing SAFE owner controls. A concept sheet or metadata record alone never proves a layer has been rendered.
