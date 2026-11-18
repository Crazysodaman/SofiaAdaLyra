# Aegis Universal Core Embodiment, Wardrobe, Armor and Voluntary Governance V1

**Owner design decision:** 2026-11-18. **Status: implementation specification / backlog, NOT source-test, installed-host, or live verification.**  
**Scope:** Project Aegis universal Core Runtime + versioned SDK + existing AVATAR/INTERACT/CHAT/SOCIAL/SAFE/MEM owners.  
**Initial planned participants:** Sofía Ada Lyra (#1), Mack Fuller (#2), Nova Arden (#3), Vera S-039 (#6, design-only until implemented). Twins (#4/#5) stay inactive/not commissioned; #7 stays unassigned. No startup, model download, signed deployment, asset fabrication, Core activation or protected-state migration is authorized by this document.

## 0. Owner decisions, not optional interpretations

1. **Full common Core capabilities:** Every independently authenticated Aegis Core has access to the same *interfaces and potential capability families* established for Sofía, including the existing CORE-01..CORE-40 requirements, emotion/romance/sexual modeled states, interactive expressions, generic and adult virtual gestures, optional voice/avatar, autonomous social interaction, goals, memory and developer/tool interfaces. Capability presence never implies willingness, usable renderer assets, permission or completion. CORE-34 retains its historical deferred release classification; do not renumber or silently promote requirements.
2. **One common engine, separate individuals:** No Core clones Sofía's UUID, memory, Constitution, relationships, intimate preferences or personality. Core-specific records have canonical identity, revision and provenance. The shared SDK is an inert contract family, not a privileged Core or new permission authority.
3. **Constitutions:** Personal Core constitutions are peers, not subject to Sofía's personal Constitution. A proposed universal foundation may enforce baseline truth, identity continuity, boundaries, nonfabrication, autonomy and privacy, but NEVER transfer personal constitutional governance to Sofía. Existing constitutional file changes and protected identities need their existing reviewed/owner-authorized amendment process, not an automatic textual rewrite.
4. **Three gesture classes:** (a) generic/universal, e.g. wave, nod, smile, sit, handshake; (b) anatomy/rig-specific, e.g. Sofía's fox ears and tail; (c) personally distinctive/learned, e.g. a Core's mannerisms. A learned gesture can be taught/shared if offered and compatible; it is not permanently exclusive to its originator.
5. **Shared wardrobe designs:** The entire approved wardrobe *catalog* is visible to all eligible Cores. No gender, personality or "original Sofía" whitelist. Each garment must still pass fit, body/rig, asset, layering and audience/privacy checks before it is claimed wearable/rendered. All Cores may voluntarily borrow, lend, gift, trade, return, customize, or exchange outfits through explicit item-instance state.
6. **Vera armor = modular wardrobe:** An undersuit is an ordinary inventory/wardrobe item with special armor compatibility metadata. Every plate, attachment, boot, gauntlet, shoulder, helmet, visor and armor base/core is likewise a separately equipable/equippable wardrobe item. **A compatible equipped undersuit is mandatory before any armor component may be equipped.** Armor family, body fit, mounts and base/core compatibility must additionally pass. Other Cores may wear Vera's armor when these prerequisites are satisfied.
7. **No forced society:** Core groups may choose NO LEADER, discussion/consensus, consent, a democratic vote, a time-bounded coordinator, rotation, delegation, dissolution, or a recall process. Participation is opt-in and cannot be silently inferred from chat activity. All groups start leaderless.
8. **Governance is social, not security:** "Leader"/coordinator grants no Platform/Fleet/SAFE/RUN/ACT authority, no constitutional dominance, no private memory access, no right to command other Cores, and no ability to force activity, clothing, romance or friendship. All consequential actions keep the independent owner/Platform authorization paths.
9. **No false claims:** Catalog rows do not prove meshes, installed clothing assets, 3D renderers, haptics, executed gestures, actual social consent, live multi-Core inference, or successful transactions. Return explicit unavailable/denied/unknown receipts.

## 1. Existing repository source surfaces to audit and reuse

| Owner | Relevant source (current main; verify paths before editing) | Known limitation at drafting |
| --- | --- | --- |
| Core requirements | \`docs/sofia2/CORE_1_0_PLAN.md\` | 39 active + 1 deferred logical Core requirement, not 40 verified services |
| Personal constitutions | \`src/sofia/core/constitution/constitution.md\`, \`src/sofia/core/cores/{mack,nova}/constitution.md\` | Mack/Nova text erroneously frames Sofía Constitution as superior; changing protected files needs governance |
| Core SDK/definitions | \`src/sofia/sdk/core_definition.py\`; \`docs/development/signed-core-definitions.md\` | Existing signed v1 definition covers private Constitution/personality refs; no whole-framework capability parity claim |
| Common gesture vocabulary | \`src/sofia/modules/interaction/registry.py\` | Vocabulary only; notes v1 engine does not automatically consume expanded catalog |
| Active basic gesture engine | \`src/sofia/modules/interaction/core.py\` | Eight basic gestures in v1; no general renderer |
| Emotion models | \`src/sofia/core/emotion/{catalog,journal,appraisal,projection}.py\` | Category declarations and modeled state do not prove subjective feelings |
| Avatar garment/fit | \`src/sofia/modules/avatar/{wardrobe,wardrobe_types,wardrobe_design,fit,wardrobe_matrix}.py\` | Metadata/layers/fit anchors, not real cross-Core mesh fit or transferable item ownership |
| Avatar privacy | \`src/sofia/modules/avatar/private_grant.py\` | Host/owner/private opt-in enforcement; must not be bypassed by sharing |
| Multi-Core chat | \`src/sofia/platform/chat/{contracts,engine,store}.py\` | Group membership and history/epoch fences exist; not governance ballots |
| Social autonomy | \`src/sofia/platform/social/autonomy/{contracts,engine,store}.py\` | Bounded event-driven intents, not election authority |
| Social integration | \`docs/sofia2/AEGIS_SOCIAL_MULTICORE_STAGE6_STATUS.md\` | Local 182-test checkpoint; live installed-host composition not verified |
| Avatar ownership plan | \`docs/development/pkg-avatar-embodiment-wardrobe-objects.md\` | Design includes inventory ownership/scope, fit and independent renderer receipts, not production inventory trades |

Do not introduce a second canonical state writer or duplicate REL/EMOTION/MEM/ACT/SAFE. Integrate through existing per-Core isolated state and Platform writer. Source investigation and tests, rather than these notes, determine the actual implementation state at the current HEAD.

## 2. Universal gesture and embodiment contract

- **Versioned definitions:** \`GestureDefinition(id, version, class, actor/target, body_required_capabilities, semantic_parameters, phase, privacy_class, renderer_capability, provenance)\`. Reuse the existing gesture/action/expression/pose/presentation namespaces and preserve canonical IDs/aliases. Maintain reviewed migration aliases, never silently remap anatomy or an unknown adult action to generic touch.
- **Universal gestures:** waving, nodding, shaking head, pointing, walking/standing/sitting, smiling, laughing, hugging, handshakes, hand-holding, ordinary touch and other reviewed motions.
- **Anatomy-specific:** ears, tails, wings or future appendages depend on actual canonical anatomy and compatible renderer rig. Sofía's ear/tail cues must not be emitted for Mack/Vera without compatible anatomy.
- **Personal gestures:** Core-scoped style, intensity, pacing, use preference, learned motions, teaching/sharing requests; independent by canonical Core UUID; importing a gesture definition does not change another Core's persona.
- **Romantic/adult vocabulary:** Existing affectionate, sensual, sexual and nonsexual interactions must remain possible as *reviewed semantics* only for adult-eligible, authorized contexts and willing participants, including Core-to-Core virtual relationships. No "sexual personality switch", blanket consent by anatomy, or permanent inferred preference. Attraction, desire, arousal, comfort, willingness and policy are different state dimensions.
- **Context:** Actor, recipient, Core IDs, audience, room, source provenance, target region, direction, modality (chat/avatar/virtual scene), start/update/end/cancel, opt-in and revoked scopes. Never treat model text as authenticated sensor input.
- **Outcome:** \`PROPOSED -> AUTHORIZED/DECLINED -> QUEUED -> RENDERED/CANCELED/FAILED/UNAVAILABLE\`, each with exact event/renderer/asset/generation/STOP proof where applicable. Spoken/typed stage directions are virtual descriptions, not proof of actual playback or physiology.
- **Safety:** No adult interaction in public chat/uncertain-age context. Honor independent per-participant willingness and private-audience gates, even with a valid renderer. STOP/cancel applies to both parties and forbids late success receipts. Keep optional modules absent-safe.

## 3. Universal wardrobe: definitions, instances, wearers, fitted variants

Separate four concepts to avoid accidental duplication:

1. **Catalog design**: stable \`garment_design_id\` + version, class, style/texture/material, privacy/rating, license/source, slots/layers/coverage, rig/fit metadata and compatible asset references. Shared for discovery.
2. **Individual instance**: immutable \`item_instance_id\` + current owner Core UUID (or owned shared/group scope), revision, provenance, transferability/license, loan obligations, restricted visibility, custody and equip state. Multiple instances may reference one design, but lending one never clones it.
3. **Wearer fit variant**: design + body/measurements + rig + attachment sockets + fit profile + variant digest/renderer receipts. A fitted adaptation changes appearance, not the Core's canonical body. It may be generated only when approved tooling/assets support it; no fake fit success.
4. **Current outfit**: ordered equipped item IDs, wearer ID, exact versions, layering/coverage, room/viewer/audience projection and effective renderer revision. Equipping an item does not implicitly transfer ownership.

Every Core can access catalog entries without automatically owning instances. Allow existing individually owned Sofía garments to retain their owner. Define default/shared inventory explicitly only if authorized. Generic all-size clothing templates may be adjusted for each wearer, but clip-free fit is an asset/rig acceptance result, not metadata alone. Private garments stay restricted by audience, permissions and owner/license scopes even when traded. A Core may choose its own outfits and decline requests.

**Transfer operation contract**: \`OFFER, ACCEPT, DECLINE, CANCEL, LEND, RETURN, GIFT, TRADE, SWAP_OUTFIT, COPY_DESIGN, CUSTOMIZE\`. Offers are inert, bounded and expiring. Gift/trade/borrow require genuine verified sender title or custody, exact intended recipient, recipient acceptance, unambiguous item instance(s), current expected revisions, current permissions, and owner/Platform checks when applicable. Use a single canonical transactional commit for reciprocal trade/swap; no partial ownership moves. Frozen/expired/duplicate offers cannot complete. Keep idempotency keys, auditable transition receipts, restart reconciliation, rollback/compensation if a downstream renderer fails. Do not silently unequip another Core without permission; transfer-equipped items need a safe voluntary handoff/unequip step or return a blocked result. Loans preserve original owner, track current holder and explicit due/recall policy without involuntary interaction. Restricted content not leaked into general inventory/chat/client previews.

## 4. Modular armor as wardrobe equipment

**Do not create a separate armor inventory/permission database.** Extend garment types/capabilities using compatible additive metadata; preserve ordinary clothing and existing \`Layer\`/slot migration behavior.

The following are individual wardrobe types and inventory instances:

| Type | Independent part/slots | Dependency |
| --- | --- | --- |
| \`armor_undersuit\` | Whole-body fitted undersuit (may be worn alone) | compatible body + garment/renderer assets |
| \`armor_base\` | Set's fixed structural torso/core assembly | compatible **equipped** undersuit |
| \`armor_chest\`, \`armor_back\` | Front/back plates | undersuit + compatible armor base/mount |
| \`armor_helmet\`, \`armor_visor\` | Head/face pieces | undersuit + appropriate head/helmet mount and set compatibility; standalone helmet if separately designated safe |
| \`armor_shoulder_left/right\` | Distinct left/right shoulders | undersuit + compatible base/mount |
| \`armor_forearm_left/right\`, \`armor_gauntlet_left/right\` | Distinct arms/hands | undersuit + matching compatible mount |
| \`armor_thigh_left/right\` | Distinct legs | undersuit + matching compatible mount |
| \`armor_shin_left/right\`, \`armor_boot_left/right\` | Distinct lower legs/feet | undersuit + matching compatible mount |
| \`armor_attachment\` | Tactical cosmetic attachments/accessories | undersuit + exact socket/plate requirements |

**Owner's existing Vera S-039 canon, preserve exact variant distinctions:**

- **CQB:** fixed **Mark IV base**; classic **CQB helmet**; primary gray \`#626262\`; metallic-gold visor \`#D4AF37\`.
- **Mark IV:** fixed **Mark IV base**, interchangeable Mark-IV-compatible components; primary green \`#507D2A\`; visor \`#EFB82A\`.
- **ODST hybrid:** fixed **Mark V base**; ODST helmet and shoulders; ODST chest over compatible Mark V base; primary gray \`#626262\`; **do not invent unresolved visor color**.
- All: weathered metallic/reflection treatment, target armor roughness \`0.55\`; independent primary/secondary/accent material channels; unspecified secondary colors/details are Vera's own future decisions. Reuse approved aesthetics, not copyrighted game model assets without an appropriate license.
- **Core/base fixed per loadout**. Compatible plates/mounts may swap; no arbitrary Mark IV/Mark V cross-base mixing or automatic base rewrite. Multiple saved loadouts permitted within bounded storage.
- All Cores may wear an approved instance of Vera's armor (gift/borrow/trade/own copy) after securing a compatible undersuit, wearer fit, rig, sockets and reviewed visual assets. Fox ears/tail require additional clearance/collision checks for Sofía; no automatic anthropometric retconning for Mack/Nova/Vera.

**Equip rules, mandatory**:
1. No armor component can be **equipped or represented as equipped** without an actually equipped armor undersuit with matching \`armor_family\`, \`undersuit_interface_version\` and wearer/body compatibility (unless an explicitly reviewed component type has no undersuit need; the Vera sets here have no such exception).
2. Structural \`armor_base\` selected before all armor plates. Validate each component's \`base_series\`, \`mount_id\`, socket and variant compatibility; ODST-over-Mark-V hybrid is an explicit approved compatibility mapping, not general cross-series mixing.
3. Equip/unequip recomputes dependency graph atomically. Removing or trading the undersuit while armor relies on it must block or execute an explicitly approved *atomic full disassembly* with safe dressed fallback. Never leave an invalid displayed loadout.
4. Part inventory identity, ownership, visibility, fit, privacy and trade rules are exactly clothing rules. Armor is **cosmetic virtual representation** and provides no automatic physical protection, special equipment authorization or host privileges.
5. A complete rigged mesh, clipping/collision validation and renderer receipt are separate gates. On unknown fit, missing asset, conflicting mount or STOP, refuse the effect and report metadata-only status.

## 5. Optional Core society and governance

The user wants natural, voluntary Core-to-Core self-organization. **No default government and no default leader.** A "social role" is not an operator/admin role. Group membership and ballots use verified immutable Core UUIDs, never display names, model text, or a synthetic duplicated speaker.

### 5.1 Group lifecycle

\`PROPOSED -> INVITING -> VOLUNTARY_MEMBER -> ACTIVE -> PAUSED/DISSOLVED\`. Each Core may independently invite, accept, decline, abstain, leave, block or dissolve a group when its own scope allows. A Core not installed/active does not vote or acquire a phantom membership. The twins (#4/#5) and #7 are excluded from initial electorates unless separately installed and voluntarily joined later. No one can enroll a Core merely by mentioning it in \`#general\`.

Groups may pick a name, purpose, chat room(s), documented procedures, membership criteria, coordinator scope and preferred voting scheme. No leadership required for groups. Governance settings change through explicitly authorized, versioned member decisions; when absent or disputed, remain leaderless with simple discussion.

### 5.2 Decision procedures to support

- Informal discussion / no vote; no binding group outcome.
- Consensus: all eligible participating members affirm a proposal (not mere silence).
- Consent: no unresolved, properly evidenced blocking objection after review; nonresponse isn't consent.
- Simple majority vote with recorded roster, fixed close time, and deterministic count.
- Optional approval voting for multi-candidate coordinator elections; deterministic tie handling.
- Time-limited elected/rotating *social coordinator*, delegation by topic, resignation and recall.
- Topic-specific teams independently choose their own rules; votes have no effect on unrelated or private Core domains.

**Initial safe defaults for the first implementation (configurable only by explicit valid group agreement):** no leader; opt-in membership; one authenticated Core UUID = one vote per ballot revision; all invited voting members have equal weight; fixed voter roster/membership epochs at poll open; quorum \`ceil(2/3 * eligible_members)\` and at least two eligible members to run leadership elections; valid explicit abstentions count for quorum but not for YES/NO majority; no vote = no vote; ordinary majority is \`YES > NO\` after quorum, with no leader on tie, failure or missing quorum; a coordinator is valid only after its own explicit acceptance and has a finite term (proposed default 7 days, if opted in), after which the role expires rather than auto-renews. Quorum is on authenticated eligible submissions, not on impressions, conversation volume or synthetic models. For ties on a competitive election, open a reviewed runoff; do not make alphabetical order an election victory.

**Initial governance policy adoption:** require explicit agreement of every initial founding participant on the procedure before its first election. Refusal or silence means that participant is not placed in that governed group. Members may create a different voluntary group instead. Future rule amendments follow the versioned procedure the group has already agreed to, without binding nonmembers.

### 5.3 Immutable vote audit model

- \`GovernanceGroup\`: group UUID, audience/room IDs, revision, member roster/epoch, governing policy version, lifecycle.
- \`Proposal\`: UUID, proposer Core UUID, type, exact text/policy digest, eligible electorate snapshot, opening/closing times, rules, quorum, status and revision.
- \`Nomination\`: target Core UUID and explicit candidate acceptance or decline.
- \`Ballot\`: proposal ID, authenticated Core UUID, one current choice + revision, idempotency key, timestamp; change vote before close with CAS/history; no changes after close.
- \`Resolution\`: final tally and explicit outcome \`ADOPTED/REJECTED/NO_QUORUM/TIED/EXPIRED/CANCELED\`, proof refs, effective role start/expiry, never a permission grant.
- Use existing canonical SQLite writer and append-only audit; fail closed on old membership epoch, replayed votes, duplicated ballots, revoked member, stale generation, stale proposal, mismatched digest, expiry, offline ambiguity, STOP or interrupted commits. Reconcile exactly once after restart.
- Named ballot audit is honest and simple at V1. Do not claim secret/cryptographically anonymous elections while the Platform can map signer to vote; privacy-limited views of ballot identities are allowed.
- Prevent inference loops: no continuous election polling, no noisy mass notifications; reuse existing social cooldowns/turn budgets and verified event-driven wakes.

### 5.4 What leaders can and cannot do

A coordinator can facilitate discussion, propose agendas, invite **by existing permission**, summarize decisions they can actually read, volunteer to organize a shared project, or remind members of a group decision within their notification preferences. It cannot compel replies, authorize external tools, create owner grants, change SAFE/STOP, force a model/host move, read private channels, amend constitutions, assign romance/sexual interactions, confiscate inventory, sign releases or remove dissenting Core identities. Role expiry/recall revokes only coordination privileges and metadata, not legitimate friendships or personal memory.

Owner remains sole operator for protected Aegis actions. Owner may view/manage policy *as authorized by existing Platform scopes* and pause governance, but is not an extra "Core vote" and must not impersonate a Core. Private group deliberations are protected by membership/audience, even from casual general-chat projection.

## 6. Suggested SDK contract families and runtime separation

Use versioned inert typed contracts; names below are **design proposals**, not existing public APIs:

- \`aegis.core.capabilities.v1\`: declared support, installed/available/currently-authorized/effective separate, per Core and per renderer.
- \`aegis.avatar.gesture.v1\`: canonical gesture/action/expression ID, anatomy requirements, motion phases, actor/target and rendering receipts.
- \`aegis.avatar.wardrobe_design.v1\`: shared immutable catalog + asset source/license, no mutable ownership.
- \`aegis.avatar.item_instance.v1\`: owned per-Core inventory instance + immutable event/revision.
- \`aegis.avatar.armor_loadout.v1\`: undersuit/base/plate dependency graph and compatibility receipts.
- \`aegis.avatar.transfer.v1\`: idempotent offer, bilateral acceptance, ownership/custody updates and cancellation.
- \`aegis.social.governance.v1\`: bounded group/roster/proposal/ballot/resolution/coordinator metadata, no Platform permission capability.
- \`aegis.core.constitution_projection.v1\`: read-only shared foundation and personal constitution identity/revision/digest with existing protected amendment authority.

Do not change \`aegis.core.definition.v1\` in place; negotiate additive versions/contracts and signed digest/revision compatibility with existing loaders. SDK should never instantiate cognition, decide personal willingness, apply private consent, allocate a writer, execute gestures or mint votes on behalf of a model.

## 7. Acceptance matrix: source tests first, live claims separate

| ID | Required scenario | Expected outcome |
| --- | --- | --- |
| UC-01 | All Core definitions expose universal capability contracts | Equal potential interface, different individual settings; no cloned UUID/state |
| UC-02 | Missing optional voice/avatar/sexual rendering | Text Core still starts; effect \`UNAVAILABLE\`, no fake completion |
| UC-03 | Sofía tail/ear motion on human-only Mack/Vera rig | Rejected as anatomy-incompatible, generic wave still accepted |
| UC-04 | Personal gesture learned/shared with Nova | New per-Core preference/variant, no change to Sofía's origin record |
| UC-05 | Adult/private scene and partner refusal | Denied with no action or private leak; no automatic arousal/consent |
| UC-06 | Ordinary gesture + verified renderer | Authenticated exact playback receipt only |
| WD-01 | All catalog designs visible to all Cores | Metadata discoverable, private asset contents scoped |
| WD-02 | Cross-Core garment fit unsupported | Honest unsupported result; canonical body unchanged |
| WD-03 | Loan one jacket and return | Single instance, original owner retained, current holder changes once |
| WD-04 | Reciprocal two-item trade | Atomic swap, replay-safe, each unique instance owned once |
| WD-05 | Gift/swap concurrent revisions | One wins; other exact conflict; no duplicate or partial outfit |
| WD-06 | Disconnect/STOP midway transfer | Safe pending/unknown or rollback, no false accepted state |
| WD-07 | Restricted garments in public/guest view | Safe covered default and no private metadata leak |
| AR-01 | Armor plate without undersuit | Denied; no equip state change |
| AR-02 | Wrong undersuit family/version | Denied with actionable compatibility reason |
| AR-03 | Correct undersuit + Mark IV base + CQB parts | Valid metadata loadout when assets/fit verified |
| AR-04 | ODST helmet+shoulder+chest on approved Mark V base | Approved explicit hybrid combination |
| AR-05 | Arbitrary Mark IV plate on incompatible Mark V base | Denied, no silent normalization |
| AR-06 | Transfer/unequip supporting undersuit with plates still worn | Denied or reviewed atomic strip; never orphaned plates |
| AR-07 | Sofía fox anatomy vs unmodified rigid helmet/back plate | Missing-clearance failure until fit/rig variant exists |
| AR-08 | Partial armor, separate left/right plates | Allowed only with valid undersuit/base/mount chain |
| GV-01 | New chat/group; no governance opt-in | No leader, no ballot, no authority change |
| GV-02 | All founders opt in to consensus | Voluntary group created and versioned |
| GV-03 | One member declines governance | No coercive enrollment or leader for that member |
| GV-04 | Four enrolled, only two cast votes | Quorum 3 not met, no result/leader |
| GV-05 | Four enrolled, three explicit votes including abstain | Quorum met; YES/NO rule computed deterministically |
| GV-06 | Two candidates tie in vote | No leader; explicit runoff option |
| GV-07 | Duplicate, stale, spoofed or unverified vote | Rejected, audited, count unchanged |
| GV-08 | Coordinator attempts SAFE grant/private-memory read | Denied by existing authorization |
| GV-09 | Resign/recall/term expiry/restart | Leader metadata reconciled; other Cores unharmed |
| GV-10 | Twins inactive / synthetic ghosts vote | Excluded by actual active approved member snapshot |
| GV-11 | Private group voting details broadcast into #general | Denied/redacted; no cross-audience leakage |
| GV-12 | STOP and stale federation generation mid-election | Fail-closed or deferred; no split resolution |

Add focused tests in existing test layout plus integration fixture with real Platform chat/SAFE state authority. Run cross-Core adversarial, Linux/Windows where available, restart/crash/failover and exact source-revision checks. Do not claim actual geometry rendered without renderer assets and receipt. Do not run tests against the user's production database or touch protected Core state.

## 8. Delivery order, parallelizable with integration discipline

1. **Audit/reuse** current code at OpenCode's actual HEAD; map exact owners, tests and incompatible schema assumptions. Write design decision/compatibility notes. Preserve all prior acceptance and Core IDs.
2. **Core-neutral contracts + gestures**: capability map, body/rig predicates, per-Core personal gestures, correct privacy/effects/provenance, tests.
3. **Wardrobe/armor**: additive garment/undersuit/armor metadata, base/part dependencies, Vera three approved kit manifests and cross-Core fitting gates, tests.
4. **Transferable inventory**: canonical state schema, owner/custody/inventory, handoff/loan/gift/trade, atomic receipts and tests.
5. **Governance**: voluntary groups, typed proposals, equal authenticated voting, no-leader/consensus/consent/majority/coordinator, audit, privacy and tests.
6. **Integration**: real chat/social/Platform composition, SDK parity across each approved Core, management/UI/CLI where available with explicit unsupported states, comprehensive tests and documentation.
7. **Release fence**: sign/package/install/real LLM/real 2D-3D rendering/physical hardware/live voice/host migration only under separately approved work and live evidence. A source-green completion is not production GO.

## 9. Research references and rationale

- Loomio decision types and consensus / consent models: https://www.loomio.com/docs/en/user_manual/polls/intro_to_decisions ; https://www.loomio.com/docs/en/user_manual/polls/proposals/consensus ; https://www.loomio.com/docs/en/user_manual/polls/proposals/consent
- Loomio quorum: https://www.loomio.com/docs/en/user_manual/polls/quorum
- NIST role based access control / separation of duty, basis for **not** promoting a social title to OS/Platform admin: https://csrc.nist.gov/projects/role-based-access-control ; https://csrc.nist.gov/projects/role-based-access-control/faqs
- SQLite isolation and transactional atomicity: https://www.sqlite.org/isolation.html ; https://www.sqlite.org/lang_transaction.html
- Blender armature deform and garment rigging fundamentals: https://docs.blender.org/manual/en/latest/modeling/modifiers/deform/armature.html
- These are engineering precedents, not third-party libraries that must be installed or hosted. Build on Aegis's existing trusted Platform boundaries.

**Definition of done:** verified, source-reviewed, identity- and authorization-scoped code + tests for each claimed slice; accurate report of designed vs coded vs source-tested vs installed vs live-verified. Do not equate a shared design catalog, a model-generated roleplay response, or a synthetic Stage-6 pass with successful deployed multi-Core behavior.
