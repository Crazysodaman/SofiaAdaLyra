from enum import Enum


class RuntimeState(Enum):
    CREATED = "created"
    STARTING = "starting"
    READY = "ready"
    FAILED = "failed"
    STOPPED = "stopped"