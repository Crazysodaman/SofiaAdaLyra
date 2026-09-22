# PKG-AVATAR | Starter wardrobe blueprints and style evidence

**2026-09-22 | draft PR #7 | metadata/authoring handoff, not rendered garments.** This addition is AVATAR-only. It does not alter `src/sofia/data/avatar.json`, INTERACT, identity, Constitution, or production data.

## Prebuilt catalog

`src/sofia/avatar/wardrobe_catalog.py` defines **16 proposed garment blueprints** and three slot/layer-validated, normally covered presets:

- `engineer.signature`: breathable underlayer and base undergarment; fitted long-sleeve technical shirt; articulated trousers with tail clearance; asymmetrical engineer jacket; technical socks, mid-calf boots, gloves, modular forearm gauntlets, utility belt, diagonal harness and equipment pouch.
- `lounge.relaxed`: the same two underlayers, oversized soft T-shirt and relaxed sweatpants with tail opening. Sparks has now approved the described lounge concept and likes this outfit, but not every individual garment or print has a separately confirmed preference.
- `fallback.covered`: the two underlayers, opaque simple long-sleeve top and trousers with tail opening. This is a **blueprint for a future independently verified fallback mesh**, not an already safe renderer asset.

**Optional fourth outfit design, not an automatic preset:** [occasional graphic T-shirt variation](pkg-avatar-lounge-graphic-tee-variation.md) adds one more garment blueprint and a separate explicit-choice `lounge.graphic` outfit. The plain lounge T-shirt stays default. The graphic is an original print design proposal, not yet approved artwork, a liked individual graphic, or a renderer asset.

Each blueprint records garment ID/name, existing wardrobe layer and slots, metadata coverage, fox-feature clearance, proposed material and colors, construction/fit notes, relevant named fit anchors, source status, and `asset_ref=None`. `build_starter_wardrobe().manifest()` produces JSON-ready authoring metadata without any network or file writes. This deliberately cannot pass the existing renderer's `require_public_ready()` gate: metadata is not visual opacity, fitted topology, mesh ownership, or asset verification.

Canonical engineer jacket dimensions and palette details are explicitly garment targets from the existing avatar clothing specification, **not bare-body anatomy**. No licensed/downloaded models are bundled; a proper adult female base and fit/rig checks must precede garment modeling.

## Sparks preference handling

`StyleInput` stores an item/outfit ID, typed `USER_REQUESTED`, `USER_LIKED`, or `USER_DISLIKED` status, source ID, and concrete detail. `starter_user_preferences.py` records Sparks' explicit **“Both”** answer as likes for `engineer.signature` and `lounge.relaxed`. `lounge_graphic_tee.py` records the later **occasional graphic tee** as `USER_REQUESTED`, not a confirmed like for the graphic itself. No unconfirmed individual garment or print favorite is invented and no Sofía preference is manufactured.

The source-aware `project_style_context()` produces JSON-ready separate requests/confirmed likes/dislikes for eventual INTERACT context; any proposed like/dislike needs an independently reviewed source ID before it is exposed as confirmed. The trusted host must authenticate/verify source ownership and content. This code is *not* wired into live INTERACT or MEM yet.

## Verification and remaining work

Previously **22 focused tests passed in an equivalent isolated harness** for starter wardrobe, style context and explicit outfit likes; the new graphic variation's six focused tests have been committed but **not executed in an exact checkout**. Full repository/Windows/CI tests remain NOT RUN. Earlier checks covered slots/layers, tail clearance, covered presets, metadata-only renderer denial, manifest serialization, source labels, and approved versus unreviewed style evidence.

**Next:** inspect exact checkout and full suite; obtain/review a real base `.blend`, model one fitted garment at a time, verify actual opacity/coverage and deformations, connect true asset receipts to the shared wardrobe state, and wire style projection into INTERACT after its independent release gate. No merge/deployment is performed here.
