import pytest

from sofia.ui.process_lock import TrayProcessAlreadyRunning, TrayProcessLock


def test_only_one_tray_agent_can_own_one_state_database(tmp_path):
    state = tmp_path / "sofia.db"
    state.touch()

    first = TrayProcessLock(state)
    second = TrayProcessLock(state)

    first.acquire()
    try:
        with pytest.raises(TrayProcessAlreadyRunning, match="another live Sofía tray agent"):
            second.acquire()
    finally:
        first.release()

    second.acquire()
    second.release()


def test_same_lock_object_cannot_be_acquired_twice(tmp_path):
    state = tmp_path / "sofia.db"
    state.touch()
    lock = TrayProcessLock(state)
    lock.acquire()
    try:
        with pytest.raises(RuntimeError, match="already acquired"):
            lock.acquire()
    finally:
        lock.release()
