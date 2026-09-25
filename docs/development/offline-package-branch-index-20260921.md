# Sofía package branch index | reconciled 2026-09-22

This index follows the ordered 16-package [root roadmap](../../ROADMAP.md). It is a navigation aid, not a release authority. Package branches are intentionally isolated; do not assume their APIs compose until a reviewed integration branch proves it.

## Ordered implementation branches

| Order | Package | Active source of candidate work | Status boundary |
| ---: | --- | --- | --- |
| 1 | CORE | PR #1 merged to main | Foundation merged; current integrated/live acceptance still open |
| 2 | INTERACT | PR #2 · feature/pkg-interact-shared-engine | Active implementation candidate; current head still under live-quality verification |
| 3 | MEM | PR #9 · feature/pkg-mem-original-retrieval-preflight | Read-only original retrieval preflight; broader memory integration open |
| 4 | SOCIAL | PR #4 documentation | Minimum Sparks principal/audience contract only; general multi-user deferred |
| 5 | NET | PR #11 · feature/pkg-net-discord-route-preflight | Discord route preflight only; no general internet/search |
| 6 | UI | PR #6 · feature/pkg-ui-workbench-offline | Offline workbench candidate; real client/Discord adapter/voice/rendering open |
| 7 | RUN | PR #3 · feature/pkg-run-always-on | Periodic opportunity gate candidate; no real 24/7 service yet |
| 8 | ACT | PR #15 · feature/pkg-act-outreach-preflight | Outreach eligibility preflight; no live sender |
| 9 | REL | PR #12 + alternate PR #13 | Overlapping absence/reunion candidates; reconcile one pipeline before integration |
| 10 | AVATAR | PR #7 · feature/pkg-avatar-offline-wardrobe-scene | Offline body/wardrobe/scene/tooling candidate; live renderer/rig acceptance open |
| 11 | DEV | PR #17 · feature/pkg-dev-change-proposal-preflight | Proposal preflight only; no trusted executor |
| 12 | BODY | PR #16 · feature/pkg-body-simulator-preflight | Simulation only; no real Gaia motion |
| 13 | EVOLVE | PR #19 · feature/pkg-evolve-amendment-preflight | Protected-change proposal only; no mutation executor |
| 14 | CLEAN | PR #14 · feature/pkg-clean-review-preflight | Read-only inventory/protection candidate; no destructive cleanup |
| Gate | SAFE | PR #18 · feature/pkg-safe-disclosure-preflight | Cross-cutting disclosure/privacy preflight; trusted enforcement open |
| Gate | VERIFY | PR #8 · feature/pkg-verify-evidence-gates | Active evidence-gate candidate; PR #10 is superseded/closed |

## Cross-package channel

**Discord D0–D4:** PR #5 (feature/pkg-discord-single-user-preflight) plus INTERACT, MEM, SOCIAL-minimum, NET, UI, SAFE, ACT, RUN, and VERIFY.

Initial scope is exactly one independently authenticated Sparks private-DM principal. No second user, group/server channel, public mode, or general web access is enabled by the preflight code.

## Historical foundation branches

Earlier package-foundation branches created small isolated package-domain prototypes. Keep them as reference/history unless their active package PR explicitly reuses them. Do not merge both an old foundation and a newer preflight implementation merely because they share a package name.

## Evidence rules

- Record exact branch + SHA + environment for every test result.
- Isolated Linux/preflight results are not Windows/full-repo/live acceptance.
- Results from different SHAs are not additive.
- Mock/fake transports do not prove authenticated Discord, Artemis, avatar, Gaia, or other real-system capability.
- A branch being ahead of main means only that commits exist, not that they are accepted.
- Preserve production state, backups, credentials, protected identity, and Constitution while reviewing branch work.

## Release sequence

CORE → INTERACT → MEM → SOCIAL minimum → Discord D0–D4 using NET/UI/SAFE → RUN verified 24/7 → separately authorized general web/search.

Other packages may develop in parallel when they do not silently advance or weaken those gates.
