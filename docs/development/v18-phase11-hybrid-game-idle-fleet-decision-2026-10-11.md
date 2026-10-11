# Workstream 4 | Phase 11 | Approved hybrid gaming, desktop idle and Fleet inference

**Decision date:** 2026-10-11. **Owner direction:** gaming on Venus takes priority; a verified active-user desktop idle window of approximately 30 minutes should allow model preloading; an additional owner GPU computer may provide model inference after its hardware/identity and Fleet approval are reviewed. **Coding only:** no tests, CI, model loads/unloads, hardware inspection, remote enrollment or host configuration performed.

## Production source paths

- `src/sofia/ops/activity.py`: `windows_desktop_idle_seconds` uses Windows `GetLastInputInfo` in the current interactive tray session. It records *age only*, never keystrokes. `observed_desktop_activity` requires no observed game process, an aware threshold and real last-input evidence. Unknown is never coerced to idle.
- `src/sofia/ui/tray_agent.py`: every existing 30-second process observation chooses GAMING before IDLE; the IDLE signal starts at `RuntimeUserSettings.cognitive_model_idle_preload_seconds`, default 1800 seconds. A still-running game always wins even when its input has stopped. Manual Game Mode ON remains an explicit GAMING override. There is no background Session 0 desktop-input assumption.
- `src/sofia/composition/engines.py`: the existing OPS canonical activity store supplies both gaming and idle observers; automatic observations more than 120 seconds old cannot be used to preload. Missing game/idle evidence stays unknown. The lifecycle policy remains owner-configured and can be updated without inventing a new scheduler.
- `src/sofia/cognition/model_lifecycle.py`: `hybrid_gaming_idle` reclaims **idle** locally loaded models during observed gaming, preserves any model actively serving a request, makes ordinary activity on demand, and only preloads both configured role models after verified non-gaming idle AND independently observed enough RAM and VRAM and low CPU/GPU utilization. Unknown telemetry fails closed; the same model shared by both roles is counted once. No installation/download of missing models or role-identity change.
- `src/sofia/config/model.py`, `src/sofia/config/defaults.py`, `src/sofia/config/user_settings.py`: bounded 60–86400 second threshold, default 1800; hybrid selectable as an explicit policy. Existing saved residency settings are not silently rewritten.
- `src/sofia/ui/settings_window.py`, `src/sofia/ui/control_center.py`, `src/sofia/ui/windows_tray.py`: owner can select the hybrid policy and set idle threshold in Models settings; tray quick control has the new option.
- `test/test_model_hybrid_residency_production.py`: source-only synthetic cases for game-first eviction, safe in-flight calls, exact 1800-second idle threshold, unknown inputs and insufficient RAM/VRAM. No tests executed.

## Extra 4–6 GiB GPU host

The owner mentioned an additional, not yet enrolled or identified machine with approximately **4–6 GiB** of VRAM. Its actual hostname, operating system, GPU model, driver, measured usable VRAM, network trust, available disk/RAM and model inventory are unknown. Do **not** insert guessed host entries, endpoints, VRAM values, model choices or approvals.

Reuse `src/sofia/cognition/fleet_engine.py` and `src/sofia/ops/placement.py`, which already use authenticated Fleet identity, trust/lifecycle checks, telemetry and gaming-related interactive pressure. Enroll the extra host separately using the approved owner-supervised mTLS enrollment path. A remote model must already be installed or separately approved for exact installation; **no silent download, provider role substitution or cloud fallback**. Only place workloads after independently measured VRAM and policy requirements are satisfied; never assume the primary 9B model fits 4–6 GiB.

The GPU host may serve a *small/quantized fast role* if later verified, with full prompt-routing security, model license, throughput and context-window checks. A failed remote request remains a known failure unless the existing owner-approved local-fallback policy expressly allows recovery.

## Explicit boundaries

1. A live game still running but idle for 30 minutes prevents preload. This avoids reclaiming VRAM while a game may be paused.
2. Unknown/missing/stale desktop activity or unknown VRAM never triggers an auto-preload.
3. Active model use is not killed just because a game starts; an idle model is unloaded when safe. Autonomy and foreground inference may consequently wait or fail explicitly while gaming.
4. The Windows tray must be running in the interactive session to produce the idle observation. There is no background keystroke capture, remote surveillance or raw input retention.
5. Real acceptance still needs Venus gaming launches, 29:59/30:00 transition, tray crash/stale signal, manual override, active chat, memory pressure, 4–6 GiB host enrollment and measured cold-start/GPU contention on real hardware.

**Status:** Production *source code committed*, unit tests deferred, no live activation, no safety or performance acceptance. Workstream 4 remains in Phase 11.
