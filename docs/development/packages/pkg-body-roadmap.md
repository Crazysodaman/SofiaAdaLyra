# PKG-BODY | Gaia robotics and safe embodiment

**Branch:** `feature/pkg-body-foundation` from `main` SHA `2141879`. **Status:** motion-proposal validation only. There is NO Sofía-to-Gaia connection, serial write, hardware command, power control or unattended robot job.

## Target and constraints
A separately authorized, supervised bridge may eventually connect Sofía's logical action proposals to Gaia 2.0's SSC-32 and verified sensors. Gaia's existing 3-DOF hexapod, mixed servo types and unfinished hardware calibration require a per-joint map, independent electrical stop and bench evidence. A fictional pat, virtual-lab event, avatar animation or LLM description never grants real motor authority.

## Slices
1. **B0 hardware inventory:** inspect *actual* servo models, torque, limits, continuous-rotation versus position semantics, battery/regulator current, fuse, wiring and controller firmware/baud. Treat stored design dimensions as reported until measured.
2. **B1 hardware abstraction:** versioned joint IDs and direction/inversion, calibration and pulse bounds, per-joint speed and interlock models; physically separate always-on controller from LLM process.
3. **B2 command proposal gate:** source-authenticated actor and target, explicit motion authorization, verified robot-ready state, operator-presence policy and independent E-stop. The new `src/sofia/package_foundations/body.py` is a **non-executing, caller-claim-based** eligibility prototype, not an authoritative or sufficient safety check.
4. **B3 sensors:** typed timestamps, confidence and calibration for IMU/sonar/touch/distance; missing data stays unknown. A servo pulse command is not position feedback.
5. **B4 gait simulation and bench:** model 3-DOF geometry, collision/stability/power limits and regression fixtures; test one unloaded servo under supervision before multi-leg walking.
6. **B5 physical bridge:** a separate host-enforced executor with heartbeat, mechanical/electrical stop, scope/expiry, command acknowledgment, current/temperature monitoring if instrumented, bounded timeout and safe recovery. No blind retry after uncertain movement.
7. **B6 observed integration:** independently verify sensor evidence, actuator motion, emergency-stop latency, shutdown/connection loss and human override.

## Verification and release
Run `python -m pytest -q -x test/test_pkg_body_foundation.py`, then calibration failure, continuous-servo rejection for position commands, stale sensor, power limits, firmware mismatch, unauthorized actor, serial loss and E-stop race tests. Simulated passes cannot establish real joint safety. Require physical bench plan, supervisor, inspected electrical protection, audited results and separate operator deployment permission before hardware trials. Dependencies: SAFE grants, NET transport, ACT proposal gating, UI/INTERACT semantics only for representation, VERIFY hardware tier. Do not auto-start anything on Artemis or Gaia or assume a Raspberry Pi remains dedicated to the robot.
