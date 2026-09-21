# PKG-UI | branch readiness roadmap

**2026-09-21 | draft PR #6 | baseline head `e3da480dfd172cb98e42a604265b322610cfe916`.** Also read `pkg-ui-offline-workbench-review.md` and PR #4's `pkg-ui-sofia-workbench-concept.md`. Proposed AVATAR owns mesh/props; UI owns actual presentation, input and accessibility. Never gate text chat on art assets.

## Prepared and evidence

In-memory `sofia.workbench` models source-linked loose pages, sticky notes, notebooks, binders and books, revisions, private candidate reflections and deliberate sharing. **38 focused tests passed on equivalent isolated source**, 96 with independent AVATAR fixtures. Main implementation/test GitHub blob hashes were checked against the staged originals at original PR creation. Not an app, screen renderer, authenticated user service or durable memory store.

## Ordered implementation/acceptance

1. **U0 review:** define desktop/mobile responsive mockups, accessible keyboard/touch/screen-reader semantics, persistent text-first conversation dock, optional avatar stage and low-resource/gaming mode. Confirm source-visible notes versus private reflection; bind real authenticated owner/audience through SAFE, never trust model-supplied IDs.
2. **U1 text client:** build actual chat input, preserved unsent draft, chronological attributed messages, evidence/unknown and action-state badges, stop/cancel, search of *authorized* history, model-streaming only where supported and renderer-down text-only fallback. Validate actual Windows desktop and mobile-size navigation, first-token latency and restart persistence with MEM.
3. **U2 visual objects:** bind pages/sticky notes/notebooks/binders/books to MEM/ACT reviewable records with immutable original/source IDs, owner, ACL, timestamps, revision, archive, correction and deletion; render shelf/desk without exposing existence of private objects to unauthorized viewers. Never display fabricated continuous thinking, spontaneous activity or another person's notes.
4. **U3 shared scene:** integrate AVATAR and INTERACT typed hit tests with trusted renderer receipts: propose → authorize → actually acknowledge → persist. Both Sparks and Sofía may annotate/hold/offer a virtual notebook with conflicts/undo; avatar cannot read unsent drafts, edit Sparks-authored messages or click arbitrary OS windows.
5. **U4/U5 quality:** actual canonical clothed model, consistent gaze/ears/tail and optional outfits after art is approved; reduced motion, high contrast, font scaling, chat-only mode, resource ceilings and proper voice/screen consent. Disable heavy animation instead of blocking conversation. Renderer loss must not crash core or invent completed gestures.
6. Test current branch Windows focused/combined/full, real client hit testing and privacy negative cases, actual renderer crashes and user stop. Respect Discord → 24/7 → later search. Avatar/voice are **not** prerequisites for Discord text chat.

## Review decisions

Choose UI runtime/framework, display/overlay/window interaction permissions, local-only vs remote client access, book/page visual language, privacy of screenshots/previews/cache and how Sofía proposes presentation choices without treating model preferences as subjective proof. Confirm scene persistence, accessibility criteria and latency/VRAM budgets on actual target machines.

**Exit:** in-memory workbench slice offline tested; actual GUI/render, authenticated principal, MEM/AVATAR integration and Windows/full/live acceptance = NOT RUN. No merge/deploy.
