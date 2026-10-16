# Sofía waist-up 2D VTuber: engineering build specification

**Owner decision (October 2026):** Waist-up 2D layered puppet first. Include public covered and owner-authorized private versions; the private version may support the existing private wardrobe and an optional nude torso model. 3D remains optional later.

**Status:** Build-ready design, NOT proof that artwork, an actual layered renderer, rigging, code tests or live acceptance exist.

**Companion:** avatar2d-waist-up-art-production-sheet.md.
**Public wardrobe sprite implementation and first-run:** [Generate public waist-up garment PNGs and enable the optional desktop renderer](avatar2d-public-wardrobe-first-run.md). The generator and UI renderer use the 295 existing JSON garment records; it does not duplicate the wardrobe or create private nude art.
**Pointer integration:** [Precise clickable avatar interaction](avatar2d-pointer-interactions.md), with implementation groundwork in src/sofia/avatar/vtuber_hit_test.py. **Important:** geometry and tests do not themselves enable desktop clicks or model awareness of clicks. Related: pkg-avatar-presentation-autonomy-contract.md, avatar-morphology-autonomy-v18.md, avatar-screen-interaction-contract.md.

## 1. Architecture, preserving existing owners

Use one canonical identity, one presentation authority, one canonical sofia.db writer, one expression runtime and existing SAFE gates. The 2D renderer is a replaceable view of already-authorized presentation data, not a second cognition engine or database.

| Existing module | Use |
| --- | --- |
| src/sofia/embodiment/avatar.json and model.py | Immutable body baseline: two fox ears, one tail, two arms and two legs |
| src/sofia/avatar/presentation.py | AppearanceState, PresentationAuthority, AudienceScope, AttireMode, PresentationProjection; keep revision checks |
| src/sofia/avatar/presentation_store.py | Existing avatar_presentation_state, avatar_style_favorites, avatar_appearance_history in canonical sofia.db |
| src/sofia/avatar/presentation_runtime.py | Existing bootstrap and migrations; do not overwrite Venus user state with new seed |
| src/sofia/avatar/appearance_action.py and clothing_action.py | Existing authenticated conversation-side appearance/wardrobe requests |
| src/sofia/avatar/wardrobe.py, wardrobe_catalog.py and wardrobe_matrix.py | Actual garment IDs and private_only/covered_default policy |
| src/sofia/avatar/private_grant.py | Trusted private owner session, private_chat and adult_avatar settings, explicit opt-in and operator STOP |
| src/sofia/application/expression_runtime.py | ExpressionDecision and independent output receipts |
| src/sofia/ui/avatar_renderer.py and desktop_controller.py | Existing AvatarRenderRequest, paint completion/cancel semantics and desktop integration |
| src/sofia/avatar/presentation_routine.py | Existing context-driven wardrobe policy; avoid a second scheduler |

The current Tk renderer is symbolic; it is not a real rigged/layered VTuber. The wardrobe catalog is design metadata, not proof that matching PNG parts exist.

## 2. MVP acceptance contract

Provide a transparent-background, waist-up portrait with approved canonical crimson/violet hair, violet irises, dark violet fox ears, visible dark violet tail, and covered practical engineer outfit.

Required v1 public visual abilities:
- blink, eye open/half/closed, left/center/right gaze, independent brow expressions;
- mouth closed plus three talk shapes gated by actual audio playback, not pretend model speech;
- smile/frown/skeptical/focused expressions, two head tilt ranges;
- independent fox ear perk/relax/flatten, calm/flick/wag tail poses;
- idle breathing, small torso/head motion, simple hair sway;
- at least two *actual* artwork-supported hairstyles and two compatible public torso outfits;
- tintable hair and irises, freckles, makeup, optional tattoo/piercing overlays;
- durable current look, favorites/history and restart restoration;
- accurate cancel/failed/visible-frame receipts.

Target (must be measured on Venus): approximately 30 FPS while visible, idle/hidden low-work mode, capability to drop to 15 FPS or freeze secondary effects when gaming or under resource pressure. No always-on camera/mic access, desktop control or GPU preemption.

Public fallback must always be covered, available offline and usable if assets, rig or backend fail. Text chat continues independently.

## 3. Verified asset manifest and layout

Suggested source structure (new files, not yet claimed to exist):

    assets/avatar2d/public/manifest.json
    assets/avatar2d/public/base/
    assets/avatar2d/public/eyes/
    assets/avatar2d/public/hair/
    assets/avatar2d/public/mouth/
    assets/avatar2d/public/brows/
    assets/avatar2d/public/ears/
    assets/avatar2d/public/tail/
    assets/avatar2d/public/outfits/
    assets/avatar2d/public/overlays/
    src/sofia/avatar/vtuber_manifest.py
    src/sofia/avatar/vtuber_state.py
    src/sofia/avatar/vtuber_animation.py
    src/sofia/avatar/vtuber_look_builder.py
    src/sofia/avatar/vtuber_asset_proposals.py
    src/sofia/ui/avatar2d_renderer.py

Private image bytes must instead be under a separately controlled local private asset root, NOT committed to a public repository/release or stored in public package examples.

Manifest schema: sofia.avatar2d.manifest.v1. Each verified bundle has immutable ID, sha256 digest, creator/provenance/license, audience classification, compatible renderer version, canvas/pivot, covered fallback, and asset capability declarations.

Each layer records stable ID, relative file path, actual file digest, source pixel dimensions, z index, anchor/pivot, parent and crop, slot/variant/visibility, optional tint mask, bounded transforms and compatible outfit IDs. Verify everything before enabling the asset.

Reject duplicate/unknown layer IDs, absolute paths, traversal, escaping symlinks, mismatched digests, overlarge/decompression-bomb images, missing fallback layers, incompatible outfits, unsafe audience mixes and unverified generated assets. Never let image metadata, generated prompts or source assets execute code.

## 4. Visual state and animation

Define a pure derived VisualState, never a new persistent appearance authority. Source it from:
1. Already audience-checked PresentationProjection (including source revision).
2. Settled ExpressionDecision and actual renderer-consumable gesture/pose.
3. Voice runtime playback events, not generated prose or an unverified speak request.
4. Reviewed manifest capabilities, current monotonic animation time and renderer budget.

VisualState fields: presentation_revision, expression decision ID, verified bundle digest, eye openness and gaze, viseme, speaking flag, brows, head angle/offset, ear angles, tail segment angles, breathing phase, posture, hair/outfit variant references, public overlays and intended frame ID. Clip all numeric motion to safe defined ranges. Never include private anatomy attributes in public VisualState.

Animation primitives: frame/keyframe interpolation with easing, no new LLM in frame loop; blink timing, breathing, subtle hair drift, ear/tail secondary motion, gaze and mouth changes. Effects must be constrained and interruptible.

The layered renderer implements current AvatarRenderRequest and render completion callback semantics; it must not claim displayed frames until the correct presentation revision and image bundle were actually painted. Missing assets/cancel/mute/renderer stopped yield unavailable or canceled receipt, never rendered/spoken.

## 5. Public and PRIVATE profiles

There are two *presentation profiles* with different allowed assets, **not two Sofía identities** or independently controlled state machines.

**PUBLIC:** fully covered outfit, public asset bundle and safe projections only; guaranteed default and fallback.

**PRIVATE:** existing private-only wardrobe and optional nude waist-up sprite pack; only during authenticated owner-private session with separately enabled private_chat and adult_avatar authority where applicable, explicit current opt-in, and inactive operator STOP. This must be checked through the existing PrivatePresentationGrantResolver, not by a renderer-provided boolean, chat instruction or LLM claim.

Protected render sequence:
1. Confirm trusted principal and private audience, actual PermissionStore rights, current opt-in and operator STOP clear. Existing SAFE FIDO2-backed authorization requirements apply to changes that require it.
2. Commit desired private outfit/nude state through existing PresentationAuthority proposal+grant+commit and PresentationStore persistence. Do not update last_daily with private or nude.
3. Obtain PRIVATE projection with current grant, check revision, scope, asset bundle audience and outfit compatibility before loading or drawing private art.
4. Display an explicit owner-private indicator. Recheck before subsequent private frame batches and on trust/session change.
5. On audience change, opt-out, expiry, screen lock, STOP/revocation, renderer stop, errors or unsupported private asset: immediately clear private pixels/pending jobs/caches and draw the **covered public fallback**. Receipt must report canceled/unavailable rather than pretending private image appeared.
6. Never attach private art to Discord/mobile/public transport, general logs, notifications, generated previews, public snapshots, auto-backups, or release bundles. Use separately authorized protected backup handling.

Nude is a private adult virtual avatar state, not a blanket permission or emotional behavior. Never generate or display nude without explicit authenticated opt-in. If optional nude artwork does not yet exist, respond honestly that the private art asset is unavailable and present the covered fallback. The private sprite package may include only visible waist-up anatomy; confidential attributes for other body regions are not part of its public manifest or look history.

OS-level screen capture cannot be reliably prevented by an application-layer toggle; offer a private-mode warning and an owner-accessible screen-sharing safe switch, but do not claim absolute screenshot protection.

## 6. Sofía-generated looks

Autonomous look composition should be built on the **existing** presentation state, style favorites/history, wardrobe policy and RUN schedule. No model may alter canonical anatomy, grant itself private authority, or invent missing render assets.

- Choose from present, hash-verified, audience-compatible approved hair/eye/outfit/accessory layers; apply safe tint changes and bounded gestures.
- Use real available assets and corrected/preferences evidence, not simply recent chat approval as a lifelong preference.
- Follow cooldown and daily change budget; restore the existing look at reboot and honor owner-chosen outfits.
- Validate before applying, then propose and commit revision through PresentationAuthority; persist with PresentationStore.persist_mutation, record evidence-linked reason/asset digest, and request a render acknowledgement.
- For a new visual concept without compatible art, create a bounded candidate with prompt summary, base-version, suggested parts, license provenance, review state and verification outcome; do not silently call it a completed look.
- Allow private candidate design only within authorized private scope; entering nude/private visualization always requires live owner opt-in. Proposal generation is not an approval token.

## 7. Phased source work and acceptance

| Batch | Work | Must prove |
| --- | --- | --- |
| A | Typed manifest validator, safe file resolver, VisualState and capability checks | Reject malformed and unsafe assets; no new writer |
| B | First actual public waist-up art bundle and layered renderer | Real frames, correct draw ordering, render/cancel receipts |
| C | Eye/brow/mouth/ears/tail/hair/body interpolation and performance control | Real timing, mute, STOP, interruption and resource tests |
| D | Public wardrobe part mapping, saved looks and on-screen style controls | Correct revision, restart, old snapshots, missing asset behavior |
| E | Private wardrobe and optional nude sprite package, protected transition | Authorized preview, revocation mid-frame, covered fallback, no egress |
| F | Sofía's approved-part look creation and candidate asset proposals | Choice provenance, stable preferences, rate limit, no auto-private |
| G | Supervised Windows Venus and optional Linux validation | Exact SHA CI, real host visuals, measured FPS/resources, no invented Gate 4 |

Use existing test marker ownership: PKG-AVATAR primary, PKG-UI for real renderer, PKG-SAFE for authority, PKG-INTERACT for expression, PKG-VERIFY for evidence. New tests should cover wrong audience/principal, adult flag false, opt-in false, STOP, revoked grant mid-frame, stale revisions, missing nude art, content hashing, resource budgets, screen-share masking, public fallback, 24h/restart tests and text-only fallback.

## 8. Existing V18 alignment (not new CA tasks)

CA-504/507: expression-to-visual intent. CA-505/905: honest rendered/speech receipts and Venus acceptance. CA-6008/1011: expression and environmental/voice alignment. CA-3112: distinguish simulated, requested and actual effects. CA-901/2307: cross-package and failure-injection tests. CA-6310: private egress boundaries. Do not change the task ledger to Gate 4 without tests, CI and real-host receipts.

**Deferred:** Full-body IK, real hair-strand physics, professional Live2D/Inochi deformation, motion capture, new LLM for rigging, unattended private image generation/activation, and any 3D renderer.
