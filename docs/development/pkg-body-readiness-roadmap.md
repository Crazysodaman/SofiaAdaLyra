# PKG-BODY | branch readiness roadmap

**2026-09-21 | draft PR #16 | baseline head `93f03928bdccc7b0e65e6f257aeb3a75b0a4ecda`.** Companion: `pkg-body-simulator-review.md` and original Gaia/BODY roadmap. A simulation is not a physical safety device.

## Prepared and verified in isolation

Stopped-by-default in-memory servo rig, bounded/atomic motion proposals, pulse limits, replay/revision rejection, read-only positions and simulated halt. **36 focused tests passed on equivalent isolated Linux code**, including a rerun after deleting an unused test import. No USB/serial driver, real 180°/360° servo calibration, feedback, battery control, real stop, SSC-32 connection or motion has been tested.

## Development and test gates

1. Pin source and inventory Gaia frame, 3-DOF leg/channel map, SSC-32 firmware/interface/baud, real servo inventory (positional versus continuous), measured pulse endpoints, supply/battery/BEC, joint direction, hardware limit switches/IMU and available command feedback. A continuous-rotation servo pulse is a *speed command*, not an angular position; do not assume position control from nominal pulse range.
2. Specify non-energizing simulator contracts: calibration units, per-servo types/limits, neutral mapping, gait/interpolation timing, communication timeout, stale/replayed commands, power budget, fault-latched state, and independent sensor confidence. Test collision/support stability in simulation without inventing physical sensor readings.
3. Design trusted hardware adapter **separately**, with explicit owner authorization, no generic text-to-servo command path, watchdog, bounded commands and device identity. A **physical independently wired emergency stop or power cutoff** must work when Python, serial or a model hangs. Simulated `stop_simulation` is never represented as hardware e-stop.
4. Run branch/Windows tests and robot simulator fault injection: stale source, conflicting command, overrange, unexpected restart, unknown feedback, serial disconnect, sustained command, stall and watchdog timeout; no motor power. Reconcile BODY with SAFE/NET scopes and independent kill authority.
5. Only with approved wiring/calibration and physical stop: supervised low-torque single-servo bench test, then one leg, support fixture, then full gait, measured current/heat and fail-stop. Record real measured limits, exact firmware and recoverability. No autonomous unattended walking before physical acceptance.

## Decisions at BODY review

Actual servo models and whether each is 180° positional or 360° continuous, link lengths/IK geometry, mounting order, voltage/current protection, real SSC-32 transport and deployment host, independent stop hardware, allowed motion envelope, whether physical Gaia integration is wanted at all. Existing Raspberry Pi is not assumed available.

**Exit:** synthetic offline tests only. Actual hardware, Windows checkout/full suite, independently proven stop, calibration, motion and deployment = NOT RUN. Do not connect, energize or merge on the basis of this roadmap.
