# Project summary — RUN live canary pause and next package focus

**Date:** 2026-09-26 (America/Chicago)  
**Branch:** `feature/pkg-ops-run-act-evolve-control-plane`  
**State:** RUN intentionally paused after major live single-host recovery/safety acceptance. Next active engineering focus is CORE/INTERACT live-quality repair.

## Executive summary

Sofía's Windows production RUN path moved from offline-tested infrastructure to a real SCM-hosted canary using a dedicated machine-wide Python 3.13 runtime. The runtime service and independent watchdog now operate as separate `LocalSystem` processes, reach durable RUN state, write fenced heartbeat evidence, and recover from both process loss and stale-heartbeat failure. The live FENCED authority path also proved that an operator fence can stop Sofía and prevent watchdog, SCM recovery, or a manual start from silently resurrecting her.

RUN is paused deliberately before the remaining local reboot/boot and soak gates. Work now returns to the release-critical cognition/social chain: CORE/INTERACT quality, SOCIAL authenticated principal projection, Discord cognition identity quality, then ACT live outbound. RUN will resume afterward for reboot + soak before broader fleet/high-availability work.

## RUN live acceptance completed in this session

- Dedicated machine-wide runtime installed at `C:\Program Files\SofiaAdaLyra\Python313`.
- Python 3.13.15 + pywin32 installed machine-wide; pywin32 post-install completed.
- `SofiaAdaLyra` and `SofiaAdaLyraWatchdog` registered under Windows SCM using machine-wide `pythonservice.exe` and `LocalSystem`.
- Focused hardened RUN gate reached **48/48 passed**.
- Runtime reached durable `READY` and created an advancing heartbeat bound to the SCM PID.
- Independent watchdog ran in a separate PID.
- Crash canary: watchdog restarted the killed runtime; **~26.6 seconds kill→READY**.
- Stale-heartbeat canary: watchdog recorded `service_restart` with `health_state=stale`; **~37.1 seconds stale→READY**.
- FENCED authority canary: watchdog recorded `fenced_stop`; runtime stayed STOPPED; watchdog stayed RUNNING; manual start was refused; no resurrection occurred.
- Startup/fence race hardened so a fence asserted during startup becomes a controlled stop rather than an SCM failure.
- Operator explicitly cleared the fence and restored a fresh READY runtime/heartbeat.

## RUN still open

1. Windows reboot/boot recovery canary.
2. Multi-day single-host soak with resource/health/event review.
3. Later heterogeneous host deployment with OPS/NET.
4. Cross-host exclusive fencing and standby promotion/failback.
5. Replicated durable-state recovery, backup/restore and measured failover RPO/RTO.

## Package status snapshot

| Package / gate | Current state | Next meaningful gate |
| --- | --- | --- |
| CORE | Foundation merged | **Next active work:** natural live-quality repair with INTERACT; identity/personality persistence and latency evidence |
| INTERACT | Accepted semantic/safety foundation | **Next active work:** remove generic/canned assistant fallback; varied greetings/closings; preserve personality in technical mode |
| MEM | Original/provenance + promoted runtime memory foundation accepted | Archive import, privacy/retention/encryption, SOCIAL binding, backup/restore |
| SOCIAL | Minimum principal/audience design exists; runtime projection missing | Authenticated owner must become `Sparks` in shared cognition; negative audience/leakage tests |
| NET | Admission + pinned mTLS transport source accepted | Real Windows/Linux/Pi deployment; outage/revocation acceptance; no general web |
| UI | Windows workbench accepted; Discord DM transport accepted | Preserve same runtime/personality through Discord cognition; later renderer/voice/mobile |
| RUN | **Major live Windows single-host gates accepted; paused** | Reboot/boot recovery + multi-day soak |
| OPS | Strong repository fleet/tooling foundation | Real heterogeneous deployment, maintenance/workload movement, failover/restore |
| ACT | Durable outreach/scheduler/sender boundaries candidate-accepted offline | Real authorized Discord sender/event-loop attachment, receipts/isolation/no spam |
| REL | Overlapping stale drafts / partial foundations | Rebuild one authenticated non-clingy relationship pipeline after SOCIAL |
| AVATAR | Headless presentation foundation accepted | Renderer/mesh/rig/hit-test/animation + authenticated private audience |
| DEV | Repository engineering tools accepted | Live OpenCode/self-tooling acceptance |
| BODY | Simulation-only stale candidate | Real Gaia hardware calibration + independent physical E-stop |
| EVOLVE | Governed revision primitives accepted | SAFE-backed production approvals + VERIFY evidence |
| CLEAN | Recovery-first cleanup candidate | Verified backup/restore, then untrack/migrate live runtime state safely |
| KNOW | Document/manual/provenance foundation accepted | Richer retrieval/citations, privacy/audience, live documentation upkeep |
| INTEGRATE | Typed adapter source foundation accepted | Real service canaries, scope/health/version/rollback |
| ENVIRONMENT | Shared environment + NWS + persistent HOST accepted | Optional Home Assistant canary; fleet-managed location replication later |
| SAFE | Cross-cutting foundations only | Secrets/privacy/revocation/independent stop/backup/restore production enforcement |
| VERIFY | Partial candidate foundation | Current-revision CI/live failure matrix, restore, latency, RPO/RTO and soak |

## Next engineering sequence

1. **CORE + INTERACT live-quality repair**
   - remove generic assistant fallback,
   - natural greetings and varied closings,
   - persistent Sofía personality in technical/casual/emotional contexts,
   - consistent local UI and Discord behavior,
   - measured latency and live Qwen acceptance.

2. **SOCIAL minimum Sparks principal/audience**
   - structural authenticated `principal_id`,
   - exact private-DM audience binding,
   - project authenticated owner into cognition as Sparks,
   - deny unknown/group/guild actors,
   - negative MEM/ENVIRONMENT/UI/ACT leakage tests.

3. **Discord cognition/identity acceptance**
   - same canonical Sofía as local UI,
   - correct authenticated owner recognition,
   - restart/reconnect continuity,
   - human-reviewed conversational quality.

4. **ACT live outbound**
   - explicitly authorized proactive sender,
   - delivery receipts/retry reconciliation,
   - dedupe/rate limit/quiet/mute/stop,
   - no duplicate or unsolicited spam.

5. **Resume RUN**
   - reboot/boot recovery,
   - multi-day soak,
   - then OPS/NET cross-host deployment and later HA/failover work.

## Constraints preserved

- One canonical Sofía identity remains independent of model, host, process and client.
- Git remains source of truth.
- General web/search stays deferred until Discord + OPS host enforcement + real RUN 24/7 acceptance; the narrow NWS route is the existing exception.
- One authoritative writer for durable state; no dual-writer SQLite or live-copy of open SQLite databases.
- Final machine removal always requires Sparks's explicit approval for that exact machine/proposal.
- Protected identity/Constitution changes retain no-self-approval.
