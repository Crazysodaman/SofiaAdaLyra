"""CORE-001 disposable readiness generation and bootstrap monitoring negatives.

Uses fake application and fake generation store. No canonical SQLite or
production service is accessed.
"""
import inspect
import json

import pytest

from sofia.platform.run import runtime_child, runtime_service


TOKEN = "a" * 32


class _FakeApplication:
    def __init__(self, stop_file=None):
        self.started = False
        self.stopped = False
        self.stop_file = stop_file

    def start(self):
        self.started = True
        if self.stop_file is not None:
            self.stop_file.touch()

    def shutdown(self):
        self.stopped = True


class _EpochStore:
    def __init__(self, sequence):
        self.sequence = list(sequence)
        self.last = self.sequence[-1] if self.sequence else None

    def current_generation(self):
        if self.sequence:
            self.last = self.sequence.pop(0)
        return self.last


def _run_disposable(
    tmp_path, monkeypatch, *, actual_epochs, expected_epoch=7, stop_after_start=True,
):
    path = tmp_path / "synthetic-not-real.db"
    path.touch()
    ready = tmp_path / "synthetic.ready.json"
    stop = tmp_path / "synthetic.stop"
    app = _FakeApplication(stop if stop_after_start else None)
    store = _EpochStore(actual_epochs)
    emitted = []
    monkeypatch.setattr(runtime_child, "SofiaApplication", lambda config: app)
    monkeypatch.setattr(
        runtime_child, "create_production_configuration", lambda **kw: object(),
    )
    def require_fake_authority(state_path, *, expected_epoch):
        if expected_epoch != store.current_generation():
            raise PermissionError("generation changed; denying stale runtime")
    monkeypatch.setattr(
        runtime_child, "require_local_runtime_authority", require_fake_authority,
    )
    monkeypatch.setattr(
        runtime_child, "atomic_write_text",
        lambda path, content: emitted.append(json.loads(content)),
    )
    monkeypatch.setattr(runtime_child.time, "sleep", lambda seconds: None)
    return app, emitted, dict(
        state_path=path, ready_file=ready, stop_file=stop,
        start_token=TOKEN, expected_generation_epoch=expected_epoch,
        poll_seconds=0.01,
    )


def test_core001_child_emits_launch_and_generation_bound_readiness(
    tmp_path, monkeypatch,
):
    app, receipts, args = _run_disposable(
        tmp_path, monkeypatch, actual_epochs=[7, 7],
    )
    runtime_child.run_child(**args)
    assert app.started and app.stopped
    assert len(receipts) == 1
    assert receipts[0]["start_token"] == TOKEN
    assert receipts[0]["generation_epoch"] == 7
    assert receipts[0]["state_path"] == str(args["state_path"].resolve())
    assert type(receipts[0]["pid"]) is int


def test_core001_child_denies_wrong_generation_before_application_start(
    tmp_path, monkeypatch,
):
    app, receipts, args = _run_disposable(
        tmp_path, monkeypatch, actual_epochs=[8],
    )
    with pytest.raises(PermissionError, match="generation changed"):
        runtime_child.run_child(**args)
    assert not app.started
    assert not receipts


def test_core001_child_denies_generation_changed_during_boot(
    tmp_path, monkeypatch,
):
    app, receipts, args = _run_disposable(
        tmp_path, monkeypatch, actual_epochs=[7, 8],
    )
    with pytest.raises(PermissionError, match="generation changed"):
        runtime_child.run_child(**args)
    assert app.started and app.stopped
    assert not receipts


def test_core001_child_denies_generation_changed_while_running(
    tmp_path, monkeypatch,
):
    app, receipts, args = _run_disposable(
        tmp_path, monkeypatch,
        actual_epochs=[7, 7, 8], stop_after_start=False,
    )
    with pytest.raises(PermissionError, match="generation changed"):
        runtime_child.run_child(**args)
    assert app.started and app.stopped
    assert len(receipts) == 1


@pytest.mark.parametrize("token", ["", "not-a-uuid", "x" * 32, "f" * 31])
def test_core001_child_refuses_invalid_launch_tokens(tmp_path, token):
    path = tmp_path / "disposable.db"
    path.touch()
    with pytest.raises(ValueError, match="start_token"):
        runtime_child.run_child(
            state_path=path, ready_file=tmp_path / "ready",
            stop_file=tmp_path / "stop", start_token=token,
        )


def test_core001_child_refuses_bootstrap_without_writer_generation(
    tmp_path, monkeypatch,
):
    app, receipts, args = _run_disposable(
        tmp_path, monkeypatch, actual_epochs=[], expected_epoch=None,
    )
    with pytest.raises(PermissionError, match="positive generation"):
        runtime_child.run_child(**args)
    assert not app.started
    assert not receipts


def test_core001_bootstrap_monitor_reports_crash_without_false_running():
    class DeadChild:
        def running(self):
            return False

    with pytest.raises(RuntimeError, match="bootstrap.*exited unexpectedly"):
        runtime_service.assert_runtime_child_alive(DeadChild(), phase="bootstrap")


def test_core001_both_service_loops_check_child_alive():
    source = inspect.getsource(runtime_service)
    assert 'assert_runtime_child_alive(child, phase="active")' in source
    assert 'assert_runtime_child_alive(child, phase="bootstrap")' in source

def test_core001_duplicate_child_process_lock_denied_before_start(
    tmp_path, monkeypatch,
):
    from sofia.platform.run.process_lock import StateProcessLock

    app, receipts, args = _run_disposable(
        tmp_path, monkeypatch, actual_epochs=[7],
    )
    with StateProcessLock(
        args["state_path"], resource="core-runtime",
        owner_label="Core runtime child",
    ):
        with pytest.raises(RuntimeError, match="already owns this state"):
            runtime_child.run_child(**args)
    assert not app.started
    assert not receipts
