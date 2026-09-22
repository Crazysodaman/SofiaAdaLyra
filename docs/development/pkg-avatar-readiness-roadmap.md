# PKG-AVATAR | branch readiness roadmap

**2026-09-22 | draft PR #7 | not merged, integrated or released.** Read the [starter wardrobe blueprint milestone](pkg-avatar-starter-wardrobe-blueprints.md), A1+ dressed visual milestone, measured proxy milestone, A1 proportions and measurement plan, A1 body-region and garment-fit contract, text-chat wardrobe state reflection contract, A0 dressed GLB milestone and dynamic wardrobe/Blender authoring contract. This branch does not modify INTERACT, canonical avatar.json, identity/Constitution or production state.

## Actually built versus remaining

- **Headless wardrobe and virtual scene:** layered garment metadata, fine-grained slots, covered-default proposals, seasonal/activity/late-night lounge routines, reviewed Sparks/Sofía modeled taste candidates, and versioned virtual-object proposals. Earlier 58 and 96 isolated test results belong to different revisions; no current full checkout proof.
- **Shared avatar/text wardrobe authority:** src/sofia/avatar/shared_wardrobe_state.py now provides one revisioned current wardrobe state for both avatar and text, explicit avatar-primary versus text-fallback presentation, pending/failed transition separation, covered-default enforcement, renderer-failure preservation, exact-revision avatar resync, cancellation and a compact INTERACT-facing text projection. test/test_avatar_shared_wardrobe_state.py recorded **19 focused tests passed on equivalent isolated local source**. Exact GitHub checkout, Windows/full-suite and live INTERACT wiring remain NOT RUN.
- **Starter wardrobe blueprints (new):** src/sofia/avatar/wardrobe_catalog.py supplies 16 versioned, unrendered garment specifications across three covered presets: engineer.signature, lounge.relaxed and fallback.covered. Every garment has stable ID, name, existing layer/slots/coverage, colors/materials/construction, fit-anchor references and source status; all asset refs remain None and cannot pass public renderer readiness. src/sofia/avatar/style_context.py exposes sourced user requests separately from explicitly confirmed likes/dislikes for eventual INTERACT grounding. The two known requests are NOT stored as likes. **17 focused metadata/style tests passed on equivalent isolated source** across test_avatar_wardrobe_catalog.py and test_avatar_style_context.py; exact GitHub checkout, full suite, live renderer, preference intake and INTERACT integration NOT RUN. See the [blueprint milestone](pkg-avatar-starter-wardrobe-blueprints.md).
- **A0 dressed GLB:** modular engineer and lounge blockouts from the committed generator; 10 earlier isolated exporter tests and test-fixture GLB roundtrips. No actual Blender acceptance or full-canon export.
- **A1a metadata contract:** src/sofia/avatar/body_contract.py defines adult female base requirements, typed regions, authoring anatomical landmarks separate from clothing and interaction anchors, and fox-tail clearance; 15 isolated metadata tests passed previously. A specification is NOT sculpted anatomy.
- **A1b-0 measured authoring proxy:** committed tools/avatar/measure_calibrated_body.py generates a 20-part guide with 67-in crown reference and actual 33/30/26/37-in guide ring cross-sections; 11 isolated tests previously passed, including GLB import/hash and actual-section remeasurement. Example was minimal fixture, not actual full canonical file. NOT the completed anatomical sculpt or Blender-approved .blend.
- **A1+ visual experiment:** a separate authoring workspace exported a 94-part fully dressed GLB with stylized face/eyes, layered crimson hair, ears, two-tone tail, engineered jacket/harness, gauntlets, utility trousers, gloves and boots. Eight isolated tests passed on that experiment. It remains a clothed proposal, not a verified fitted garment set or the required complete anatomical authoring base.
- **Real-base workflow decision:** the primitive/procedural visual model is retained only as pipeline/measurement evidence. Future production art should start from a proper editable humanoid Blender base and be sculpted against Sofía's approved reference and measurements rather than treating primitive geometry as final art.

## Shared-state behavior now required

1. AVATAR owns one authoritative current wardrobe revision.
2. Avatar and text consume that same revision.
3. Avatar-primary changes commit only after trusted visual success and asset verification.
4. If the renderer is unavailable or failed, a trusted host may explicitly commit the same validated change in text-fallback mode.
5. Text fallback is not a second wardrobe. It is a presentation mode for the same current state.
6. Pending or failed requested clothing remains distinct from current clothing.
7. A returning avatar stays hidden/non-body until it successfully renders the exact current fallback revision.
8. Renderer loss can switch to text fallback without changing current clothing.
9. INTERACT will later consume WardrobeTextProjection and the sourced style-context projection rather than infer clothing or user likes from prose.
10. MEM may later store history/preferences, but memory is never current worn-state authority.

## Next work, dependency order

1. **User preference intake and review:** ask Sparks which exact preset/items/colors they like or dislike; record explicit statements with source IDs as likes/dislikes, not merely requests. Independently review sources before exposing positive/negative taste claims to INTERACT or the outfit planner. Do not claim Sofía has preferences she has not actually selected/reviewed. This work can run alongside 3D creation.
2. **Real 3D base and provenance:** obtain/review a suitable editable Blender humanoid base, pin license/source, shape it against canonical measurements and approved reference, save an inspected .blend, and keep the old procedural meshes only as technical fixtures.
3. **A1 actual continuous adult female sculpt:** create the final body topology and approved silhouette, face, hands, feet, fox ears/tail and required external anatomy in the controlled authoring model. Verify real mesh measurements and front/side/back views.
4. **A1c rig and real anchors:** deformable body, hands/fingers, eyes/face/ears, independent tail bones, actual garment anchor transforms and pose tests.
5. **A2 fit prebuilt garments:** tailor underlayers, independently verified fully clothed fallback, engineer outfit and lounge clothes from the blueprints onto the SAME body/rig. Test actual coverage, opacity, collision, tail/ear openings and motion; only then attach reviewed asset references.
6. **A3 renderer + shared-state adapter:** implement authenticated renderer receipts that drive SharedWardrobeState, hide stale avatar revisions, expose compact current-wardrobe and reviewed-style projections to INTERACT, and verify avatar/text remain one state across success, failure, fallback, restart and resync.
7. **A3 privacy/reliability:** no accidental authoring-base inclusion/fallback, default-denied restricted previews, thumbnail/cache/crash/stop tests and resource budgets.
8. **A4/A5 later:** art-backed virtual props, MEM-persisted sourced wardrobe choices, safe preset-based outfit proposals and supervised DEV/SAFE Blender generation. No general internet or unsupervised host Python/hardware authority.

## Acceptance boundaries

Pin code/art hashes; run exact GitHub checkout on Windows plus suitable full suite; verify Blender artifacts, source/license, actual visual coverage, renderer receipts and reviewed authoring-versus-public asset segregation; obtain separate merge/deploy approval.

**Current truth:** starter wardrobe data and source-aware preference projections are prebuilt AVATAR candidates with focused isolated test evidence. They are NOT garment meshes, verified renderer assets, live chat knowledge, or demonstrated user/Sofía likes. The shared avatar/text wardrobe state machine exists but is not yet wired into live INTERACT or a real renderer. There is still no final sculpt/rig, fitted wardrobe, verified Blender .blend, live renderer, current full-suite acceptance, merge or deployment. AVATAR may develop independently, but cannot bypass CORE → live INTERACT → MEM → Sparks-only private Discord → supervised 24/7 RUN → separately authorized web search.
