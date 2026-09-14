from dataclasses import dataclass


@dataclass(frozen=True)
class Authority:
    """
    Immutable description of what Sofía is authorized to do
    during a cognitive operation.
    """

    can_respond: bool = True
    can_propose_actions: bool = True
    can_execute_actions: bool = False
    can_inspect_filesystem: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.can_respond, bool):
            raise TypeError(
                "Authority can_respond must be a bool."
            )

        if not isinstance(self.can_propose_actions, bool):
            raise TypeError(
                "Authority can_propose_actions must be a bool."
            )

        if not isinstance(self.can_execute_actions, bool):
            raise TypeError(
                "Authority can_execute_actions must be a bool."
            )

        if not isinstance(self.can_inspect_filesystem, bool):
            raise TypeError(
                "Authority can_inspect_filesystem must be a bool."
            )