# PKG-AVATAR | Starter wardrobe blueprints and style evidence

**2026-09-22 | draft PR #7 | metadata/authoring handoff, not rendered garments.** This addition is AVATAR-only. It does not alter `src/sofia/data/avatar.json`, INTERACT, identity, Constitution, or production data.

## Prebuilt catalog

`src/sofia/avatar/wardrobe_catalog.py` defines **16 proposed garment blueprints** and three slot/layer-validated, normally covered presets:

- `engineer.signature`: breathable underlayer and base undergarment; fitted long-sleeve technical shirt; articulated trousers with tail clearance; asymmetrical engineer jacket; technical socks, mid-calf boots, gloves, modular forearm gauntlets, utility belt, diagonal harness and equipment pouch.
- `lounge.relaxed`: the same two underlayers, oversized soft T-shirt and relaxed sweatpants with tail opening. Colors and cuts beyond the user-requested silhouette are **proposals**, not approved canon or confirmed likes for each individual component.
- `fallback.covered`: the two underlayers, opaque simple long-sleeve top and trousers with tail opening. This is a **blueprint for a future independently verified fallback mesh**, not an already safe renderer asset.

Each blueprint records garment ID/name, existing wardrobe layer and slots, metadata coverage, fox-feature clearance, proposed material and colors, construction/fit notes, relevant named fit anchors, source status, and `asset_ref=None`. `build_starter_wardrobe().manifest()` produces JSON-ready authoring metadata without any network or file writes. This deliberately cannot pass the existing renderer's `require_public_ready()` gate: metadata is not visual opacity, fitted topology, mesh ownership, or asset verification.

Canonical engineer jacket dimensions and palette details are explicitly garment targets from the existing avatar clothing specification, **not bare-body anatomy**. Lounge/fallback colors and many minor pieces remain `design_proposal_review_required`. No licensed/downloaded models are bundled; a proper adult female base and fit/rig checks must precede garment modeling.

## Sparks preference handling

`StyleInput` stores an item/outfit ID, typed `USER_REQUESTED`, `USER_LIKED`, or `USER_DISLIKED` status, source ID, and concrete detail. Earlier outfit requests remain **requested**, separate from later explicit likes.

**New confirmed user input, September 22, 2026:** when asked whether he liked the signature engineer outfit, relaxed lounge outfit, both or neither, Sparks answered **“Both.”** The new `src/sofia/avatar/starter_user_preferences.py` records two separate outfit-level `USER_LIKED` entries with distinct conversation source labels and provides `build_sparks_starter_wardrobe()` or `with_sparks_outfit_likes(catalog)` to include them in wardrobe data without replacing earlier requests or duplicating additions. These are outfit-level likes only, not confirmation of individual colors, accessories, every garment detail, or Sofía's personal preferences.

`project_style_context()` still requires a trusted host to review source ownership/content before presenting positive claims to INTERACT. The source labels are traceability metadata, **not authentication**. Unreviewed likes remain in `awaiting_source_review`. Future INTERACT should use the enriched wardrobe builder plus verified source IDs so it can correctly distinguish `liked_by_sparks`, `requested_by_sparks`, and the empty `sofia_preference_claims` field. This is **not yet connected to live INTERACT or MEM**.

New input from Sparks should be linked to the concrete item/outfit ID and actual source, distinguish request versus explicit like/dislike, and then be reviewed before becoming a grounded text or planner preference. The existing routine/planner `Preference` type is a separate sourced integration step; do not silently convert a request into a positive scoring signal.

## Verification and remaining work

Earlier development: **17 focused tests** for the original starter wardrobe/style files passed on equivalent isolated local source. The new preference-overlay tests plus existing catalog/style tests passed **22/22 in an isolated harness using an older Wardrobe implementation updated with the current slot list/garments method and a minimal wardrobe-routine stub**. That is useful focused evidence, **not an exact current branch checkout or real production dependency test**. Exact GitHub checkout, Windows/CI, full suite, live INTERACT, and authenticated preference-source review remain NOT RUN.

**Next:** inspect exact checkout and full suite; collect item-level color/accessory likes only when explicitly supplied; obtain/review real base `.blend`, model one fitted garment at a time, verify actual opacity/coverage and deformations, connect true asset receipts to shared wardrobe state, and wire style projection into INTERACT after its independent release gate. No merge/deployment is performed here.
