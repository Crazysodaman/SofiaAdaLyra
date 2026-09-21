# Sofia package branch index and deferred-review register

**2026-09-21 · PR #4 documentation addendum · not merged, not a release plan override.** This is the coordination index for the original **13 packages** and the **3 proposed additions** (SOCIAL, RUN, AVATAR). Each code PR remains its own branch; this index neither merges nor approves them. The root `ROADMAP.md` on `main` still enumerates 13 and contains older state descriptions; reconcile actual PR status and dependency order before merging the roadmap. Do not count this index as implementation.

## Original packages: actual branch/code status

| Original package | Branch / PR | Offline result known at 2026-09-21 | What remains for package acceptance |
| --- | --- | --- | --- |
| CORE | Foundations merged in [#1](https://github.com/Crazysodaman/SofiaAdaLyra/pull/1) | Previous targeted Windows subset: 17 passed after narrow fixes | Coordinated full pytest at current revision and human live model/personality/latency review; never replace real failure investigation with old pass |
| INTERACT | [#2](https://github.com/Crazysodaman/SofiaAdaLyra/pull/2) | Previous 274 coordinated Windows tests passed on older revision; subsequent supervised CLI quality failed; new projection candidate not Windows-verified | Retest pinned branch and real live CLI, all-region policy, full suite, separate renderer/Discord later; **do not merge early** |
| MEM | [#9](https://github.com/Crazysodaman/SofiaAdaLyra/pull/9) | 23 focused tests on equivalent isolated source with stand-in model | Real conversation-store integration, user/auth scopes, immutable originals, durable retention/migration and restart; tests on actual branch |
| NET | [#11](https://github.com/Crazysodaman/SofiaAdaLyra/pull/11) | 29 focused equivalent isolated tests | Trusted transport/DNS/TLS/redirect enforcement and verified Discord route; local-to-Artemis real transport separately, no browsing yet |
| ACT | [#15](https://github.com/Crazysodaman/SofiaAdaLyra/pull/15) | 46 focused equivalent isolated tests | Reconcile existing outbox and RUN gate, trusted channel receipts, opt-in, Sparks's quiet hours, rate limits, stop/recovery and live delivery |
| DEV | [#17](https://github.com/Crazysodaman/SofiaAdaLyra/pull/17) | 41 focused equivalent isolated tests | Integrate existing code inspector, actual OpenCode host install, independent authority/diff/rollback, supervised executor tests |
| REL | [#12](https://github.com/Crazysodaman/SofiaAdaLyra/pull/12); concurrent alternative [#13](https://github.com/Crazysodaman/SofiaAdaLyra/pull/13) | #12: 28 focused equivalent isolated tests; #13 GitHub checkout tests not reported | **Reconcile to one relationship pipeline, do not merge duplicate stores/absence modules**; real sourced memory, restart and human non-clingy model review |
| UI | [#6](https://github.com/Crazysodaman/SofiaAdaLyra/pull/6) | 38 focused equivalent isolated tests | Real text client, MEM integration, source-linked books/binders/notes renderer, audience/revision controls and actual viewport |
| BODY | [#16](https://github.com/Crazysodaman/SofiaAdaLyra/pull/16) | 36 focused equivalent isolated tests | Real channel calibration, servo types, power, physical e-stop/watchdog, authenticated adapter and supervised Gaia trials |
| SAFE | [#18](https://github.com/Crazysodaman/SofiaAdaLyra/pull/18) | 35 focused equivalent isolated tests | Independently authenticated actor/grant enforcement, secrets, stop, privacy negatives, backups/recovery; boolean trust flags are not authentication |
| EVOLVE | [#19](https://github.com/Crazysodaman/SofiaAdaLyra/pull/19) | 24 focused equivalent isolated tests | Reconcile protected integrity workflow, independently hash actual state, explicit human amendment review and rollback; **no self-approval** |
| VERIFY | Active [#8](https://github.com/Crazysodaman/SofiaAdaLyra/pull/8); alternative [#10](https://github.com/Crazysodaman/SofiaAdaLyra/pull/10) closed without merge | #8: 27 focused equivalent isolated tests | Authenticate real test evidence and machine, pin actual checkout, resolve exceptions policy; no automatic merge/deploy |
| CLEAN | [#14](https://github.com/Crazysodaman/SofiaAdaLyra/pull/14) | 39 focused equivalent isolated tests | Actual inventory, Windows path/reparse checks, deletion evidence, protected backups, current-head regressions; no file removal authorized |

**Tests in this table are independent focused runs in Linux Python 3.13.5 / pytest 9.0.2 unless explicitly identified as previous Windows evidence.** GitHub branch checkouts, CI, full repository suite and dependent live tests have not been run for these new slices. For CLEAN, ACT, BODY, DEV, SAFE and EVOLVE, committed source and test file blob hashes were compared against the isolated tested copies; in BODY an unused test import was removed and 36 tests rerun before hashes matched. Do not add test counts as if one integrated test suite had passed. Every individual PR has its own detailed pending-review note.

## New packages and Discord channel work

| Workstream | Branch / PR | Status / next review |
| --- | --- | --- |
| SOCIAL (proposed) | Architecture in [#4](https://github.com/Crazysodaman/SofiaAdaLyra/pull/4) | **General multiuser is deferred.** Preserve minimum trusted identity/audience boundary for the one Sparks account only; no second-user implementation required now. |
| RUN (proposed) | [#3](https://github.com/Crazysodaman/SofiaAdaLyra/pull/3) | R1 periodic-opportunity code drafted, but Windows/live tests not run; no supervisor, actual 24/7 uptime, or unattended thought claimed. |
| AVATAR (proposed) | Contract in #4, offline code in [#7](https://github.com/Crazysodaman/SofiaAdaLyra/pull/7) | 58 focused equivalent isolated wardrobe/scene tests; actual adult base mesh, art, clothing assets, rig, renderer and real acknowledgments not produced. |
| Sparks-only Discord D0–D4 | [#5](https://github.com/Crazysodaman/SofiaAdaLyra/pull/5) plus NET #11 and INTERACT #2 | 26 isolated DM policy tests; only authenticated Sparks private DMs may later be enabled. No real bot/token/live DM sent; internet search not enabled. |

## Release / review gates

1. Keep current dependencies: CORE checkpoint → INTERACT text/headless and supervised live quality → MEM originals/privacy → authenticated Sparks-only Discord DM with Discord-scoped NET → **verified** supervised 24/7 RUN → separately authorized internet search. Offline code may be developed on other branches without silently advancing a release gate. AVATAR artwork and rich UI do not block Discord/RUN.
2. Each package review uses its actual pinned GitHub SHA and exact diff, fresh focused tests, applicable cross-package/Windows/full pytest, separately labeled real acceptance, negative security tests, data/migration/rollback and explicit merge decision. `not run` is not `passed`. Recorded evidence must come from a trusted test runner or observed system, not an LLM assertion.
3. **Open design decisions:** real avatar art/rig/runtime and licensed assets; Gaia calibration and independent physical cut-off; OpenCode host and executor security; authenticated Discord account IDs/tokens and trusted origin; actual user-approved local quiet-hour preference; private-reflection promotion/retention and real UI sharing; authorizing proper protected amendments. Do not guess these while offline coding.
4. Do not create new duplicates of existing emotion journals, conversation databases, authorization gateways, reflection loops or full user-relationship implementations. Explicitly resolve REL #12/#13 and VERIFY #8/#10 history before integrating. Never modify local `state/sofia.db` or backups, protected identity/Constitution, deploy or merge as a side effect of documentation.

**Summary:** all 13 original packages remain in scope and now have either existing merged foundations or independently reviewable draft code branches; that does **not** mean all 13 are complete, integrated, fully tested or merge-ready. SOCIAL remains future-only for general multiuser, and search remains last.
