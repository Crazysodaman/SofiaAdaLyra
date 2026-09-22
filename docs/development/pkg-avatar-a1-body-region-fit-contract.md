# PKG-AVATAR A1 | Body, rig and wardrobe fit contract

**2026-09-21 | draft PR #7 | requirements and metadata only, not a completed sculpt, rig or render.** Related code: `src/sofia/avatar/body_contract.py` and `test/test_avatar_body_contract.py`. Preserve `src/sofia/data/avatar.json`, identity, Constitution, INTERACT and production state. Do not mistake this design for an approved or existing asset.

## One Sofía, separate authoring and display assets

- Author **one distinctly adult female base** in a neutral *modeling pose*, not a gender-neutral body. Include her established appearance, human body, two fox ears and a separate fox tail. The user requires complete external adult anatomical detail including nipples, vulva and anus. The vagina is an internal canal, unnecessary for a normal external character mesh. Treat these anatomical details as sculpt requirements, **not** garment slots, touch targets, consent or sensory evidence.
- The tail root emerges dorsally near the tailbone, at the posterior pelvis above the gluteal cleft. The anus remains between the buttocks, separate from the tail root; the vulva remains at its usual anterior perineal location. Tail-opening garment anchors attach to the tail region, **not** to the anus/perineum.
- An unclothed mesh is a **controlled authoring asset** for fitting, deformation and rigging. Ordinary runtime packages must not accidentally include or reveal it: default output is independently verified clothed meshes or a non-body placeholder. A future restricted preview requires a separate trusted, authenticated, explicit opt-in/stop implementation and tests, never a prompt-only flag.

## Canonical data and art review

Read and SHA-256 pin the repository's actual `src/sofia/data/avatar.json` without editing it. Its recorded measurements include height 67 in, bust 33 in, underbust 30 in, waist 26 in and hips 37 in; its documented hair/skin/teal colors include `#8B1E3F`, `#F1E9D8`, and `#19D3C5`. These are design references, not automatic Blender measurements or mesh-quality proof. Violet eyes, ears and tail should follow the accepted character reference; approve their actual geometry, face and stylization visually. A0 engineer/lounge GLBs are **dressed primitive prototypes**, not an A1 anatomical model.

## Body regions, fit slots and landmarks must remain distinct

- `BodyRegion` is a typed map for body *fit/deformation*: face/head, chest, abdomen, back, pelvis/buttocks/perineum, bilateral arms/hands/legs/feet, fox ears and tail root/shaft/tip. This metadata **does not modify INTERACT's existing body-interaction registry** or authorize runtime hit tests.
- `wardrobe.SLOTS` identifies **garment occupancy**, e.g. torso, pelvis, shoulders, bilateral forearms/wrists/hands, ears and tail. `REGION_TO_SLOTS` describes fitting relationships, not geometric coverage or permissions.
- `AuthoringLandmark` marks required anatomical details separately: left/right nipple, vulva, anus and tail root. A landmark must never become a garment attachment ID or a runtime interactive target.
- `FitAnchor` is an immutable **named reference only**: bilateral shoulders, forearms, wrists and feet; torso front/back; waist/pelvis; two ear-clearance references; independent tail-opening clearance. Real Blender empty transforms, rig binding, vertex groups, seam allowances and meshes remain to be authored and checked. `tail.opening.clearance` maps to `TAIL_ROOT → tail`, never `PERINEUM → pelvis`.

## Clothing and deformation rules

Keep the **body separate from clothing layers**. Existing layers are `UNDERWEAR → BASE → MID → OUTER → ACCESSORY`; a garment may occupy multiple slots but cannot conflict with another at the same layer/slot. Fit garments to **one base body and skeleton**: first a fully clothed fallback, then the canonical engineer top/jacket/trousers/socks/boots/belt/gloves/gauntlets, then oversized lounge tee and sweatpants. Use independent left/right gauntlets and an explicit clearance check for ears/tail on jackets, trousers, coats and hoods even when their garment slot is not `tail`/`ears`.

Each eventual real garment should record its base revision, licensed asset and SHA, fitted anchors, cloth-layer/slot occupancy, coverage and opacity evidence, tail/ear clearances, compatible rig revision, pose/clipping tests, audience eligibility and independently issued renderer receipt. Current `asset_ref`, `coverage`, and `tail_clearance` metadata **cannot establish real opacity, fitting or visible coverage**. Hiding portions of the body under clothing is a rendering optimization, not a privacy boundary.

Proposed skeleton: root/pelvis/spine/neck/head; mirrored clavicle/arm/hand/fingers and leg/foot/toes; separate ear bones and a posterior-pelvis-parented multi-bone tail. Choose exact bone counts, face controls, IK, topology and performance budgets only after an actual sculpt, Blender inspection and export roundtrip. Animation is never a completed action until the renderer verifies it. No physical touch/sensation assertions.

## Failure and privacy requirements

At startup, use an independently verified clothed asset or non-body placeholder. Missing or partial garments, a crashed renderer, malformed asset, or revoked permission must **never fall back to the unclothed base**. Test private mesh separation in exports, previews, thumbnails, caches, logs and backups; prevent automatic publishing of authoring material. Any later restricted preview needs actual trusted checks for adult user, authenticated owner, genuinely private local session, current explicit opt-in and external stop. Neither source labels nor LLM words authenticate them.

## Release checkpoints

1. **A1a metadata (current):** body region/landmark/fit-anchor types and isolated negative tests; no 3D anatomy or permission claim.
2. **A1b real base:** author one actual adult female sculpt with required external anatomy and fox features; review front/profile/back, canonical measurements, topology, material provenance and controlled `.blend`/export hashes.
3. **A1c rig:** build consistent body/ear/tail rig with applied transforms, named real Blender anchors, deformations and pose tests, including the tail-root/pelvis separation.
4. **A2 garments:** generate and fit underlayers, fully clothed fallback, engineer and lounge wardrobes, then run bending/sitting/raised-arm/tail-motion/clipping and opacity/coverage tests.
5. **A3 renderer:** integrate with independently authenticated UI/SAFE/INTERACT event and display adapters, verify actual animation and outfit receipts, denial, STOP, crash fallback and resource budget.
6. **Gate:** pinned source/asset hashes, focused Windows tests, full relevant repository integration, supervised Blender inspection, renderer privacy negative tests and separate merge/deployment approval. None of these release steps has been accepted by the current metadata commit.
