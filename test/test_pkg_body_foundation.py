import pytest

from sofia.package_foundations.body import MotionProposal


def test_default_motion_proposal_does_not_pass_gate():
    assert not MotionProposal('hip-1', 1500, 1200, 1800).eligible_for_independent_hardware_gate


def test_out_of_calibration_or_emergency_stop_denies():
    assert not MotionProposal('hip-1', 1900, 1200, 1800, True, True, False).eligible_for_independent_hardware_gate
    assert not MotionProposal('hip-1', 1500, 1200, 1800, True, True, True).eligible_for_independent_hardware_gate


def test_all_prerequisites_only_make_proposal_eligible():
    assert MotionProposal('hip-1', 1500, 1200, 1800, True, True, False).eligible_for_independent_hardware_gate


def test_invalid_calibration_rejected():
    with pytest.raises(ValueError):
        MotionProposal('hip-1', 1500, 1800, 1200)
