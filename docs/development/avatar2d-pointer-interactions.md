# Sofía 2D VTuber: precise click and gesture interaction

**Owner intent:** Any actually visible waist-up part is selectable, and Sofía can identify what was selected through a source-authenticated virtual interaction.
**Implementation snapshot:** src/sofia/avatar/vtuber_hit_test.py and test/test_avatar2d_hit_test.py provide pure geometry. Real desktop input binding, interaction ledger, conversation/animation routing and art geometry remain **open**. The existing synthetic test method from_lab_pointer is *not* an authenticated desktop input endpoint.

## Semantics

A click identifies only the *rendered* region, visible garment and exact revision/frame. A click is not automatically a pat, stroke, sexual interaction, physical sensation, permission to touch, or proof that Sofía wanted contact. Repeated tap, hold, drag and stroke need independent observed gesture phases and contextual policy. Positive, negative, neutral or no reaction remain possible; never infer literal touch, pleasure or feeling.

## Coverage for the waist-up art

| Clickable visual item | Canonical interaction target |
| --- | --- |
| Each fox ear, base and tip | left-ear, right-ear and registered subparts |
| Hair and visible scalp | hair, scalp |
| Face, left/right cheek, forehead, nose, lips, jaw and chin | Existing region IDs; unmapped eye subparts fall back to face only when explicitly mapped |
| Neck and shoulders | neck, left-shoulder, right-shoulder |
| Visible upper arms, forearms, wrists and hands | Side-specific registered region |
| Torso | torso in the covered public portrait; restricted region only for authorized actually visible private art |
| Jacket, sleeve, collar, top or overlay | Top painted garment/layer ID plus visible canonical region; not skin contact |
| Tail base, length and tip | tail-base, tail-length, tail-tip |
| Temporary tattoo, piercing or accessory | Top visible cosmetic layer plus region, without changing anatomy |

The visible part may not correspond to every canonical body region. Off-screen legs, feet and other non-rendered parts cannot be clicked. Transparent pixels are misses, not guessed body hits.

## Existing technical parts

- Canonical INTERACT region registry: src/sofia/interaction/core.py.
- Source interaction ledger and stop: src/sofia/interaction/ledger.py, currently built around authenticated user-authored chat text.
- Current Tk avatar renderer: src/sofia/ui/avatar_renderer.py. Its canvas in src/sofia/ui/desktop.py currently has no avatar pointer handler.
- Pure 2D pointer hit geometry: src/sofia/avatar/vtuber_hit_test.py with exact per-frame alpha-mask, affine rotation/mirror/pan/scale, z-order, original garment ID, asset digest, presentation revision and audience redaction.

## Next implementation: trusted desktop event path

1. Register mouse press/release/move against the actual avatar viewport, with event consumption preventing click-through to underlying UI.
2. The trusted application owns the current authenticated principal and session and obtains *really displayed* frame ID, checked asset bundle digest, presentation revision, viewport dimensions and final image transforms. A model or untrusted client cannot claim any of these.
3. Resolve actual pixel hit through hit_test_avatar. Abort when frame/revision stale, outside viewport, transparent, unmapped or unauthorized.
4. Revalidate principal, current session, operator STOP, interaction STOP and consent. Private/optional nude input must independently require owner-private authenticated context, private_chat/adult_avatar/current opt-in and approved grants. No private region disclosure when denied.
5. Introduce a dedicated typed source ui_avatar_input. Do **not** call the virtual lab pointer fixture for real input; do **not** fabricate equivalent owner chat or pass UI coordinates straight to model text.
6. Record minimal, deduplicated source-linked event and policy result in existing canonical state via INTERACT. Don't persist raw coordinates in long-term memory by default.
7. Treat a single click as a virtual tap at most. Only observed motion/duration supports stroke/hold/release. Attach begin/update/end/cancel, actor/session identity and source reference.
8. Let Sofía respond, decline, ignore or ask about the virtual event in context. Route optional reaction to existing ExpressionRuntime and wait for truthful output receipts. No automatic emotional response or intimacy from region alone.
9. Cancel all pending events on renderer stop, logout, audience switch, grant revocation, STOP, screen lock or displayed frame replacement.
10. Include private click tests covering garment overlays, nude optional pack only while authorized, covered fallback on revoked authority, no public region/asset leakage.

## Acceptance

- Public click coverage for every *actually painted* selectable region, not invisible geometry.
- No undergarment or invisible body target guessing; alpha, occlusion and tail/ear transform correctness.
- Mirror/pose scaling and actual viewport crop correctness.
- Distinguish click/tap/hold/drag; no click automatically means pat or stroke.
- At-most-once typed UI event; valid actor identity, STOP and consent enforced outside renderer.
- Private area only accessible while continuously authorized; mid-gesture revocation cancels and clears hit result.
- Real UI input to canonical INTERACT, cognition and optional expression receipt demonstrated on Venus.
- Exact-SHA automated tests plus actual supervised acceptance, separately tracked.

**V18 mapping:** CA-504, CA-505, CA-507, CA-901, CA-905, CA-3112, CA-6008, CA-1011 and CA-6310, plus existing PKG-AVATAR/INTERACT/UI/SAFE/VERIFY. No duplicate CA task is created and nothing is marked Gate 4 based on this plan.
