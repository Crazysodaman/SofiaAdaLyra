# Sofía 2D: modular puppet and wardrobe rendering

Status: source integrated on main; separate focused Windows CI and real Venus acceptance are required. The art is procedural starter quality, not fully polished Live2D artwork.

## Features

- Existing outfit manifests and canonical wardrobe slot/layer matrix remain the only source of clothing truth. One body base, with UNDERWEAR / BASE / MID / OUTER / ACCESSORY layers.
- A verified, optional public character pack replaces old baked-in face/hair/tail sprites. It includes face, optional freckles, independent left and right eyes/brows, mouth, front and back hair, both fox ears and one tail, all aligned to the 320 x 400 canvas.
- Actual animated three-frame PNG swaps for tail flick/swish/wag, ear-perk/flick, wink and two-eye blink. Completion is acknowledged only after last displayed frame.
- Existing trusted expression decisions choose a limited smile or skeptical brow where matching authored variants exist. No invented audio activity or unverified 2D rig deformation is claimed.
- Character pack files are hash-checked and audience-constrained; only the actual selected sprites are loaded. Missing pack uses legacy approved public art. Invalid pack falls back to safe symbolic rendering rather than layering corrupted pictures.
- 3D mode and private-only wardrobe assets are NOT part of this public renderer. A renderer selection never grants private access.

## Verified combined public asset archive

The source-verified build generated and checked **21 current public outfit packs** plus the separate 33-variant character-part library. Public wardrobe catalog item IDs are reused; do not confuse the 21 public outfits with the larger 244 public garment records, or equate draft PNGs with finished art.

GitHub Actions run: https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/38946148863
Successful archive: https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/38946148863/artifacts/12067195040

On Venus, download the artifact ZIP, then extract it to an owner-controlled **public** directory so the folder has both:
    Public-V2\outfits\day.default\manifest.json
    Public-V2\character\manifest.json

The archive is a transient CI artifact (30-day retention). Do not place private wardrobe assets, private session grants or any secret tokens in this public folder.

## Set up public 2D on Venus

From a pulled latest main checkout with Sofía installed:

    $Root = Join-Path $env:LOCALAPPDATA 'SofiaAdaLyra\Avatar2D\Public-V2'
    python -m sofia.avatar.vtuber_starter_art --output "$Root" --outfit all
    python -m sofia.avatar.vtuber_character_parts --output "$Root\character"
    $env:SOFIA_AVATAR2D_PUBLIC_ROOT = $Root
    python -m sofia

Use a fresh output directory to avoid overriding reviewed art. The public art root needs per-outfit manifests under outfits/ AND the modular pack under character/; one isolated library of garment PNGs is not a drop-in substitute for these per-outfit layers.

## Frame sequences

- Blink closes both eyes on the middle frame, returning to the original gaze.
- Wink closes only the left eye on the middle frame.
- Ear-flick changes ear sprites from perked to relaxed and back.
- Ear-perk starts with relaxed ears and ends perked.
- Tail gestures switch the actual tail sprite to the authored flick variant and return to the canonical resting/raised pose.
- Smile/skeptical variation is conservative and sourced from current expression labels, never invented as a factual emotion or voice receipt.
- Public head parts do not support every available recolor or hairstyle yet. Selection warns instead of claiming a missing sprite was rendered.

## Focused tests

    pytest -q test/test_avatar2d_character_bundle.py test/test_ui_avatar2d_modular.py test/test_ui_avatar2d_renderer.py test/test_avatar2d_character_parts.py test/test_avatar2d_character_selection.py

Before Gate 4, inspect on real Venus: correct visible sprite alignment/occlusion; render stop during tail flick; public fallback after corrupt PNG; face, ears and tail animations; CPU/RAM while gaming; proof of no private asset disclosure. Full package CI is a separate acceptance gate.

## Remaining work

- Replacing starter artwork with reviewed high-detail consistent master Sofía base and each garment per exact wardrobe source specification.
- Advanced eye tracking, facial visemes linked to proven voice playback, local image cache/performance tuning and fully authenticated pointer-to-INTERACT bridge.
- Actual live 3D mesh, physics and wardrobe fitting, separately from these 2D features.
