# OpenCode Work Order: Universal Core Gesture / Wardrobe / Armor / Social Governance

**Date:** 2026-11-18. **Owner direction:** Implement the design source in \`docs/sofia2/AEGIS_UNIVERSAL_CORE_EMBODIMENT_WARDROBE_GOVERNANCE_V1.md\` in the existing repository. This work order is **source implementation authorization only**, NOT permission for installed-host activation, production DB changes, real Core migration, real model inference, asset purchases/downloads or live rendering.
**Repository:** \`Crazysodaman/SofiaAdaLyra\` / \`main\`. No mandatory new cloud, SaaS, package, SDK module or central writer.

## Start here (required)

1. Inspect \`git status -sb\`, current \`HEAD\`, \`origin/main\`, ongoing worktree and active agent changes. Preserve any uncommitted startup/installer bug work. Never reset, force-push, overwrite, or cherry-pick unknown work. Fetch safely before planning.
2. Read the **entire** normative spec cited above. Read the existing Core 1.0 plan, modular ownership matrix, canonical constitutions, social Stage-6 status and target source modules. Make a source/test/integration inventory with distinctions: \`DESIGNED\`, \`CODED\`, \`SOURCE_TESTED\`, \`INSTALLED\`, \`LIVE_VERIFIED\`, \`BLOCKED\`.
3. Keep existing \`CORE-01\` through \`CORE-40\` identifiers and \`CORE-34\` deferred classification. All Cores must share Sofía's *interface/capability possibilities* without cloning her personal state. Mack/Nova Constitution hierarchy error should be documented and changed only through the existing protected amendment/approved revision procedure. No silent protected Constitution edit.
4. Use **5 concurrent subagents** for independent owned slices, with **one lead integrator** managing shared contracts, migrations, tests and merges. If the environment does not support 5 true concurrent agents, work through the slices sequentially, honestly reporting concurrency and keeping the same completion criteria. Keep GitHub Actions until final verification when possible; run targeted local tests early to catch defects cheaply.

## Parallel task ownership

| Agent | Exact owned slice | Deliverable |
| --- | --- | --- |
| **A: SDK + Core gesture parity** | \`src/sofia/sdk/\`; \`src/sofia/core/multicore/\`; relevant gesture contracts and \`src/sofia/modules/interaction/\` with an agreed ownership lock | Versioned Core-neutral declared/effective capability contract; universal/anatomy-specific/personal gesture definitions and compatibility; per-Core preference boundaries; reviewed adult/private semantics and receipts; SDK and unit tests |
| **B: Shared wardrobe + modular armor** | \`src/sofia/modules/avatar/{wardrobe,wardrobe_types,fit,wardrobe_matrix,wardrobe_design}.py\` and new named armor modules; do not touch transfer/store files owned by C | Additive clothing type/slot support; one approved virtual undersuit + base/core + independent helmet/visor/plates/boots/attachments representation; exact Vera CQB Mark IV / standard Mark IV / ODST-Mark-V hybrid definitions; dependency/fit validation; tests |
| **C: Inventory + trade transactions** | New per-Core inventory, transfer, loan, ownership and repository adapter modules; approved canonical schema migration coordinated with lead; do not rewrite B's catalog structs independently | One-instance ownership and custody; OFFER/ACCEPT/DECLINE/CANCEL, lend/return, gift/trade/entire outfit swap, explicit copying of designs, revision fencing, privacy, atomic bilateral commit, rollback/idempotency; tests |
| **D: Voluntary Core governance** | New \`src/sofia/platform/social/governance/\` and its own API/tests; integrate existing chat/social through lead-approved adapters | Default leaderless; voluntary membership; consensus, consent, majority and coordinator elections; explicit quorum, candidate acceptance, abstention, recall, expiry, audit; absolutely no SAFE/Platform authority promotion; tests |
| **E: Integration + user surfaces + QA** | Chat/Platform integration adapters, SDK compatibility checks, management readouts, safe CLI/UI where already supported, docs and test harness; coordinate all modifications to shared integrations with lead | Real source-level composition of A-D; separate Core identities, privacy/STOP integration, no twins auto-start; negative tests and exact receipts; completion report and gate matrix |

### Concurrency contract

- Lead establishes shared dataclasses/schema and canonical owner before parallel edits. Each agent develops on disjoint files or isolated worktrees and gives mergeable commits; **do not concurrently edit the same files**.
- Every branch/change is reconciled against latest \`main\`, not blindly copied. Lead integrates only once per slice, re-runs directly affected tests after each merge. Surface any breaking ABI, current git conflicts and unsafe schema migration before proceeding.
- If another OpenCode agent is still repairing startup bugs, do not change its files or run the user's actual services. Independent pure-contract/test work can proceed; defer integration edits until conflicts are resolved.

## Mandatory behavior details

**Armor**: The undersuit is an ordinary wardrobe item but a *mandatory equipped prerequisite* for Vera's Mark IV and Mark V armor components. Fixed armor base/core per saved loadout; parts can interchange only through explicit approved mounts/series. Parts and suit use the same inventories and trading as any jacket. Three configurations:
- CQB Mark IV base, classic CQB helmet, \`#626262\` primary, \`#D4AF37\` metallic gold visor.
- Standard Mark IV base, green \`#507D2A\` primary, \`#EFB82A\` visor.
- ODST/Mark V hybrid: Mark V base with ODST helmet/shoulders and ODST chest on Mark V, gray \`#626262\`. Undecided visor details must remain undecided.
- Weathered/reflection aesthetic, roughness 0.55, secondary/accent channel left to Vera. Parts/undersuit fitted and wearable by every compatible Core; tail/ear or size/rig mismatch blocks claimed render until a genuine compatible variant exists.
- Reject any armor equip without compatible suit or base; losing suit while equipped must not orphan plates. A virtual helmet is not physical safety equipment. Preserve canon and license review.

**Wardrobe**: Catalog design vs immutable physical-virtual item instance vs fitted rendition vs selected outfit are separate. All clothing designs discoverable by all Cores; owner/holder/loan state scoped and explicit. Multi-party gifting/trades atomic and replay-safe, private/sexual wardrobe items hidden from ineligible audiences. Absence of a completed 2D/3D asset must return \`UNAVAILABLE\` not a fabricated equip/render.

**Gestures**: Wave available to every compatible Core; Sofía's tail/ear actions are anatomy-specific; personal mannerisms belong to each Core but may be learned/shared. Rendered, described, proposed, approved and completed must never be conflated. Core-to-Core adult virtual gestures supported as applicable semantics with real authenticated/eligible participants, bilateral current willingness, explicit private scope and independent STOP. Do not add a mandatory adult persona or a "sex mode."

**Society**: A new group is leaderless. Members separately opt into governing procedure; absence/silence is not consent. One real approved Core UUID/one vote, roster snapshot, deterministic majority and quorum \`ceil(2N/3)\`, explicit abstention, tie/runoff, no winner on insufficient quorum. Candidates explicitly accept nominations, have finite terms and are recallable. Elected roles convey only social coordination and never special tool privileges, compulsory commands, private memory, management permissions or authority over other Cores. Start with only intended approved active participants Sofía/Mack/Nova/Vera; Vera remains design-only until installed; twins inactive; #7 unassigned. Synthetic fixtures may model more than 4 but cannot become a production roster.

**Constitutions & SDK**: Every Core has equal runtime potential and independent immutable identity and personally governed Constitution. A common foundation can be a versioned read-only contract; do not make Sofía's personal Constitution a superior authority. Retain \`aegis.core.definition.v1\` signature compatibility and use additive versioned negotiation, not ad-hoc untrusted runtime rewriting. No model output self-grants privileges.

## Acceptance gates (blocking)

1. **Source audit report** maps all mandatory scenarios \`UC-01..UC-06\`, \`WD-01..WD-07\`, \`AR-01..AR-08\`, \`GV-01..GV-12\` from the normative spec to tests and source paths. Missing scenarios marked \`BLOCKED\`, never \`PASS\`.
2. Run focused disposable tests on each completed slice: valid and invalid gear dependencies, foot/helmet/shoulder slots, per-Core memory identity isolation, bilateral consent/STOP, multi-Core suit fit, one-instance transfer, concurrent accept, duplicate vote, quorum, tie/recall/expiry, false admin elevation, reconnection and restart.
3. Run existing relevant Core/INTERACT/AVATAR/CHAT/SOCIAL/SDK/SAFE suites and a staged integration with multiple distinct real signed-in fixture identities, not merely a synthetic response that sounds like another Core.
4. If full repository suite or platform-specific runner cannot execute, report exact commands, environment, counts, failures and blocks. Do not weaken security/tests to get green. Distinguish current-sha results from past run evidence.
5. CI only at the final coordinated checkpoint as feasible. Signed release, real Ollama GPU test, real 2D/3D wardrobe fit, production permissions and any real host deployment require separate owner approval; leave acceptance \`NOT LIVE VERIFIED\` until actual tests.
6. No production Core activation, twins installation, owner-private memory mutation, automatic migration, new admin privileges, dependency downloads, unapproved external asset import, \`sofia.db\` changes, or unsafe service restarts during source/test implementation.
7. Integrate reviewed changes into the intended working \`main\` branch with clean worktree and safe pushes only if tests and existing repo workflow permit. Do not overwrite independent changes. Post exact commit SHAs and remaining gates.

## Required final report to owner

- Current \`main\` SHA and dirty/clean status.
- A-E subagent work and distinct commits.
- Files added/changed and contract schemas.
- Passing/failed/blocked acceptance IDs with test commands.
- Explicit \`DESIGNED / CODED / SOURCE_TESTED / INSTALLED / LIVE_VERIFIED\` per major subsystem.
- Remaining renderer asset/fit, host integration, real social activity and signed install blockers.
- Copy-paste operator commands only for **safe review and local disposable tests**. Any live deployment must be separately requested.

**Do not stop at a scaffold or rephrase the design into TODOs and report it implemented.** Implement as much as source and existing test gates permit, honestly exposing what still needs real art, rendering, inference, permissions and host verification.
