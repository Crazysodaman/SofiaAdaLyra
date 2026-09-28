from datetime import datetime, timedelta, timezone

import pytest

from sofia.body.controller import (
    BodyController,
    BodyExecutionError,
    MotionApproval,
    ServoBackend,
)
from sofia.body.model import MotionKind, MotionRequest, ServoCommand
from sofia.body.safety import EmergencyStopEvidence, EmergencyStopMonitor
from sofia.body.ssc32 import SSC32Backend


NOW = datetime(2026, 9, 28, 18, 0, tzinfo=timezone.utc)


class FakeBackend(ServoBackend):
    def __init__(self):
        self.executed = []
        self.stop_count = 0

    def execute(self, request):
        self.executed.append(request)

    def stop_all(self):
        self.stop_count += 1


class FakeStop(EmergencyStopMonitor):
    def __init__(self, evidence):
        self.evidence = evidence

    def observe(self):
        return self.evidence


def _request(kind=MotionKind.POSE):
    commands = () if kind is MotionKind.STOP else (
        ServoCommand(channel=1, pulse_us=1500, move_time_ms=250),
    )
    return MotionRequest("motion-1", kind, commands)


def _approval():
    return MotionApproval(
        "approval-1",
        "motion-1",
        "Sparks",
        NOW + timedelta(minutes=1),
    )


def _evidence(*, asserted=False, verified=True, observed_at=NOW):
    return EmergencyStopEvidence(
        asserted=asserted,
        hardware_verified=verified,
        observed_at=observed_at,
        source="hardware:test",
    )


def test_body_motion_requires_fresh_verified_independent_estop():
    backend = FakeBackend()
    controller = BodyController(
        backend=backend,
        emergency_stop=FakeStop(_evidence()),
    )

    controller.execute(_request(), _approval(), now=NOW)

    assert len(backend.executed) == 1
    assert backend.stop_count == 0


@pytest.mark.parametrize(
    ("evidence", "message"),
    [
        (_evidence(verified=False), "not verified"),
        (_evidence(observed_at=NOW - timedelta(seconds=2)), "stale"),
    ],
)
def test_body_motion_fails_closed_when_estop_evidence_is_unsafe(
    evidence,
    message,
):
    backend = FakeBackend()
    controller = BodyController(
        backend=backend,
        emergency_stop=FakeStop(evidence),
        max_estop_age_seconds=1.0,
    )

    with pytest.raises(BodyExecutionError, match=message):
        controller.execute(_request(), _approval(), now=NOW)

    assert backend.executed == []


def test_asserted_estop_stops_backend_and_refuses_motion():
    backend = FakeBackend()
    controller = BodyController(
        backend=backend,
        emergency_stop=FakeStop(_evidence(asserted=True)),
    )

    with pytest.raises(BodyExecutionError, match="asserted"):
        controller.execute(_request(), _approval(), now=NOW)

    assert backend.stop_count == 1
    assert backend.executed == []


def test_body_motion_approval_is_exact_and_sparks_only():
    backend = FakeBackend()
    controller = BodyController(
        backend=backend,
        emergency_stop=FakeStop(_evidence()),
    )

    wrong_person = MotionApproval(
        "approval-2",
        "motion-1",
        "someone-else",
        NOW + timedelta(minutes=1),
    )
    with pytest.raises(PermissionError, match="Sparks"):
        controller.execute(_request(), wrong_person, now=NOW)

    wrong_request = MotionApproval(
        "approval-3",
        "different-motion",
        "Sparks",
        NOW + timedelta(minutes=1),
    )
    with pytest.raises(PermissionError, match="another request"):
        controller.execute(_request(), wrong_request, now=NOW)


class FakeSerial:
    def __init__(self):
        self.writes = []

    def write(self, payload):
        self.writes.append(payload)
        return len(payload)


def test_ssc32_backend_emits_only_structured_motion_frame():
    serial = FakeSerial()
    backend = SSC32Backend(serial)
    request = MotionRequest(
        "motion-frame",
        MotionKind.POSE,
        (
            ServoCommand(0, 1250, 200),
            ServoCommand(3, 1750, 350),
        ),
    )

    backend.execute(request)

    assert serial.writes == [b"#0 P1250 #3 P1750 T350\r"]


def test_ssc32_software_stop_never_claims_to_replace_hardware_estop():
    backend = SSC32Backend(FakeSerial())

    with pytest.raises(RuntimeError, match="cannot substitute"):
        backend.stop_all()
