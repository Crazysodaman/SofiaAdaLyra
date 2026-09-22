# PKG-AVATAR | Optional relaxed graphic T-shirt

**2026-09-22 | AVATAR draft PR #7 | authoring metadata only.** Sparks confirmed that the existing relaxed lounge design is fine and requested that Sofía wear a graphic T-shirt from time to time. This does **not** establish that Sparks likes any particular print design, or that Sofía has expressed a separate preference.

## Outfit design

The existing `lounge.relaxed` outfit remains the ordinary/default combination: underlayers, oversized plain jersey T-shirt, and relaxed sweatpants with fox-tail opening. Its colors, material target, fit and coverage are unchanged.

`src/sofia/avatar/lounge_graphic_tee.py` adds a distinct `lounge.graphic_tee` garment blueprint with the **same** T-shirt silhouette, material, layer, fit anchors, slots and coverage. Its original front graphic is a pending art decision. Suggestions, not approved graphics, include a minimal fox-and-circuit emblem, a schematic constellation, or a small original engineering joke / abstract circuitry. Avoid licensed third-party characters or trademarks without review.

The alternate `lounge.graphic` selection substitutes only the T-shirt. Underlayers, sweatpants and fox-tail clearance remain unchanged. The optional plan is deliberately **not registered** in the default `WardrobePrebuild.presets`, so the existing automatic outfit planner cannot select the graphic every time. A trusted host can explicitly request it using `GraphicLoungeVariation.select_lounge(graphic_requested=True)`; `False` returns the original plain lounge preset. Actual occasional rotation frequency and wear history need a separately implemented/persisted host policy, not an invented cadence.

The optional variation's manifest includes the graphic blueprint, a separate `optional_outfits` entry, and print concepts. Every garment still has `asset_ref=None`; no texture, licensed print, fit-tested 3D cloth, or renderer receipt is present. This blueprint does not change Sofía's actual currently worn state. Any later change must pass through `SharedWardrobeState` with proper acknowledgement and text fallback.

## Preference provenance

An explicit `USER_REQUESTED` style input with ID `chat.2026-09-22.request.occasional_graphic_tee` records Sparks' request. Existing confirmed outfit-level likes for `engineer.signature` and `lounge.relaxed` remain intact; no separate `USER_LIKED` record is invented for the graphic shirt, any proposed print, or Sofía.

## Verification boundary

`test/test_avatar_lounge_graphic_tee.py` covers default/plain selection, explicit alternate selection, identical fit/coverage, preserved likes, request provenance, JSON-ready manifest, and strict typed selection. **These new tests have been committed but not executed in an exact repository checkout.** No change to INTERACT, MEM, the canonical avatar body, protected data, deployment or merge.
