# PKG-AVATAR A1 | Proportions and mesh-measurement plan

**2026-09-21 | draft PR #7 | authoring requirements, NOT measured or approved mesh evidence.** Complements [A1 body-region/fit contract](pkg-avatar-a1-body-region-fit-contract.md) and [AVATAR readiness roadmap](pkg-avatar-readiness-roadmap.md). `src/sofia/data/avatar.json` remains the canonical source; do not edit it or turn artist estimates into canon. Work is confined to AVATAR, not INTERACT.

## 1. Source of truth versus artist estimates

| Existing canonical field | Target | Usage / limitation |
| --- | --- | --- |
| Height | **67 in** | Reference human standing stature; document whether ears and footwear are excluded from height in the art measurement protocol; do not silently include tail or ears. |
| Weight | **135 lb** | Character/reference metadata, **not** a spatial constraint, proof of mesh mass, or instruction to compute tissue volume. |
| Bust circumference | **33 in** | Horizontal body circumference at the full bust in a consistent reference pose; record landmarks and measurement plane. |
| Underbust circumference | **30 in** | Separate horizontal circumference beneath the bust. |
| Waist circumference | **26 in** | Circumference at an explicitly marked, repeatable natural-waist landmark. |
| Hip circumference | **37 in** | Circumference at the greatest hip/seat girth; record the actual plane rather than assuming the pelvis bone height. |
| Appearance | Deep-crimson hair `#8B1E3F`, warm-ivory skin `#F1E9D8`, electric-teal accents `#19D3C5`, two fox ears and one tail | Match the canonical visual description and approved character reference. Hair, ears, tail, garments and shoes must not distort *body-only* circumference readings. |
| Bra-size reference | **30C** | Clothing-fit label only; do not derive exact breast shape, volume, nipple position, or mesh measurements from it. |

The canonical JSON also contains *garment* measurements (e.g., jacket shoulder width, length, sleeve length, boot and belt dimensions). Those belong to garment fitting, **not** to bare-body anatomical dimensions. The character reference sheet is an artistic guide, not a calibrated orthographic measurement or an extra canonical numeric source.

## 2. Provisional proportions still needed

Record these as `ARTIST_ESTIMATE` with units, reference image or rationale, revision, and reviewer status. An unknown remains `TBD`, never zero or an invented canonical number:

- **Vertical:** floor-to-crown stature reference, head height, neck length, shoulder-to-waist, waist-to-hip, crotch height, inseam, thigh/calf lengths, ankle-to-floor and foot/sole height. Define the reference pose, foot contact and crown position before measuring.
- **Width and circumference:** biacromial/shoulder span, upper chest and ribcage shape, neck circumference, upper arm/forearm/wrist girths, upper-thigh/knee/calf/ankle girths, and left/right symmetry targets. Width is not circumference; do not mix them.
- **Hands and feet:** palm length/width, finger lengths and thumb range, foot length/width, toe/heel volume and boot allowance. Clothing/gloves/boots use fit tolerances separate from the body mesh.
- **Head and face:** head-to-height ratio, cranium width/depth, jaw/cheek silhouette, eye spacing/tilt, ear-to-head relationship, jaw movement and expression clearance. Face morphology requires visual review, not a numeric deduction from bust/waist/hip.
- **Fox features:** left/right ear root position, ear height/width, fur envelope, hair and hood clearance; tail-root transform near the posterior tailbone, tail length, base/tip girth, fur volume, neutral curve and allowable swing. Tail length/volume do not count toward human standing height. The tail root remains separate from the anus and perineal anatomy.
- **Adult external anatomy:** include the required details specified in the [body contract](pkg-avatar-a1-body-region-fit-contract.md) on the controlled authoring base; do not fabricate numerical locations from clothing or bra sizing. These landmarks are not garment anchors, interactive targets or evidence of sensation.

A **provisional mesh may be blocked out using editable visual ratios** from the approved character reference, but do not present those ratios or artist-proposed values as existing canon. Store every proposed value with provenance and approval status. No physiological inference from the 135 lb reference.

## 3. Measurement procedure and acceptance artifacts

1. **Pin provenance:** read canonical JSON as UTF-8 with optional BOM, record SHA-256 of original bytes, link its exact Git revision, record art reference/rights and mesh revision. Do not claim a cryptographic signature or artist approval from a hash alone.
2. **Set scene conventions:** use a documented real-world Blender unit scale, world-up and forward axes, human crown-to-floor height reference and a single symmetric A- or T-pose. Record whether feet are barefoot; exclude ears, hair, tail, clothes and shoes from stature. Fix a common local origin and mirrored left/right naming.
3. **Build reference landmarks:** mark crown, soles, bust, underbust, waist and max-hip planes on the unclothed human base and keep tail-root/ear transforms distinct. Separate rig/garment anchors from measurement markers. Document precisely where each girth was taken and whether the measurement follows the mesh surface at that plane.
4. **Measure rather than infer:** record actual scene scale, mesh dimension/girth readings and signed error against **67 / 33 / 30 / 26 / 37 in**, with measurement methodology. Use a repeatable cross-section/perimeter tool; an object's bounding-box width is **not** a circumference. Weight and 30C are non-geometric references and get no false pass/fail metric.
5. **Review shape:** capture front, side, rear and three-quarter views in the same camera/pose, plus neutral face and ear/tail silhouettes. Compare with approved character reference; note unapproved or conflicting details. Verify tail root and human anatomy remain distinct without turning anatomical landmarks into garment slots.
6. **Test motion and fit after silhouette review:** hands/shoulders, hip/knee bend, seated pose, tail swing, face/ear expression; then fit the same base rig to underwear, engineer and lounge garment prototypes with actual clearances, opacity and coverage reviewed in renderer. No garment metadata flag alone proves visual coverage.
7. **Record result:** source `.blend` path and rights, measured dimensions, screenshots/visual signoff, mesh/GLB SHA-256, Blender version, export/import transforms, collision/clipping findings and an explicit `PASS`, `FAIL`, or `NOT_RUN` for each test. Only a real inspected asset can pass A1b.

## 4. Non-goals and release boundary

This plan does **not** generate the adult base sculpt, `.blend`, skeleton, fitted clothing or live renderer. It does not authorize private/unclothed preview, give Sofía physical sensations, modify canonical identity or Constitution, or grant tools/host access. Keep normal runtime clothed with independently verified garments or a non-body placeholder if assets are missing. A1b sculpt, A1c rig, A2 wardrobe and A3 renderer remain open milestones; separate approval remains required for merge and deployment.
