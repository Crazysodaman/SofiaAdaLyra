"""Single Discord ownership using RUN's shared OS-backed process lock."""
from sofia.run.process_lock import StateProcessLock


class DiscordProcessLock(StateProcessLock):
    def __init__(self, state_path):
        super().__init__(
            state_path, resource="discord", owner_label="Discord process",
        )
