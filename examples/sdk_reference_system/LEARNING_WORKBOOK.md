# Build the finish line: Aegis SDK learning workbook

**Status:** developer/Core training plan and runnable **in-process** fixtures, not production authority or an auto-teaching model. The end-to-end goal is known before Lesson 1: *a Core sends a typed SDK request to the Platform, the Platform makes a separately authorized decision, the reference Module responds, and the Core validates the receipt. Two Cores remain independently scoped; removing the Module withdraws its capability without rebooting the Platform.*

**Who can use this:** a human developer or **any authorized Core with an approved read-only repo/workspace and a sandboxed DEV tool runner**. An LLM can read this guide and use test results to improve its current work, but source reading does not change its trained weights, grant privileges, or create persistent learned skills by itself. Persistent progress/skills require a separate authorized, evidence-backed workflow.

## Final build (show the whole machine first)

```text
CORE A                   CORE B
build_ping()              build_ping()
    |                         |
    +-------------+-----------+
                  v
        PLATFORM TEST DOUBLE
      independently check session
      owner/SAFE is simulated only
      validate version, digest, time,
      target, generation and STOP
                  |
                  v
        REFERENCE MODULE
            reference.ping
                  |
             test-only result
                  v
        PLATFORM RESPONSE ENVELOPE
             reported/unverified
                  |
                  v
       CORE verifies reply binding
```

**Never equate the dummy Platform with production.** The real Platform must use OS-authenticated transport, enrollment, SAFE/STOP, signed packages, canonical writer fencing and verified worker receipts. The demo's `test_only_grant` is a deliberate *test double* and never a service API.

## Study method for a developer or Core

1. **Look at the end result.** Run the complete no-effect example. Record what you expected and observed. Do not start by rewriting everything.
2. **Learn one boundary.** Read only the listed SDK/source file and its smallest corresponding test. Summarize its responsibility and what it must never do.
3. **Run one test before editing.** Preserve the exact command, source SHA and output. Failed test = investigate, not a pass.
4. **Make one harmless experiment in a disposable branch/workspace.** Predict the change, run the test again, observe why it passed or failed, then revert or update a specifically authorized fixture.
5. **Prove negative behavior.** Requests from unauthorized, stale, spoofed or disconnected actors must fail closed.
6. **Checkpoint before advancing.** Pass the test and explain which component owns authority. A Core may submit a progress record, but must not mark itself production certified.
7. **Reassemble all three at the end.** Re-run the complete suite on the same exact commit; record genuine evidence and unresolved gaps.

If a lesson fails, inspect the test, interface contract and last edit; do not silently patch an unrelated source file. A permission refusal is expected behavior, not something to bypass. Work only on synthetic identities and disposable files.

## First run (read-only demo)

In a disposable checkout of the draft branch:

```powershell
python -m pip install -e . pytest
$env:PYTHONPATH = "src"
python -m examples.sdk_reference_system.try_it
python -m pytest -q test/test_sdk_reference_core_platform.py test/test_sdk_reference_module.py
```

The demo should report `succeeded_reported_unverified` for Core A, `denied` for Core B before its test grant, `succeeded_reported_unverified` after the test grant and `unavailable` after unplug. **These are expected results; confirm using actual test output before claiming they occurred.**

## Lessons and exact checkpoints

| Step | Learn and inspect | Build one piece, then prove it | Observable checkpoint |
| --- | --- | --- | --- |
| **0. The finish line** | [Full demo](try_it.py), [3-piece README](README.md) | Run `python -m examples.sdk_reference_system.try_it` and explain each of four outcomes | Same four states as the goal; no host modifications |
| **1. Common language** | [Wire helper](wire.py), `src/sofia/sdk/contracts.py` | Read `payload_digest` and versioned request/response contracts. Change the nonce in a sandbox, compare digest | `python -m pytest -q test/test_sdk_reference_core_platform.py::test_bounded_json_digests_never_grant_permission` |
| **2. Smallest module** | [Module](../sdk_reference_module/reference.py) `ReferenceModule.capability_registrations` | Identify one name, one input `nonce`, one output and `effect=none`; try an invalid nonce in tests | `python -m pytest -q test/test_sdk_reference_module.py::test_reference_module_is_bounded_and_only_declares_current_sdk` |
| **3. Platform owns the socket** | [Platform](../sdk_reference_platform/platform.py) `plug_reference_module`, `unplug_reference_module`, `dispatch` | Trace registration, Platform authorization, and removal. Unplug and show capability `unavailable` | `python -m pytest -q test/test_sdk_reference_core_platform.py::test_two_cores_are_isolated_and_module_unplug_does_not_close_them` |
| **4. Core builds a request** | [Core](../sdk_reference_core/core.py) `build_ping`, `read_ping` | Trace Core endpoint, request ID, payload digest, response correlation; Core must not import Platform | `python -m pytest -q test/test_sdk_reference_core_platform.py::test_wire_round_trip_and_forged_success_rejected_by_dummy_core` |
| **5. Two Cores, separate rights** | Platform `open_test_session`, `test_only_grant`, `test_only_revoke` | Run two synthetic Cores; deny one before its grant; show permissions do not transfer | `python -m pytest -q test/test_sdk_reference_core_platform.py::test_two_cores_are_isolated_and_module_unplug_does_not_close_them` |
| **6. Failure is part of the API** | Shared SDK envelopes; Platform `dispatch` | Attempt stale generation, changed payload, replay, expired deadline, STOP, disconnected session; never fabricate success | `python -m pytest -q test/test_sdk_reference_core_platform.py::test_caller_fields_do_not_impersonate_active_core_or_platform test/test_sdk_reference_core_platform.py::test_expiry_replay_future_time_stop_and_close_fail_closed` |
| **7. Hot-swap the Core** | Core endpoints and Platform sessions | Disconnect Core A, prove B still works, reconnect A generation 2 with new synthetic session | `python -m pytest -q test/test_sdk_reference_core_platform.py::test_core_replacement_keeps_platform_and_other_core_alive` |
| **8. Real lifecycle contracts** | `test/test_sdk_reference_module.py`, `platform/modules/lifecycle.py` | Verify disposable signed manifest and real `discover→approve→stage→activate→pause→resume→disable→remove` API | `python -m pytest -q test/test_sdk_reference_module.py::test_signed_reference_installs_activates_responds_and_unplugs` |
| **9. Settings and revision safety** | Module `settings_contract()`, `ModuleSettingsService` | Distinguish LIVE from COMPONENT_RESTART; verify a stale edit is rejected | `python -m pytest -q test/test_sdk_reference_module.py::test_reference_settings_live_pending_restart_and_stale_edit` |
| **10. Cross-language compatibility** | `src/sofia/sdk/contracts.py`, `rust/crates/sofia-contracts/src/lib.rs` | Locate Python/Rust protocol `1.0`; show that incompatible major versions are not admitted | `python -m pytest -q test/test_sdk_reference_module.py::test_protocol_negotiation_and_rust_python_sdk_version_parity` |
| **11. Capstone** | All three examples and tests | Explain every boundary, run full suite, produce evidence with exact SHA and failures; do not deploy | `python -m pytest -q test/test_sdk_reference_core_platform.py test/test_sdk_reference_module.py` |

### One optional hands-on exercise

In a **new disposable branch**, add a second **read-only**, bounded response field to the reference Module's `ping` response, then update the corresponding assertions. This tests how changes propagate from implementation to SDK consumers, conformance tests and documentation. The original golden fixture must stay unchanged until the PR and compatibility review are approved. Do not modify signed package identities, Platform authority or Core memory.

### What every checkpoint record should include

```text
lesson_id:    04-core-request
source_sha:   <actual commit SHA, not a guessed value>
read_files:   <exact referenced files>
expected:     <what the test should show>
observed:     <actual test summary and exit code>
negative:     <which denied/stale case was verified>
understood:   <one sentence: who owns authority?>
gaps:         <unknowns and failed commands>
next:         <only after evidence passes>
```

A Core should use this as **instructional retrieval + test evidence**, not as unverified permanent memory. Any saved reusable skill must cite code version, host and test results, survive independent review and be revocable if contracts change. Model weights do not update by reading this document.

## Beyond the textbook: production exercises that remain OPEN

The following are **not** achieved by this workbook and need independent disposable-host acceptance: real authenticated Core/Platform IPC and current enrollment, real worker process, durable STOP/revocation, signed Windows/Debian 12 installation, precise host resource limits, GUI/TUI hot-plug observation, Core crash recovery, asynchronous workload cancellation, actual SDK package release/automatic compatibility updates and tested rollback.

**Completion rule:** Passing Lessons 0–11 makes someone familiar with the **source-level SDK development contract**. It never implies Core/Platform/Module 1.0 production readiness or authorizes a live host action.
