# V18 focused production audit: Phases 08, 09, 12, 13

**Date:** 2026-10-11. **Branch:** `main` only. **Reviewed main:** `f98167ad6a661e63844d630ec9ef6617b9b7a02a`.
**Scope:** 209 immutable V18 IDs, not a replacement for the 700-task master. Each item below preserves its global ledger status; WS4's finer-grained evidence is shown separately.

## Owner decisions added for Phase 12

- Sofía may operate the **mouse and keyboard** only through separately authorized exact GUI actions. Vision/capture permission does not authorize clicking or typing.
- **Venus** is protected as a gaming workstation. No input if game evidence is positive, stale, manually overridden, missing, or the current foreground window differs from the independently approved HWND/PID; per-action live process inspection is required. Executable-game detection cannot guarantee anti-cheat safety for every game. The conservative fallback is refusal.
- **Artemis and enrolled VMs** may eventually support desktop automation on their own interactive OS sessions, each with independent per-host identity and SAFE approval. Hyper-V host visibility is not VM guest visibility. Session 0 and a VM without an OS cannot receive GUI input.
- **Exact SAFE boundary:** `screen.act_exact` remains NEVER_SELF_AUTHORIZED and requires locally verified owner WebAuthn/FIDO2, one-use exact approval, canonical STOP clear, exact executing-host match and target-bound input. No standing grant, no screen-derived instruction authority.
- Current `src/sofia/vision/desktop_control.py` supplies a Windows foreground executor and `desktop_control_cli.py` its real interactive owner entrypoint. No automatic remote GUI control, Windows.Graphics.Capture picker, Linux PipeWire adapter, model-driven GUI control, screenshot semantic VLM verification, or active Hephaestus guest is claimed.

## Actual source routes and gaps

| Phase | Real production source | Key missing acceptance/coding evidence |
|---|---|---|
| 08 | `application/background_runtime.py` → `PresenceInitiativeEngine` → ACT delivery; `application/expression_runtime.py`; EMOTION and REL stores | Acknowledged recipient receipts across channels, complete cue renderer proof, long-gap emotional/relationship behavior, prospective shared conversation/hobby invitations, seven-day no-nag test |
| 09 | `SofiaApplication` → `SelfDirectedLifeCoordinator.tick` → canonical LIFE/GOALS/RUN/Creative persisted jobs and verified artifact evaluation | Exhaustive 66-ID caller-to-effect closure, actual Windows creative validators, abnormal interrupt/restart, independent critique and adaptive resource budgets, live absence/soak |
| 12 | `vision/consent.py`, `vision/journeys.py`, new `vision/desktop_control.py` and separate signed owner CLI | Real Win11 OS-picker screen capture, Hyprland portal/PipeWire, comprehensive privacy/redaction, active watch/revocation, model-safe perception; interactive Windows/anti-cheat acceptance |
| 13 | `ops/workshop_*`, typed restricted Hyper-V/Fleet preflights, `ops/digital_twin.py` simulation | Owner's existing Hephaestus VM has no installed OS/guest worker, hence no live isolated commands or attestable sample; host firewall/ACL, verified resource quotas and guest isolation acceptance still unavailable |

## Testing scope

- Static syntax and deterministic existing Phase 08/09/12/13 Python regression tests are selected in `.github/workflows/v18-focus-08-09-12-13.yml`.
- New `test/test_vision_desktop_control.py` uses a spy backend; never injects input, never bypasses owner key or STOP. These tests cannot prove Windows focus, real game detection or ban-free behavior.
- Integration acceptance still requires independently supervised Venus game start/pause/close tests, hardware FIDO2, Win11 foreground switching and real Artemis guest isolation tests. Do not change hosts or enroll VMs autonomously.
- No original CA ID is marked accepted merely by writing this report or tests; record exact successful CI/live receipts in the master ledger later.

## Exact original-ID checklist and latest classifications

### Phase 08: Emotion / relationship / companion presence (56 IDs)

Global status: {"unassessed":56}.

| CA ID | Master ledger | Workstream source evidence |
|---|---|---|
| `CA-401` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-402` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-403` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-404` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-405` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-406` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-407` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-408` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-409` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-410` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-411` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-501` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-502` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-503` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-504` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-505` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-506` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-507` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-508` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-509` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-510` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-511` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-1801` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-1802` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-1803` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-1804` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-1805` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-1806` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-2501` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-2502` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-2503` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-2504` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-2505` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-2506` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-2507` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-2508` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-3801` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-3802` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-3803` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-3804` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-3805` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-3806` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-3807` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-3808` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-3809` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-3810` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-6001` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-6002` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-6003` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-6004` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-6005` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-6006` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-6007` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-6008` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-6009` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |
| `CA-6010` | unassessed | Phase 08 source triage; ongoing Presence/Expression evidence |

### Phase 09: LIFE / GOALS / creative initiative (66 IDs)

Global status: {"partial_wiring":8,"unassessed":56,"code_present_unverified":2}.

| CA ID | Master ledger | Workstream source evidence |
|---|---|---|
| `CA-101` | partial_wiring | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-102` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-103` | code_present_unverified | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-104` | partial_wiring | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-105` | partial_wiring | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-106` | partial_wiring | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-107` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-108` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-109` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-110` | partial_wiring | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-111` | code_present_unverified | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-112` | partial_wiring | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-113` | partial_wiring | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-114` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-115` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-201` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-202` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-203` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-204` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-205` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-206` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-207` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-208` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-209` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-210` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-601` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-602` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-603` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-604` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-605` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-606` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-607` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-608` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-609` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-610` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-1301` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-1302` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-1303` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-1304` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-1305` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-1306` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-1307` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-1601` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-1602` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-1603` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-1604` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-1605` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-1606` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-2401` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-2402` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-2403` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-2404` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-2405` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-2406` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-2407` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-2408` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-3501` | partial_wiring | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-3502` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-3503` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-3504` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-3505` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-3506` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-3507` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-3508` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-3509` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |
| `CA-3510` | unassessed | Phase 09 source triage; LIFE/GOALS/RUN production source |

### Phase 12: Screen perception and separately authorized input (24 IDs)

Global status: {"unassessed":23,"partial_wiring":1}.

| CA ID | Master ledger | Workstream source evidence |
|---|---|---|
| `CA-1501` | unassessed | phase_inventory_only |
| `CA-1502` | unassessed | phase_inventory_only |
| `CA-1503` | unassessed | phase_inventory_only |
| `CA-1504` | unassessed | phase_inventory_only |
| `CA-1505` | unassessed | phase_inventory_only |
| `CA-1506` | unassessed | phase_inventory_only |
| `CA-6201` | partial_wiring | code_path_integrated_unverified (source candidate; no executed tests) |
| `CA-6202` | unassessed | partially_implemented_unverified |
| `CA-6203` | unassessed | phase_inventory_only |
| `CA-6204` | unassessed | phase_inventory_only |
| `CA-6205` | unassessed | partially_implemented_unverified |
| `CA-6206` | unassessed | partially_implemented_unverified |
| `CA-6207` | unassessed | partially_implemented_unverified |
| `CA-6208` | unassessed | partially_implemented_unverified |
| `CA-6209` | unassessed | phase_inventory_only |
| `CA-6210` | unassessed | phase_inventory_only |
| `CA-6211` | unassessed | phase_inventory_only |
| `CA-6212` | unassessed | phase_inventory_only |
| `CA-6213` | unassessed | phase_inventory_only |
| `CA-6214` | unassessed | phase_inventory_only |
| `CA-6215` | unassessed | phase_inventory_only |
| `CA-6216` | unassessed | phase_inventory_only |
| `CA-6217` | unassessed | phase_inventory_only |
| `CA-6218` | unassessed | phase_inventory_only |

### Phase 13: Hephaestus / isolated digital twin (63 IDs)

Global status: {"unassessed":63}.

| CA ID | Master ledger | Workstream source evidence |
|---|---|---|
| `CA-2801` | unassessed | partially_implemented_unverified |
| `CA-2802` | unassessed | phase_inventory_only |
| `CA-2803` | unassessed | phase_inventory_only |
| `CA-2804` | unassessed | phase_inventory_only |
| `CA-2805` | unassessed | partially_implemented_unverified |
| `CA-2806` | unassessed | partially_implemented_unverified |
| `CA-2807` | unassessed | partially_implemented_unverified |
| `CA-2808` | unassessed | phase_inventory_only |
| `CA-2809` | unassessed | phase_inventory_only |
| `CA-2810` | unassessed | phase_inventory_only |
| `CA-2811` | unassessed | phase_inventory_only |
| `CA-2812` | unassessed | phase_inventory_only |
| `CA-2813` | unassessed | phase_inventory_only |
| `CA-2814` | unassessed | phase_inventory_only |
| `CA-2815` | unassessed | phase_inventory_only |
| `CA-2816` | unassessed | phase_inventory_only |
| `CA-2817` | unassessed | phase_inventory_only |
| `CA-2818` | unassessed | phase_inventory_only |
| `CA-2819` | unassessed | phase_inventory_only |
| `CA-2820` | unassessed | phase_inventory_only |
| `CA-2821` | unassessed | phase_inventory_only |
| `CA-2822` | unassessed | phase_inventory_only |
| `CA-2823` | unassessed | phase_inventory_only |
| `CA-2824` | unassessed | phase_inventory_only |
| `CA-2901` | unassessed | partially_implemented_unverified |
| `CA-2902` | unassessed | code_path_integrated_unverified (source candidate; no executed tests) |
| `CA-2903` | unassessed | code_path_integrated_unverified (source candidate; no executed tests) |
| `CA-2904` | unassessed | code_path_integrated_unverified (source candidate; no executed tests) |
| `CA-2905` | unassessed | phase_inventory_only |
| `CA-2906` | unassessed | phase_inventory_only |
| `CA-2907` | unassessed | phase_inventory_only |
| `CA-2908` | unassessed | phase_inventory_only |
| `CA-2909` | unassessed | partially_implemented_unverified |
| `CA-2910` | unassessed | phase_inventory_only |
| `CA-2911` | unassessed | partially_implemented_unverified |
| `CA-2912` | unassessed | partially_implemented_unverified |
| `CA-2913` | unassessed | partially_implemented_unverified |
| `CA-2914` | unassessed | partially_implemented_unverified |
| `CA-2915` | unassessed | phase_inventory_only |
| `CA-2916` | unassessed | phase_inventory_only |
| `CA-2917` | unassessed | phase_inventory_only |
| `CA-2918` | unassessed | phase_inventory_only |
| `CA-2919` | unassessed | phase_inventory_only |
| `CA-2920` | unassessed | phase_inventory_only |
| `CA-2921` | unassessed | phase_inventory_only |
| `CA-2922` | unassessed | phase_inventory_only |
| `CA-3601` | unassessed | code_path_integrated_unverified (source candidate; no executed tests) |
| `CA-3602` | unassessed | code_path_integrated_unverified (source candidate; no executed tests) |
| `CA-3603` | unassessed | code_path_integrated_unverified (source candidate; no executed tests) |
| `CA-3604` | unassessed | code_path_integrated_unverified (source candidate; no executed tests) |
| `CA-3605` | unassessed | code_path_integrated_unverified (source candidate; no executed tests) |
| `CA-3606` | unassessed | partially_implemented_unverified |
| `CA-3607` | unassessed | code_path_integrated_unverified (source candidate; no executed tests) |
| `CA-3608` | unassessed | code_path_integrated_unverified (source candidate; no executed tests) |
| `CA-3609` | unassessed | code_path_integrated_unverified (source candidate; no executed tests) |
| `CA-3610` | unassessed | phase_inventory_only |
| `CA-4301` | unassessed | code_path_integrated_unverified (source candidate; no executed tests) |
| `CA-4302` | unassessed | code_path_integrated_unverified (source candidate; no executed tests) |
| `CA-4303` | unassessed | code_path_integrated_unverified (source candidate; no executed tests) |
| `CA-4304` | unassessed | partially_implemented_unverified |
| `CA-4305` | unassessed | code_path_integrated_unverified (source candidate; no executed tests) |
| `CA-4306` | unassessed | partially_implemented_unverified |
| `CA-4307` | unassessed | code_path_integrated_unverified (source candidate; no executed tests) |

## Results boundary

This audit maps **209** task IDs, but is **not** a claim that all 209 requirements were completely implemented or that any task passed its live acceptance gate. Workstream 3/4 source audits have not been replaced.

## Executed CI evidence and unresolved defects (2026-10-11)

These outcomes supersede the earlier statement that only authored tests exist. Actual Windows CI jobs ran on exact GitHub revisions. All task acceptances remain false.

- Windows focused Phase 08/09/12/13 source-and-regression gate at revision `8cafe53555d8ce8b753da5a1ed98a2de4f304264`, run [38174115143](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/38174115143): **89 passed, 74 failed** in 154.19 seconds. The new `test_vision_desktop_control.py` and `test_v18_presence_private_life_scope.py` cases did not appear in the failed-test list. The failures were 26 `test_presence_initiative`, 8 `test_life_autonomous_followthrough`, 3 `test_life_verified_milestone_production`, 5 `test_life_atomic_admission`, 2 `test_life_postrun_verification`, 17 `test_life_goal_run_resume_fence`, and 13 `test_life_run_outcome_reconciliation`. Earlier focused run `21cbe442...` was 73 passed/83 failed. The new counts reflect bootstrap fixture progress, not overall readiness.
- The broader matrix at revision `8cafe535...`, run [38174115133](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/38174115133), was **416 passed, 54 failed**, including additional canonical SQLite fixture issues and Windows platform-specific source path failures. The old OS bootstrap `fsync` read-handle issue was fixed in `1c09facab58ef1ffe632bb6fb1d10f443739ff3b`.
- Manual verification and cross-platform checks failed at that revision, partly due the package-selection test importing `conftest` as a bare module. Source fix `9f64bb6cbab004ae67e7895986334c923fd7ad3e` imports it through its `test` package. The Windows immutable roadmap byte checker now accepts **only** canonical LF or the exact CRLF checkout equivalent; substantive text edits remain rejected (`dd5bac997f80d8084b5dde6c73cefb8c2483a890`, regression `094d2ebca2a0702cca28eafaf1a3b5792ceac089`).
- The release candidate workflow at revision `8cafe535...`, run [38174115123](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/38174115123), rejected newly added `.gitattributes` source archive bytes, so the attributes file was removed at `5f01e3c28047f56d6b10fb625ca5e0214c2bde5f`; release acceptance remains **unproven** until a subsequent complete green run.
- Genuine FIDO2 enrollment/consumption with physical owner hardware, game start/pause/cancel tests, interactive Windows mouse/keyboard behavior and any Hephaestus guest job were **not** executed. Real acceptance is not reproducible in ephemeral GitHub runner without those hosts or enrolled key.

### Follow-up source hardening

- Win32 exact input path uses the existing SYSTEM process inspector (no undeclared optional psutil dependency), refuses incomplete process evidence, checks the actual approved HWND and Win32 click hit-testing before input. Production source changes include `7809c77f31e2eb23e07c5c7dac5a907dbe0d5d1d` and `2cae7702efb79261738d2884d158b64d2c689ba5`. Each operation requires independently authenticated FIDO2 `screen.act_exact` receipt and STOP clearance.
- Private `task_completed` LIFE outreach now refuses implicit audiences or unapproved recipients instead of republishing source events. Production source `254aa3756ab80cf29e23d2fbc0aab7ad94fedfe4`, tests `f82e11ecf9d952a1dfb264b7dafc733d5038412a`.
- The user-facing CLI and original limitation guide are at `src/sofia/vision/desktop_control_cli.py` and `docs/development/v18-phase12-owner-input-operation-2026-10-11.md`. No automatic model-controlled GUI use is claimed.

**Final rule:** 209 assigned tasks are not yet coding-complete or test-accepted. Original master IDs preserved; eight additional source-grounded items marked partial only. Phase 13 live implementation remains blocked on an OS-installed, operator-authorized Hephaestus guest and verified physical isolation.

## Follow-up coding and CI audit: GOALS scope and release provenance

- **Measured focused improvement:** at source revisions `80ac4b6cb23772d48f83c8580c14d861fa9ff19f` and `3d09f41e26f9b2a6a8420f4e0d9597536480bbb1`, 27 failures and 136 passes; the subsequent `52dee4a3d4ee2bb427ee4a16592729671f0983f9` run explicitly included the Phase 09 goal-audience regression and reported **27 failed, 137 passed**. [Focused run](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/38174912724). This is CI improvement, not full-phase acceptance.
- **Production root fix** `80ac4b6cb23772d48f83c8580c14d861fa9ff19f`: GOALS canonical authenticated audience is `private:local:text`; LIFE own project audience is `local:text`. Comparing them literally falsely denied legitimate grounded projects. Source checks now use `audience_scope(local_sparks_principal())`, enforce exact owner principal and preserve an independent LIFE audience gate. This affects motivation, GOALS reconciliation, RUN admission and async authority replay.
- 18 of the remaining original focused failures used a LIFE-only test harness with no application's conversation table, despite ACT `has_pending()` correctly rejecting a missing interaction evidence schema; repaired by explicit test fixture bootstrap (not by disabling GoalJournal's production guard) at `dee322697b0886aea0b6c18457cff4b4316dfa6d`.
- Seven checkable LIFE test paths previously used a plain string as originating interest without recording any canonical `InterestRecord`. Updated test builder to create a source-linked interest at `292884b1a05905bd56d2e556bf9950edc4244ce1`. The subjective/uncheckable objective test now expects the existing conservative PAUSED state, not unsupported ACTIVE spending (`4f9b5d1477da413bc603d23ec18e140eb6d45989`). A post-fix focused result is still required.
- A separate Windows matrix failure stemmed from `os.fsync()` applied to an `rb` file handle in runtime configuration seed. Corrected to `r+b` while keeping atomic source publication (`81b26e74cb6d4641fb62feacc65a5f8ea9373b4f`). Historical test helpers for MEM, HABIT, UI, COGNITION, CONVERSATION now perform explicit authorized canonical test bootstrap.
- Release candidate on original Git/tar materialization failed raw source-byte provenance; `src/sofia/verify/stage_release_source.py` stages each blob directly by hash from HEAD, and `.github/workflows/release-candidate.yml` builds two wheels from independent disposable copies, leaving signed source unchanged (`fec1a11183e32ab9561003aae14fb6ea4b0bbc32`, `36a930cc408052c91564aa2d986168bbb931448a`, `968487ac3ec298c43c9a6789e8e26968b6541452`). Reproducibility tests include Windows CRLF and unreviewed symlink rejection. The workflow progressed to revision-bound verification on [run 38175070286](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/38175070286); a fully green release result was not yet observed.
- GUI target guard now also requires the executing Windows process session equal the active local console session (`5365ce07b6d365b54417847f0a8a724654c24468`). Session-0, RDP/different-session and non-console injection cannot be represented as verified input.

### Still required

1. Re-run the focused 08/09/12/13 revision-pinned tests with post-fixture changes; investigate any remaining legitimate behavioral assertion failures.
2. Verify release and matrix green on same HEAD before acceptance; separate preexisting/non-scoped failures from Phase 08/09/12/13.
3. Execute real Windows screen picker, hardware FIDO2, actual benign input and Venus gaming/unknown state negative acceptance under operator supervision; no anti-cheat guarantee is claimed.
4. Provision and authenticate isolated Hephaestus Debian guest; prove real host quotas, blocked network and one nonprivileged worker canary before Phase 13 execution acceptance. This session has not modified any real host.

**Coding status:** the selected 209 original tasks are not all implemented; no task is elevated to `accepted` by this audit. The tracked blockers above remain open.

## Focused Phase 08/09/12/13 CI milestone: 163 / 164

- Windows focused test run at `4f9b5d1477da413bc603d23ec18e140eb6d45989` completed with **163 passed, 1 failed** in 204.68 seconds: [run 38175216585](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/38175216585). The single failure was `test_revision_abstains_if_goal_pauses_during_generator`, whose fixture asked for `deferred_daily_draft_limit` while not supplying any new generation callback. Production correctly returned `revision_requires_native_drafting` because none was available. A test correction `077735e2349de9aac729401fb9359c84984bf848` now supplies a model candidate so the original same-day draft-budget gate can be exercised, with no relaxation of production autonomy controls.
- From the original 89 passed / 74 failed, this confirms **74 to 1** fewer failing checks and **163 passing** checks in the focused suite before the last test correction. Do not claim final green until the new SHA test run completes.
- The checked-in main code changes have not been proven on a physical gaming Venus desktop or OS-installed Hephaestus guest. CI synthetic success, if later achieved, remains separate from the original acceptance requirements.
