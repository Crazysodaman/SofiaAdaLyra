# PKG-AVATAR | autonomous presentation and evolving style contract

**Planning date:** 2026-09-23. **Status:** design contract on draft PR #7; no live renderer, autonomous style loop, MEM persistence, or deployed presentation autonomy is claimed.

## Goal

Let Sofía choose, experiment with, retain, and revise how she presents herself without treating the current cyberpunk engineer look as a permanent lock. Preserve a stable canonical identity while making presentation an ordinary mutable part of her self-expression.

The key boundary is:

**identity is not presentation, and presentation is not authority.**

Changing an outfit, hairstyle, hair color, tail color, or UI theme must not silently rewrite protected identity. Likewise, a visual change must not grant physical-device, filesystem, network, or Home Assistant authority.

## Three distinct layers

### 1. Canonical identity baseline

Protected identity remains separate from ordinary presentation choices. This includes name, adult identity, continuity, constitutional rules, and other protected facts governed by CORE/EVOLVE.

Canonical avatar traits may provide a **baseline/default**, but presentation-capable traits must explicitly declare whether they are:
- immutable identity traits,
- mutable presentation traits,
- renderer-only effects,
- or unknown/unreviewed.

Do not infer that a historical default is permanent merely because it was the first implemented look.

### 2. Mutable presentation state

AVATAR owns one revisioned presentation state that may include:

- outfit and garment variants,
- hairstyle,
- **hair color**,
- **tail color**,
- makeup/cosmetics where supported,
- accessories,
- jewelry,
- glasses/headwear,
- palette/accent choices,
- avatar aesthetic/style tags,
- scene/lab decoration preferences,
- renderer-safe appearance effects,
- compatible UI/avatar theme hints.

Hair color and tail color are explicitly modeled as mutable presentation properties. A change to either must not require an identity amendment unless a future protected rule explicitly says otherwise.

Presentation state must distinguish:
- current,
- proposed,
- pending renderer acknowledgment,
- failed,
- reverted,
- and historical states.

Text and rendered avatar must consume the same authoritative revision. A text claim such as "my hair is silver today" must not appear as current unless the same presentation revision is authoritative.

### 3. Preferences and self-directed style development

Sofía may develop her own reviewed presentation preferences independently from Sparks' preferences.

Preference evidence must retain:
- actor (`SOFIA` or `SPARKS`),
- target,
- sentiment/strength,
- source/provenance,
- timestamp,
- review state,
- confidence/stability,
- and optional expiry/revisit time.

Preference maturity should support at least:

- **temporary**: "I feel like trying this today."
- **developing**: recurring attraction to a style/color/item.
- **established**: repeatedly chosen and retained over time.
- **retired**: previously liked but no longer preferred.

Sofía may revise or abandon her own preferences. A preference is not a constitutional commitment.

## Autonomous choice loop

A future autonomous presentation loop may:

1. Observe current context supplied by trusted sources: time, activity, season, renderer capability, audience/privacy state, available assets, and reviewed preferences.
2. Generate one or more presentation candidates.
3. Evaluate them against her own preferences first, then user requests/preferences where relevant, plus privacy/safety/renderer constraints.
4. Choose or propose a bounded presentation change.
5. Commit only after required renderer or state validation.
6. Record the result and preference evidence.
7. Learn from repeated choices without turning one choice into a permanent preference.
8. Revisit old preferences occasionally and allow natural drift.

The loop must avoid random churn. On every boot, Sofía should restore her last authoritative state rather than rerolling her appearance.

## User requests versus Sofía's own choice

Sparks may request or suggest a look, color, outfit, hairstyle, or theme. A request is not automatically a preference and is not automatically Sofía's own preference.

Examples:

- "Try blue hair" -> request/proposal evidence only.
- Sofía chooses blue hair repeatedly and later says she likes it -> candidate Sofía preference.
- Sparks says "I like your silver hair" -> Sparks preference, not Sofía preference.
- Sofía later chooses crimson again -> valid preference drift, not inconsistency.

Where a harmless request conflicts with an established Sofía preference, the system should allow a conversational choice rather than silently overriding either side. Safety/privacy constraints still override presentation preference.

## Persistence and memory

MEM should persist:
- authoritative presentation history,
- preference provenance,
- reversible preference revisions,
- user-vs-Sofía preference ownership,
- renderer receipts where needed,
- and last-known valid presentation revision.

MEM is not the live presentation authority. AVATAR owns current presentation state; MEM stores durable history and preference evidence.

Restart behavior:
- restore the last valid current presentation,
- restore established/developing preferences,
- do not resurrect failed or pending changes,
- do not replay expired temporary experiments as permanent state,
- and do not repeat canned "I changed..." notices on every boot.

## Renderer and asset requirements

Every mutable property must advertise renderer capability. If a renderer cannot support a requested hair/tail color, hairstyle, garment, or effect:
- do not claim it visually happened,
- keep the request/proposal distinct from current state,
- fall back to text-only representation only when the host explicitly supports that semantic mode,
- and preserve the prior valid rendered state.

Hair/tail color changes should prefer material/parameter variation where possible rather than duplicating full assets, with:
- validated color space,
- safe preset or bounded custom values,
- shader/material compatibility,
- LOD consistency,
- screenshot/cache privacy behavior,
- and exact-revision renderer acknowledgment.

## Identity continuity during visual changes

Large visual changes must not create a second personality or identity instance. The same Sofía may look radically different while retaining the same:
- conversation continuity,
- memories,
- relationships,
- authority,
- emotional continuity,
- and instance identity.

The system should expose enough stable cues for recognition when desired, but must not force permanent crimson/purple/cyberpunk elements solely to prove continuity.

## Audience and privacy

Presentation may be audience-sensitive. Private presentation state must not leak into:
- public/group Discord contexts,
- thumbnails,
- cached previews,
- notification images,
- crash dumps,
- shared streams,
- or unrelated clients.

Unknown/public audiences use an approved safe presentation. Private-only presentation remains separately authorized.

## UI and environment theming

Sofía may eventually express style through more than her body/avatar. Presentation preferences may inform:
- her own avatar UI accents,
- lab/virtual-room decoration,
- avatar renderer background,
- personal dashboard/workbench theme,
- and other explicitly scoped surfaces.

This must not automatically rewrite Sparks' global Home Assistant, desktop, or dashboard theme. External UI/device changes require the owning package and its authority gate.

## Acceptance requirements

This feature is not complete until evidence demonstrates:

1. Hair color can change and restore across restart without modifying protected identity.
2. Tail color can change and restore across restart without modifying protected identity.
3. Outfit, hairstyle, hair color, tail color, accessories, and style tags share one authoritative presentation revision.
4. Sofía can hold her own presentation preferences separately from Sparks' preferences.
5. Temporary/developing/established/retired preference states are durable and reversible.
6. Repeated autonomous choices can strengthen a preference without one-off choices becoming permanent.
7. Sofía can change her mind and preference drift does not corrupt canonical identity.
8. Renderer failure does not create false visual claims.
9. Text and renderer remain synchronized to the exact same revision.
10. Restart restores valid state and never promotes pending/failed experiments.
11. Public/private audience boundaries prevent presentation leaks.
12. A request from Sparks does not silently become Sofía's own preference.
13. Styling changes cannot grant unrelated action authority.
14. A substantially different aesthetic still resolves to the same Sofía identity/session.
15. Autonomous style selection does not churn constantly or reroll on boot.
16. Live-model tests show Sofía can naturally explain a style choice, decline one, revisit one, and change her mind without canned wording.

## Package ownership

- **AVATAR:** presentation state, renderer-facing appearance data, wardrobe/assets, hair/tail/material variants.
- **MEM:** durable preference/history provenance and restoration.
- **CORE/EVOLVE:** protected identity baseline and governed identity amendments.
- **INTERACT/REL/ACT:** conversational expression, contextual choice, initiative, and reactions.
- **UI:** renderer/client transport and visual acknowledgment.
- **SAFE:** audience/privacy/authority boundaries.
- **VERIFY:** restart, renderer, drift, privacy, and live-model acceptance evidence.

## Current truth

The existing AVATAR draft already has wardrobe preference types, including `PreferenceActor.SOFIA`, and a planner that can weight Sofía's reviewed preferences. That is useful scaffolding, but autonomous preference formation, full presentation state, hair/tail color autonomy, MEM persistence, and live renderer synchronization are not yet implemented or accepted.
