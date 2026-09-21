# PKG-BODY: synthetic servo rig and hardware review gate

**Status:** headless simulation code/tests on a package branch, not merged, installed on Gaia, or capable of moving real hardware. The software stop in this module is **simulation only**, not a physical emergency stop or substitute for an independently enforceable hardware cutoff.

## Offline code

`ServoSpec` explicitly configures channel labels, synthetic pulse envelope, maximum per-step delta and initial position. `SyntheticServoRig` starts stopped, accepts bounded multi-channel simulation plans and revalidates before applying, invalidates plans across state revisions, halts on simulated stop and exposes read-only snapshots. No guessed real channel IDs, actual current position, torque, power, voltage or servo type are inferred. The fixtures use hypothetical `hip` and `thigh` labels and values, not calibrated Gaia channels.

**Test:** `PYTHONPATH=src python -m pytest -q test/test_body_simulator.py`. Equivalent staged code passed **36 focused tests on Linux Python 3.13.5 / pytest 9.0.2**. The branch checkout, actual Windows suite, full repo tests and real hardware tests are **not run**.

## Questions and checks at BODY review

- Obtain authoritative Gaia 2.0 channel-to-joint wiring, per-servo model and continuous-versus-position rotation behavior, direction, calibrated pulse min/max/neutral, power supply, current/thermal budgets, torque and SSC-32 communication details. The fixture's nominal 500–2500 µs envelope is **not approved calibration**.
- Define independent physical emergency stop, watchdog, loss-of-signal fail-safe, boot power state, mechanical collision limits, load/thermal conditions and service operator; a Python process or model must not release a physical stop.
- Decide real actuator and sensor adapters only after SAFE/BODY authority checks and interlock hardware are inspected. Reject replay/stale commands at the real executor, not just simulation. Support no-device and fail-closed disconnected states.
- Run staged dry-run → no-load servo validation → constrained supervised movement with observed timestamps/measurements. Establish independent stop and failure recovery before autonomous gait. The existing Gaia project remains separate until explicit integration authorization.

**No hardware authority, production DB, canonical identity/Constitution, bot or internet search in this branch.** Releases remain CORE → INTERACT → MEM → Sparks-only Discord → verified RUN → separately authorized search.
