# PKG-AVATAR | Text-chat wardrobe state reflection contract

**Draft PR #7 | AVATAR-only design contract.** This does not modify INTERACT yet.

## Rule

Sofía's currently worn wardrobe state must be represented by one authoritative structured state and reflected consistently across both the visual avatar and text chat.

Text responses may describe or allude to clothing only from the currently acknowledged wardrobe state. They must not invent garments, remove garments, or imply a completed wardrobe change before the wardrobe state machine has acknowledged it.

## Source-of-truth state

At minimum, a resolved wardrobe state should expose:

- selected garment item IDs
- occupied slots and layers
- coverage
- outfit/preset identifier when applicable
- footwear state
- gloves/gauntlets state
- jacket/outerwear state
- accessories
- ear and tail clearance state
- whether a wardrobe transition is proposed, in progress, acknowledged, failed, or rolled back
- revision/timestamp or monotonic wardrobe-state version

The text layer consumes this state. It does not infer wardrobe state from prose.

## Text-chat behavior

Examples:

- Engineer outfit acknowledged: text may naturally reference her jacket, gauntlets, belt, boots, or other actually worn items when context makes that relevant.
- Lounge outfit acknowledged: text may reference the oversized shirt/sweats actually selected.
- Barefoot state acknowledged: text may reflect bare feet, but must not claim boots are still worn.
- Outer coat added/removed: text changes only after the wardrobe transition is acknowledged.
- Unknown/stale state: text stays noncommittal rather than inventing clothing.
- Failed renderer/wardrobe transition: keep the last acknowledged state and do not narrate the failed requested state as current.

## Cross-package integration

AVATAR owns wardrobe truth and typed state. INTERACT may receive a compact projection of the current acknowledged wardrobe state in cognitive context so conversation stays grounded.

MEM may later persist durable wardrobe preferences and history, but remembered preference is not current worn state.

Renderer receipts are evidence of visual application, not proof of physical sensation.

## Acceptance tests

- text and avatar agree on currently worn outfit
- no premature narration before acknowledgement
- failed transition preserves previous textual wardrobe state
- rollback restores both visual and textual state
- stale/unknown wardrobe state does not fabricate clothing
- slot/layer changes are reflected consistently
- outfit changes do not require restarting the conversation
- no clothing state is inferred solely from user wording
