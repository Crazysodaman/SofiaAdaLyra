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
