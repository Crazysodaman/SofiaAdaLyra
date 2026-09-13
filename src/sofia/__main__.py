from collections.abc import Callable

from sofia.application import (
    ConversationLoop,
    SofiaApplication,
    SofiaApplicationError,
)
from sofia.config import (
    SofiaConfiguration,
    create_default_configuration,
)


def main(
    configuration: SofiaConfiguration | None = None,
    input_function: Callable[[str], str] = input,
    output_function: Callable[[str], None] = print,
) -> int:
    """
    Run Sofía's interactive terminal application.

    Configuration and terminal I/O are injectable so the application
    boundary remains independently testable.
    """

    if configuration is None:
        configuration = create_default_configuration()

    application = SofiaApplication(
        configuration
    )

    loop = ConversationLoop(
        application=application,
        input_function=input_function,
        output_function=output_function,
    )

    try:
        loop.run()

    except SofiaApplicationError as exc:
        output_function(
            f"Sofía failed to start or operate: {exc}"
        )
        return 1

    except KeyboardInterrupt:
        output_function(
            "\nSofía > Shutdown requested."
        )
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())