from dataclasses import FrozenInstanceError
import pytest
from sofia.body import MotionPlan, ServoSpec, SimulatedStop, SyntheticServoRig


def spec(channel="hip", **kw):
    data = dict(channel=channel, min_pulse_us=1000, max_pulse_us=2000,
                max_step_us=250, initial_pulse_us=1500)
    data.update(kw)
    return ServoSpec(**data)


def rig():
    return SyntheticServoRig((spec(), spec("thigh")))


def test_defaults_stopped_and_positions_are_read_only():
    r = rig()
    assert r.stopped and r.positions == {"hip": 1500, "thigh": 1500}
    with pytest.raises(TypeError):
        r.positions["hip"] = 2000


def test_stopped_rig_refuses_proposals():
    with pytest.raises(SimulatedStop):
        rig().propose({"hip": 1501})


def test_initial_start_is_only_simulation():
    r = rig()
    r.start_simulation()
    assert not r.stopped and r.revision == 1


def test_apply_atomic_two_channels():
    r = rig(); r.start_simulation()
    p = r.propose({"thigh": 1400, "hip": 1600})
    assert p.targets == (("hip", 1600), ("thigh", 1400))
    assert r.positions["hip"] == 1500
    r.apply_simulation(p)
    assert r.positions == {"hip": 1600, "thigh": 1400}


def test_stale_replay_denied_without_moving():
    r = rig(); r.start_simulation(); p = r.propose({"hip": 1510}); r.apply_simulation(p)
    with pytest.raises(ValueError, match="stale"):
        r.apply_simulation(p)
    assert r.positions["hip"] == 1510


def test_stop_invalidates_outstanding_plan():
    r = rig(); r.start_simulation(); p = r.propose({"hip": 1510}); r.stop_simulation()
    with pytest.raises(SimulatedStop):
        r.apply_simulation(p)
    assert r.positions["hip"] == 1500


def test_restart_resets_simulated_positions_and_revision():
    r = rig(); r.start_simulation(); r.apply_simulation(r.propose({"hip": 1600})); r.stop_simulation()
    r.start_simulation()
    assert r.positions["hip"] == 1500
    assert r.revision == 4


@pytest.mark.parametrize("bad", [dict(channel=""), dict(channel=" "), dict(min_pulse_us=400), dict(max_pulse_us=2501), dict(max_pulse_us=1000), dict(max_step_us=0), dict(max_step_us=1001), dict(initial_pulse_us=999), dict(initial_pulse_us=2001)])
def test_invalid_servo_spec(bad):
    with pytest.raises(ValueError):
        spec(**bad)


@pytest.mark.parametrize("bad", [dict(max_step_us=True), dict(min_pulse_us=1000.5), dict(initial_pulse_us="1500")])
def test_noninteger_spec(bad):
    with pytest.raises(TypeError):
        spec(**bad)


def test_duplicate_channel_denied():
    with pytest.raises(ValueError, match="duplicate"):
        SyntheticServoRig((spec(), spec()))


def test_empty_rig_denied():
    with pytest.raises(ValueError):
        SyntheticServoRig(())


@pytest.mark.parametrize("targets,error", [({}, ValueError), ({"unknown": 1500}, ValueError), ({"hip": 999}, ValueError), ({"hip": 2001}, ValueError), ({"hip": 1751}, ValueError), ({"hip": 1500.0}, TypeError), ({"hip": True}, TypeError), ({4: 1500}, ValueError)])
def test_bad_targets_never_move(targets, error):
    r = rig(); r.start_simulation()
    with pytest.raises(error):
        r.propose(targets)
    assert r.positions == {"hip": 1500, "thigh": 1500}


def test_mixed_valid_and_invalid_targets_are_atomic():
    r = rig(); r.start_simulation()
    with pytest.raises(ValueError):
        r.propose({"hip": 1510, "thigh": 1800})
    assert r.positions["hip"] == 1500


def test_forged_motion_plan_cannot_skip_validation():
    r = rig(); r.start_simulation()
    with pytest.raises(ValueError):
        r.apply_simulation(MotionPlan(r.revision, (("hip", 1800),)))
    assert r.positions["hip"] == 1500


def test_duplicate_forged_target_denied():
    r = rig(); r.start_simulation()
    with pytest.raises(ValueError):
        r.apply_simulation(MotionPlan(r.revision, (("hip", 1501), ("hip", 1501))))


def test_unsorted_forged_target_denied():
    r = rig(); r.start_simulation()
    with pytest.raises(ValueError):
        r.apply_simulation(MotionPlan(r.revision, (("thigh", 1501), ("hip", 1501))))


def test_forged_unknown_channel_denied():
    r = rig(); r.start_simulation()
    with pytest.raises(ValueError):
        r.apply_simulation(MotionPlan(r.revision, (("fake", 1501),)))


def test_plan_immutable():
    r = rig(); r.start_simulation(); p = r.propose({"hip": 1501})
    with pytest.raises(FrozenInstanceError):
        p.revision = 99


def test_no_hardware_io_import_or_serial_api():
    import inspect
    from sofia.body import simulator
    source = inspect.getsource(simulator)
    assert "import serial" not in source and "subprocess" not in source
    assert not hasattr(SyntheticServoRig, "connect") and not hasattr(SyntheticServoRig, "send")
