from __future__ import annotations

from threading import Lock

from sofia.body.controller import ServoBackend
from sofia.body.model import MotionRequest


class SSC32Backend(ServoBackend):
    """Narrow SSC-32 serial backend. No arbitrary serial text is accepted."""

    def __init__(self,serial_port)->None:
        if not hasattr(serial_port,"write"):
            raise TypeError("serial_port must expose write(bytes)")
        self.serial=serial_port
        self._lock=Lock()

    @staticmethod
    def _frame(request:MotionRequest)->bytes:
        parts=[
            f"#{item.channel} P{item.pulse_us}"
            for item in request.commands
        ]
        move=max(item.move_time_ms for item in request.commands)
        return (" ".join(parts)+f" T{move}\r").encode("ascii")

    def execute(self,request:MotionRequest)->None:
        if not isinstance(request,MotionRequest):
            raise TypeError("request must be MotionRequest")
        frame=self._frame(request)
        with self._lock:
            written=self.serial.write(frame)
        if written is not None and written!=len(frame):
            raise RuntimeError("SSC-32 serial write was incomplete")

    def stop_all(self)->None:
        # SSC-32 pulse output has no universal hardware E-stop command.
        # Physical power removal / controller-side stop must remain independent.
        raise RuntimeError(
            "SSC-32 software stop cannot substitute for independent hardware E-stop"
        )
