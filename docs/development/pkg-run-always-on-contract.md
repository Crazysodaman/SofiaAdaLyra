# PKG-RUN: always-on operation and periodic thinking

**Status (2026-09-20):** RUN1 is a new, isolated, opt-in opportunity gate and explicit runner on `feature/pkg-run-always-on`. It is NOT connected to Sofía's application loop, NOT a Windows/Linux service, and has NOT passed Windows or live model testing. The current `IdleReflectionWorker` already polls while the application runs, but only reflects on recorded eligible emotional events. No execution or thought occurs while Sofía is stopped.

## What Sparks means

Sofía may be available around the clock on a supervised host AND periodically consider whether a useful, permitted, evidenced thought is due even when nobody is chatting. A wake is a scheduled *opportunity*, not evidence of an actual thought, an ongoing inner life, a completed task, or autonomous action. Sometimes the correct output is **nothing to do**. Do not call the model constantly, manufacture events, send repetitive check-ins, or imply awareness of a shutdown interval beyond recorded evidence.

## Separation of responsibilities

- **RUN owns:** boot-start supervisor/service, graceful shutdown and restart, readiness/health checks, bounded worker schedules and runtime state, resource caps, contention with foreground chat, idle quiet windows, failure visibility, recovery and observability. The service must supervise a single authorized Sofía application instance, not spawn competing persona instances.
- **CORE owns:** canonical identity/personality, grounded cognitive request and accurate restart awareness.
- **MEM owns:** original source records, retrieval, correction, durable remembered preferences and archive import. RUN does not invent those records.
- **ACT owns:** deciding goals, autonomous initiative, plans, actual outreach and bounded helpers, with external authorization, quiet/busy/mute and real delivery acknowledgment. RUN waking Sofía never grants ACT rights.
- **NET owns:** authenticated transport/agents between hosts, including Artemis, with delegated scoped grants; Windows service availability does not imply another machine is enrolled.
- **SAFE/VERIFY own:** secrets, independent stop/revoke, backup/restore, failure drills, versioned verification and deployment gates. UI/BODY remain optional and separately authorized.

## R1: bounded opportunity gate (code exists, not accepted)

`src/sofia/run/periodic.py` uses the *existing* state SQLite database, with a separate `run_thought_opportunities` table. Explicit `OpportunityPolicy` defaults to disabled. It validates interval (5 minutes to 24 hours), daily attempt cap (1 to 48), optional UTC quiet hours, observed user-busy state and up to 16 bounded recorded source event IDs. `claim` reserves a slot atomically, retaining cooldown and UTC-day quota across process restarts. `PeriodicThoughtRunner.tick` invokes a host-supplied existing reflection operation **only after a claim**; it records `reflected` only when the callback confirms one of the provided evidence IDs, `no_event` if nothing was processed, and `failed` if an exception occurs. Errors propagate. A crash can leave a `claimed` attempt; it is not reinterpreted as a completed thought or automatically retried in the same slot. The source events remain under the existing journal's separate deduplication and policy rules.

No new daemon/thread, model provider, installer, service account, network port, filesystem scan or message delivery is started by RUN1. The gate does not itself authenticate the caller or prove model output is true. Configuring the host, service and actual schedule are later work, not implied by importing this package. UTC quiet hours are explicitly UTC, not silently assumed to mean local time.

## R2: supervised service and wiring (planned)

After the headless INTERACT gate and relevant SAFE review, choose the actual host (Windows Artemis vs a Debian/Ubuntu VM) based on measured Ollama/model availability and data access. Implement an OS-native service definition with bounded restart/backoff, single-instance lock, working-directory/environment/service-identity checks, clean stop waiting for current inference/SQLite work, an observable health endpoint or status command (not open by default), and opt-in wake loop feeding verified event IDs to R1. Reconcile or replace the existing IdleReflectionWorker polling rather than running two reflection schedulers. No unrequested automatic startup installation or remote networking.

## R3: pilot and acceptance (planned)

Verify on the chosen real host: stop/start and hard-failure recovery, host reboot with observed continuity evidence, successful original-data and lab-state preservation, corrupt/unavailable state handling, Ollama offline and reconnect with finite backoff, busy-game resource throttling if measured, clean cancellation with no duplicate model calls or messages, quiet hours and opt-out. Record actual uptime, CPU/GPU/RAM and token/latency budgets before setting an interval. First pilot = **available 24/7 with occasional, evidence-backed reflection**, not continuous LLM output or independent authority. Only enable public/mobile reachability after NET/SAFE/UI authentication. A full pytest run remains scheduled after PKG-INTERACT as Sparks requested; RUN1 gets focused tests separately.

## Evidence ledger

- Previous Windows focused INTERACT I1: 59 passed (51.61 s) at `7175835`.
- Previous Windows focused INTERACT I2/I3: 44 passed (53.05 s) at `84695a6`.
- New I4 Windows run at `e83c2e6`: 33 passed, 1 failed because unrelated conversation accessed absent lab configuration; fix committed on INTERACT branch `eb73357`, **not retested**.
- RUN1 source and offline unit tests: committed, **not executed on Windows or live**. No 24/7 deployment, no autonomous thought demonstration.
