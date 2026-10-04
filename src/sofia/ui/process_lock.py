"""Single tray ownership using RUN's shared OS-backed process lock."""
from sofia.run.process_lock import StateProcessLock


class TrayProcessAlreadyRunning(RuntimeError):
    pass


class TrayProcessLock(StateProcessLock):
    def __init__(self, state_path):
        super().__init__(
            state_path, resource="tray", owner_label="tray agent",
            duplicate_error=TrayProcessAlreadyRunning,
        )
