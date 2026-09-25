# PKG-AVATAR | Text-chat wardrobe state reflection contract

**Draft PR #7 | AVATAR-owned shared state.** This does not modify INTERACT yet.

## Rule

Sofía has **one authoritative wardrobe state**. The visual avatar and text chat are two presentation surfaces of that same state, not separate clothing realities.

The shared wardrobe state module implements the state machine. INTERACT should consume its compact WardrobeTextProjection later rather than infer clothing from prose.

## Presentation priority

1. **Avatar primary:** when a trusted renderer has successfully applied and verified the current wardrobe revision, the avatar may be visible and text may describe that same revision.
2. **Text fallback:** when the avatar is unavailable, hidden, stale or failed, the same validated wardrobe change may be explicitly acknowledged in text-fallback mode. The avatar remains hidden/non-body until it successfully resynchronizes to the exact current revision.
3. There is never an automatic "renderer failed, therefore pretend it worked" transition. Fallback is a separate explicit host action.

Text fallback is therefore not a second wardrobe. It is a presentation mode for the same authoritative state.

## Source-of-truth state

The acknowledged state exposes:

- monotonic wardrobe revision
- selected garment item IDs
- structured worn-item metadata for text grounding: item name, layer, slots, coverage, ear clearance and tail clearance
- resolved coverage
- outfit/preset identifier when applicable
- presentation mode: avatar_primary or text_fallback
- exact avatar-synced revision, or None
- whether the avatar is safe to present for the current revision

A separate unresolved transition exposes:

- operation ID
- expected source revision
- requested garment item IDs
- requested outfit/preset identifier
- status: pending or render_failed

The current outfit and unresolved requested outfit are deliberately separate so text cannot accidentally promote "trying to change" into "currently wearing."

## State transitions

### Avatar-primary change

1. AVATAR validates slots/layers/coverage through the existing Wardrobe.
2. SharedWardrobeState.propose() records a pending change without mutating current state.
3. A trusted renderer adapter attempts to apply that outfit.
4. Only acknowledge_avatar(renderer_succeeded=True, assets_verified=True) commits the change.
5. The new state revision is simultaneously the text truth and visually synced avatar revision.

If renderer application fails, the previous acknowledged outfit remains current.

### Text fallback change

If no avatar renderer is available, or an avatar attempt failed:

1. the host must explicitly establish trusted renderer_unavailable=True;
2. acknowledge_text_fallback() commits the same already-validated wardrobe change;
3. current wardrobe revision advances once;
4. text may reflect the new current state;
5. the avatar is not considered visible/synced for that revision.

When the avatar returns, sync_avatar() must successfully apply the **exact current revision** before switching back to avatar-primary mode.

### Renderer loss without clothing change

force_text_fallback() can hide an unavailable/stale avatar without changing what Sofía is currently wearing or incrementing the wardrobe revision.

## Text-chat behavior

INTERACT should receive WardrobeTextProjection and follow these rules:

- natural clothing references use only current fields;
- pending fields may be used only to describe a requested/in-progress/failed change, never as current clothing;
- a failed visual transition leaves current clothing unchanged;
- text-fallback current state is still authoritative current clothing;
- avatar visibility is not inferred from clothing state;
- stale/unknown information stays noncommittal;
- clothing is never inferred solely from user wording;
- normal shared state must satisfy the existing covered-default policy.

Examples:

- Engineer outfit current: text may naturally reference its worn items when relevant.
- Lounge change pending: text can indicate a change is being attempted, but should not speak as though lounge clothes are already current.
- Renderer fails: current engineer outfit remains current.
- Renderer unavailable and fallback explicitly accepted: lounge clothes become the single current state in text fallback.
- Renderer later returns: it must render the lounge revision before being shown.

## Cross-package integration

- **AVATAR owns current wardrobe truth and transitions.**
- **INTERACT consumes WardrobeTextProjection; it does not own or synthesize wardrobe truth.**
- **MEM may later persist durable preferences/history**, but a memory of liking or previously wearing an outfit is not current worn state.
- **UI/renderer supplies independently authenticated visual receipts** before AVATAR accepts visual synchronization.
- A render receipt is evidence of presentation only, not proof of physical sensation.

## Implemented acceptance checks

The focused shared-state test file covers:

- one authoritative state drives text projection
- no premature narration before acknowledgement
- verified avatar success commits one state for both surfaces
- failed renderer change preserves previous current outfit
- failed or rendererless change can explicitly commit as text fallback
- returning avatar must sync the exact current fallback revision before visibility
- failed resync remains text fallback
- renderer loss hides avatar without changing clothes
- partial/uncovered normal states are denied
- stale/concurrent changes are denied
- fallback requires a trusted renderer-unavailable fact
- non-boolean receipt fields are denied
- cancellation preserves current state
- unresolved state cannot be snapshotted as settled
- avatar-primary initialization requires verified visual state
- failed transition remains visible to text as failed, but never current

**Recorded development result:** 19 focused tests passed on an equivalent isolated local source. Exact GitHub checkout, Windows full-suite and live INTERACT integration remain NOT RUN.

## Release boundary

This code does not render, authenticate receipts, generate natural-language text, persist state to production, modify INTERACT, or grant host/network authority. No merge or deployment is implied.
