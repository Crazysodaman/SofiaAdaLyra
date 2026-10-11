# V18 Workstream 4: Phase 12 source-to-production vision audit

**Date:** 2026-10-11. **Branch:** `main` only. **Test campaign:** deferred, not executed. **No host action, screen capture, live UI/VM or model was run.**

## Scope and acceptance standard

Source of truth: original V18 CA-1501–1506 and CA-6201–6218 requirements and the existing `docs/development/avatar-screen-interaction-contract.md`. A Python data class, manually entered target name, synthetic frame bytes or printed consent flag is **not** proof that an operating-system screen picker was invoked. Every real capture requires an authenticated active-user OS session, source identity, OS-selected exact target, independent interactive consent, secure/protected-surface exclusion, expiry and independently observed pixels.

## Production source observations

| Component / journey | Actual source evidence | Coding status | Acceptance |
|---|---|---|---|
| Four named owner journeys | `src/sofia/vision/journeys.py`, `src/sofia/ui/settings_sections.py` | Scoped proposals, distinct durations and no implicit action rights | Not run |
| Exact UI screen target | Settings allows typing an identifier and purpose | Not an OS picker or target identity proof | Blocked |
| OS interactive capture on Windows 11 | No verified Windows.Graphics.Capture picker/WinRT active-user adapter reached from UI | Missing production adapter | Blocked |
| OS interactive capture on Terra / Hyprland | No verified xdg-desktop-portal ScreenCast/PipeWire local adapter reached from UI | Missing production adapter | Blocked |
| SAFE screen capabilities | `src/sofia/safe/permissions.py` explicitly classifies `screen.discover`, `screen.capture_once`, `screen.watch_scoped`, `screen.remote_view`, `screen.act_exact`; all nonautomatic, latter two never-self-authorized | Implemented classification only; no host executor | Tests deferred |
| Scoped snapshot/follow expiry | `src/sofia/vision/consent.py`, `journeys.py` | Type-level exact scope and exclusive expiry; permit and picker flags alone are **not** cryptographic OS consent evidence | Tests deferred |
| Source-linked frame hash | `src/sofia/vision/journeys.py` | Bounded digest-only metadata, principal+audience+device source check, stable receipt ID matching; no pixels persisted | Tests deferred |
| Live watch, visible indicator, lock/picker cancellation | UI can cancel a *pending proposal* only | No running OS watch worker or guaranteed host stop signal | Missing |
| Local protected desktop and app redaction | `receipt_from_permitted_bytes` rejects caller-reported protected surfaces | No OS-proven secure desktop, sensitive target classifier or independent redaction | Missing |
| Image interpretation and prompt-injection boundary | Frame content is not semantically verified; hash comparison is not a scene change claim | No production multimodal vision/inference route or untrusted-pixel prompt fence | Missing |
| Remote viewing/export and mouse/keyboard | SAFE classification explicitly denies model self-authorization | No target-bound permission/transport, no independent GUI executor | Missing |
| Receipt history/privacy | Canonical `sofia.db` records only hash/metadata, scoped to principal+audience; old audience-only records remain unassigned | Source implemented, not tested; no actual OS frame receipt produced | Tests deferred |
| CA-1501–1506 information needs / sensor confidence | No end-to-end typed observation-to-GOALS evidence path demonstrated in this source pass | Not individually verified; no inference of completion | Open |

## Negative implementation constraints

1. **Do not register an executable capture handler** until an active-user adapter actually returns independently verified OS permission and target identity. Faking `confirmed_interactive_os_picker=True` or reusing fixtures is explicitly invalid in production.
2. Background service Session 0 has no automatic right to see Venus's desktop. Artemis and headless Hephaestus must not be treated as owner-visible monitors.
3. A selected app/window is not permission to share externally, discover other targets, act with the mouse/keyboard, or mine private Main/Discord content.
4. `screen.remote_view` and `screen.act_exact` require independently authenticated owner controls and destination/target restrictions; no automatic or standing grant.
5. Capture and interpretation rights remain separate from action rights and model training/data-use rights.
6. No source-visible proof of performance, privacy rejection rates, or end-to-end acceptance exists. The first live test must require a genuine OS indicator and target picker.

## Next concrete engineering dependencies

- Windows 11: independently launched, user-session Windows.Graphics.Capture picker, target identity/metadata and frame lifetime, protected-surface refusal, lock and revocation.
- Terra/Hyprland: portal ScreenCast session, PipeWire frame transport, portal cancellation, explicit local agent identity and entitlement.
- Common bounded host bridge: signed/peer-authenticated OS selection receipt with exact target, session and timestamp, ephemeral in-process pixels, operation scope and host stop/deadline; reject caller-supplied boolean claims.
- Only then wire one-time captures to VLM under user-reviewed privacy/redaction and resource budgets. Add start/stop visible indicator and route-specific tests.
- Finally wire separate, narrowly authorized `screen.act_exact` and remote export paths, if still desired, without any implicit desktop control.

**Decision status:** existing chosen design remains explicit single-window OS selection, default on-demand snapshot and separately opted-in bounded watch. No new owner decision or hardware enrollment made in this audit. **No original Phase 12 task accepted.**
