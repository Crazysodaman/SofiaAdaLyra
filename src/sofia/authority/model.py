from dataclasses import dataclass


@dataclass(frozen=True)
class Authority:
    """
    Immutable description of what Sofía is authorized to do
    during a cognitive operation.

    Authority controls both whether an operation may proceed and
    which capabilities may be exposed to the cognitive engine.

    Capability exposure is intentionally conservative: a capability
    is not considered authorized unless it is explicitly represented
    by an authority field or by the allowed_capabilities collection.
    """

    can_respond: bool = True
    can_propose_actions: bool = True
    can_execute_actions: bool = False
    can_inspect_filesystem: bool = False
    allowed_capabilities: tuple[str, ...] = ()

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

        if not isinstance(self.allowed_capabilities, tuple):
            raise TypeError(
                "Authority allowed_capabilities must be a tuple."
            )

        for capability in self.allowed_capabilities:
            if not isinstance(capability, str):
                raise TypeError(
                    "Authority allowed_capabilities must contain strings."
                )

            if not capability.strip():
                raise ValueError(
                    "Authority allowed_capabilities must not contain "
                    "empty capability names."
                )

        if len(set(self.allowed_capabilities)) != len(
            self.allowed_capabilities
        ):
            raise ValueError(
                "Authority allowed_capabilities must not contain "
                "duplicate capability names."
            )

    def can_use_capability(
        self,
        capability_name: str,
    ) -> bool:
        """
        Return whether a capability may be exposed to the cognitive
        engine for this authority.

        This method answers an exposure question only. It does not
        execute a capability and does not replace the capability
        system's execution-time authorization checks.
        """

        if not isinstance(capability_name, str):
            raise TypeError(
                "Authority capability_name must be a string."
            )

        normalized = capability_name.strip()

        if not normalized:
            raise ValueError(
                "Authority capability_name must not be empty."
            )

        if normalized in self.allowed_capabilities:
            return True

        if (
            normalized == "filesystem.inspect"
            and self.can_inspect_filesystem
        ):
            return True

        return False