# Offline-first package coding and test gates

**2026-09-21 · proposed coordination document · branch-only, not a replacement for the root roadmap.** The root `ROADMAP.md` on main currently lists 13 packages. Draft PR #4 proposes SOCIAL, RUN and AVATAR for 16; draft PR #3 separately proposes RUN and 14. Reconcile these branches before changing the authoritative roster. No planning line means a feature is coded, tested, accepted, enabled or deployed.

## Working agreement

- Prepare contracts, isolated code, fixtures, negative tests, migration plans and rollback procedures early. A feature can be **offline-coded**, **offline-tested**, **integrated**, **live-tested**, and **released** at different times; record all five independently with exact source revision and environment. `not run` is never displayed as `passed`.
- Keep the agreed release gates: CORE verified → INTERACT text/headless → MEM → authenticated Sparks-only Discord DM D0–D4 → supervised 24/7 RUN acceptance → separately authorized internet search. Reconcile a minimal actor/audience trust contract before DM integration, but defer general multi-user behavior, other people's relationships and shared channels.
- Early coding cannot bypass prerequisites. Preserve the Constitution, canonical identity, production databases and backups. No host service installation, bot token, live Discord delivery, network grant, real UI capture, intimate interaction, autonomous external action or robot motion is enabled merely by merging offline code.
- Each package gets an isolated branch/PR, owner, dependency contract, offline test command, measured result, live gate and rollback. Do not duplicate INTERACT PR #2 or RUN PR #3; do not merge them simply because this branch is ready.

## Concrete build/test ledger

| Package | Prepare offline | Live or dependent acceptance |
| --- | --- | --- |
| CORE | Existing context, grounding and performance regression suite | Fresh coordinated full pytest and human-reviewed personality/latency gate; PR #1 merged but full suite deferred |
| INTERACT | Reuse draft PR #2 text parser, region policy, headless lab and conversation tests | Windows focused/coordinated checks, real CLI personality and full suite; do not rewrite its existing interaction engine |
| MEM | Per-user original-message store, provenance, corrections, retention and retrieval fixtures | Restart/recovery and reviewed promotion on disposable database before production migration |
| NET | Capability/grant limits and **Discord-required-only** outbound allowlist fixtures | Real authenticated network route and Discord reachability; general browsing deferred |
| ACT | Bounded goals, unsent outbox, novelty and optional local thought fixtures | Authorized delivery, measured resource fairness, deduplication and stop behavior |
| DEV | Read-only diagnosis, patch proposals, test/rollback fixtures | Separately authorized OpenCode/file/Git/restart execution and independently checked rollback |
| REL | Evidence-linked absence, contextual emotion and non-clingy reunion fixtures | Supervised multi-session quality and correction review, Sparks-only first |
| UI | Text-first workbench, access-aware page/binder/book scene data, accessibility fixtures | Actual clients, rendering, avatar click/animation acknowledgments, no click-through |
| BODY | Gaia simulator, calibration schema and watchdog fault fixtures | Supervised real hardware and independent physical emergency stop |
| SAFE | Default-deny auth, no-leak, stop/revoke, retention and backup negative fixtures | Real secrets/deployment/recovery security verification |
| EVOLVE | Versioned proposal, review and integrity-denial fixtures | Explicit protected-state amendment authorization; never silent changes |
| VERIFY | Offline vs integration vs live evidence ledger, deterministic fixtures and baselines | Pinned full suite, real outages/latency/personality, documented failures |
| CLEAN | Read-only inventory, diffs, reversible migration and behavior-preservation fixtures | Focused/full regression checks before any cleanup/delete |
| SOCIAL (proposed) | Minimum verified-actor DM boundary now; general multi-user interfaces parked | No second-user release until explicit scope change and cross-user privacy tests |
| RUN (proposed) | Reuse draft PR #3 periodic gate and unit tests; prepare supervisor/restart fixtures | Real supervised 24/7 soak, outage/retry, observed missed windows and stop |
| AVATAR (proposed) | Canonical mesh/wardrobe/object metadata, rig compatibility and headless interaction fixtures | Actual reviewed art, rendering, accessible controls, privacy and gesture fidelity |

## First executable early slice: Sparks-only Discord DM gate

`src/sofia/discord/access.py` provides a disabled-by-default, side-effect-free policy function. Its only successful input is an authenticated-source private DM from the exact configured Discord user ID to the exact bot ID. Other people, servers, group DMs, webhooks, bot senders, malformed IDs, wrong recipients and unverified sources are rejected. IDs are placeholder fixture values only, **not actual user credentials**.

Run from an installed editable package or with `PYTHONPATH=src`:

```sh
python -m pytest -q test/test_discord_single_user_gate.py
```

**Local isolated verification on Python 3.13.5, pytest 9.0.2:** 26 passed in 0.07 s, using staged equivalent files and `PYTHONPATH=src`. This is not a Windows full-suite result and not a claim that GitHub CI ran. The GitHub branch files require their own pinned-revision verification before merge. The adapter must independently verify Discord gateway/API origin and supply trusted metadata; a `authenticated_source=True` boolean in an untrusted JSON payload is **not authentication**. The actual bot token, gateway session, DM send/receive, message idempotence, rate limiting and opt-in outreach are unimplemented in this slice. Internet search is absent.
