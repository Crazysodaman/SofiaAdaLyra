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

The owner subsequently clarified the additional machine's **owner-reported hardware** as an **NVIDIA GeForce RTX 3060 with 8 GB VRAM and 32 GB system RAM**. This supersedes the initial 4–6 GiB estimate. Operating system is now confirmed by the owner as **Windows**; the hostname remains unknown. The card's reported installed VRAM is **not** measured free headroom. GPU driver, installed Ollama models, usable context limits, actual resource telemetry, network trust and Fleet enrollment are also unverified. Do **not** create a guessed host identity, endpoint, GPU-capacity receipt, model selection or owner approval.

Phase 11 source hardening now rejects placement where a workload requires RAM/VRAM but actual host telemetry is missing, or where observed remote telemetry is stale (>120 seconds) or future-dated beyond 30 seconds. Windows Fleet telemetry now reads actual per-GPU VRAM used/total and load from the read-only NVIDIA `nvidia-smi` CLI when installed, bounded and explicitly unknown on malformed/missing driver output. It never fabricates free VRAM from the owner-reported 8 GB label. Placement penalizes expired/absent automatic host activity so a stale non-gaming signal cannot outrank a fresh eligible Windows worker. The production Fleet inference path checks current observations; unit fixtures inject a frozen clock, and `test/test_phase11_fleet_gpu_admission.py` uses *synthetic* 8-GiB-VRAM/32-GiB-RAM values to exercise trust, freshness and **free** headroom rejection. No actual PC discovery or benchmarks have occurred. Hostname, Windows version, NVIDIA driver, actual free VRAM and approved Fleet certificate remain to be observed at supervised enrollment.

Reuse `src/sofia/cognition/fleet_engine.py` and `src/sofia/ops/placement.py`, which already use authenticated Fleet identity, trust/lifecycle checks, telemetry and gaming-related interactive pressure. Enroll the extra host separately using the approved owner-supervised mTLS enrollment path. A remote model must already be installed or separately approved for exact installation; **no silent download, provider role substitution or cloud fallback**. Only place workloads after independently measured VRAM and policy requirements are satisfied; never assume the primary 9B model fits 4–6 GiB.

The GPU host may serve a *small/quantized fast role* if later verified, with full prompt-routing security, model license, throughput and context-window checks. A physical RTX 3060 8GB is not by itself proof that the configured primary or secondary model fits in GPU VRAM with its requested context length. A failed remote request remains a known failure unless the existing owner-approved local-fallback policy expressly allows recovery.

## Explicit boundaries

1. A live game still running but idle for 30 minutes prevents preload. This avoids reclaiming VRAM while a game may be paused.
2. Unknown/missing/stale desktop activity or unknown VRAM never triggers an auto-preload.
3. Active model use is not killed just because a game starts; an idle model is unloaded when safe. Autonomy and foreground inference may consequently wait or fail explicitly while gaming.
4. The Windows tray must be running in the interactive session to produce the idle observation. There is no background keystroke capture, remote surveillance or raw input retention.
5. Real acceptance still needs Venus gaming launches, 29:59/30:00 transition, tray crash/stale signal, manual override, active chat, memory pressure, 4–6 GiB host enrollment and measured cold-start/GPU contention on real hardware.

**Status:** Production *source code committed*, unit tests deferred, no live activation, no safety or performance acceptance. Workstream 4 remains in Phase 11.
