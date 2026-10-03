from pathlib import Path

from sofia.run import windows_acceptance


class Status:
    def __init__(self, valid=True):
        self.valid = valid


class FakeUtil:
    def __init__(self):
        self.stopped = []
        self.started = []

    def StopService(self, name):
        self.stopped.append(name)

    def StartService(self, name):
        self.started.append(name)


def state_file(tmp_path: Path) -> Path:
    path = tmp_path / "sofia.db"
    path.write_bytes(b"db")
    return path


def test_acceptance_requires_valid_running_services(
    monkeypatch,
    tmp_path,
):
    state = state_file(tmp_path)
    monkeypatch.setattr(
        windows_acceptance.service_admin,
        "validate_services",
        lambda state_path: (Status(), Status()),
    )
    monkeypatch.setattr(
        windows_acceptance,
        "_running",
        lambda _name: True,
    )

    result = windows_acceptance.accept_runtime_services(
        state_path=state,
    )

    assert result.accepted is True
    assert result.recovery_exercised is False


def test_watchdog_recovery_exercise_requires_runtime_return(
    monkeypatch,
    tmp_path,
):
    state = state_file(tmp_path)
    util = FakeUtil()
    monkeypatch.setattr(
        windows_acceptance.service_admin,
        "validate_services",
        lambda state_path: (Status(), Status()),
    )
    monkeypatch.setattr(
        windows_acceptance.service_admin,
        "_require_windows",
        lambda: (object(), util),
    )
    monkeypatch.setattr(
        windows_acceptance,
        "_running",
        lambda _name: True,
    )
    monkeypatch.setattr(
        windows_acceptance,
        "_wait_running",
        lambda _name, timeout_seconds: True,
    )

    result = windows_acceptance.accept_runtime_services(
        state_path=state,
        exercise_watchdog_recovery=True,
    )

    assert result.accepted is True
    assert result.recovery_succeeded is True
    assert util.stopped == [
        windows_acceptance.RUNTIME_SERVICE.name
    ]
