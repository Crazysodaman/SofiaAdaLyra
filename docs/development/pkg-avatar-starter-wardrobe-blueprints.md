# PKG-AVATAR | Starter wardrobe blueprints and style evidence

**2026-09-22 | draft PR #7 | metadata/authoring handoff, not rendered garments.** This addition is AVATAR-only. It does not alter `src/sofia/data/avatar.json`, INTERACT, identity, Constitution, or production data.

## Prebuilt catalog

`src/sofia/avatar/wardrobe_catalog.py` defines **16 proposed garment blueprints** and three slot/layer-validated, normally covered presets:

- `engineer.signature`: breathable underlayer and base undergarment; fitted long-sleeve technical shirt; articulated trousers with tail clearance; asymmetrical engineer jacket; technical socks, mid-calf boots, gloves, modular forearm gauntlets, utility belt, diagonal harness and equipment pouch.
- `lounge.relaxed`: the same two underlayers, oversized soft T-shirt and relaxed sweatpants with tail opening. Colors and cuts beyond the user-requested silhouette are **proposals**, not approved canon or confirmed likes.
- `fallback.covered`: the two underlayers, opaque simple long-sleeve top and trousers with tail opening. This is a **blueprint for a future independently verified fallback mesh**, not an already safe renderer asset.

Each blueprint records garment ID/name, existing wardrobe layer and slots, metadata coverage, fox-feature clearance, proposed material and colors, construction/fit notes, relevant named fit anchors, source status, and `asset_ref=None`. `build_starter_wardrobe().manifest()` produces JSON-ready authoring metadata without any network or file writes. This deliberately cannot pass the existing renderer's `require_public_ready()` gate: metadata is not visual opacity, fitted topology, mesh ownership, or asset verification.

Canonical engineer jacket dimensions and palette details are explicitly garment targets from the existing avatar clothing specification, **not bare-body anatomy**. Lounge/fallback colors and many minor pieces remain `design_proposal_review_required`. No licensed/downloaded models are bundled; a proper adult female base and fit/rig checks must precede garment modeling.

## Sparks preference handling

`StyleInput` stores an item/outfit ID, typed `USER_REQUESTED`, `USER_LIKED`, or `USER_DISLIKED` status, source ID, and concrete detail. The two known outfit requests are entered as **requested**, not liked. No unconfirmed favorite is invented and no Sofía preference is manufactured. The source-aware `project_style_context()` produces JSON-ready separate requests/confirmed likes/dislikes for eventual INTERACT context; any proposed like/dislike needs an independently reviewed source ID before it is exposed as confirmed. The trusted host must actually authenticate/verify source ownership and content. This code is *not* wired into live INTERACT or MEM yet.

New input from Sparks should first be linked to the concrete item/outfit ID and actual conversation source, distinguish request versus explicit like/dislike, and then be reviewed before becoming a grounded text or planner preference. `Preference` in the existing routine/planner is a separate source-backed integration step; do not silently convert a request to a positive scoring signal.

## Verification and remaining work

**17 focused tests passed on equivalent isolated local source** across starter wardrobe and style context. The committed source/test blobs were copied from those files; full repository/Windows/CI tests remain NOT RUN. These tests cover slots/layers, tail clearance, covered presets, metadata-only renderer denial, manifest serialization, malformed references, non-invention of likes, and approved versus unreviewed style evidence.

**Next:** inspect exact checkout and full suite; gather Sparks' explicit likes/dislikes and record them with source; obtain/review real base `.blend`, model one fitted garment at a time, verify actual opacity/coverage and deformations, connect true asset receipts to the shared wardrobe state, and wire style projection into INTERACT after its independent release gate. No merge/deployment is performed here.
