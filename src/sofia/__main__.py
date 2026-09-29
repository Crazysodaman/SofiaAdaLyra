from collections.abc import Callable, Sequence
import sys

from sofia.application import (
    ConversationLoop,
    SofiaApplication,
    SofiaApplicationError,
)
from sofia.config import (
    SofiaConfiguration,
    create_default_configuration,
)


def _run_terminal(
    configuration: SofiaConfiguration | None,
    *,
    input_function: Callable[[str], str],
    output_function: Callable[[str], None],
) -> int:
    if configuration is None:
        configuration = create_default_configuration()

    try:
        application = SofiaApplication(configuration)
        loop = ConversationLoop(
            application=application,
            input_function=input_function,
            output_function=output_function,
        )
        loop.run()
    except SofiaApplicationError as exc:
        output_function(f"Sofía failed to start or operate: {exc}")
        return 1
    except KeyboardInterrupt:
        output_function("\nSofía > Shutdown requested.")
        return 0
    return 0


def main(
    configuration: SofiaConfiguration | None = None,
    input_function: Callable[[str], str] = input,
    output_function: Callable[[str], None] = print,
    argv: Sequence[str] | None = None,
) -> int:
    """Launch the production desktop by default.

    The historical terminal client remains available explicitly through
    python -m sofia --cli. Keeping the desktop as the default makes the
    normal production entrypoint match the accepted PKG-UI surface instead of
    silently falling back to a different client.
    """

    arguments = tuple(sys.argv[1:] if argv is None else argv)

    if arguments in (("--cli",), ("--terminal",)):
        return _run_terminal(
            configuration,
            input_function=input_function,
            output_function=output_function,
        )

    if arguments:
        output_function(
            "Usage: python -m sofia [--cli]\n"
            "Run without arguments for the desktop workbench."
        )
        return 2

    try:
        from sofia.ui.desktop import run_desktop
        from sofia.ui.tray_launcher import ensure_tray_agent

        desktop_configuration = (
            configuration
            if configuration is not None
            else create_default_configuration()
        )
        try:
            ensure_tray_agent(desktop_configuration)
        except Exception as exc:
            output_function(
                "Sofía tray failed to start: "
                f"{type(exc).__name__}: {exc}"
            )

        return run_desktop(
            configuration=desktop_configuration
        )
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        output_function(
            f"Sofía desktop failed to start or operate: "
            f"{type(exc).__name__}: {exc}"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
