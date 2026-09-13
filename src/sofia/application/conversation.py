from collections.abc import Callable

from sofia.application.bootstrap import SofiaApplication
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveRole,
)


class ConversationLoop:
    """
    Interactive terminal conversation loop for Sofía.

    Owns terminal interaction only.
    Application and runtime remain responsible for
    lifecycle and cognition.
    """

    def __init__(
        self,
        application: SofiaApplication,
        input_function: Callable[[str], str] = input,
        output_function: Callable[[str], None] = print,
    ) -> None:
        self._application = application
        self._input = input_function
        self._output = output_function

    def run(self) -> None:
        """
        Start an interactive conversation session.

        The loop exits when the user enters an exit command
        or sends EOF.
        """

        self._application.start()

        try:
            while True:
                try:
                    user_input = self._input("You > ")
                except EOFError:
                    break

                user_input = user_input.strip()

                if not user_input:
                    continue

                if user_input.lower() in {
                    "exit",
                    "quit",
                }:
                    break

                request = CognitiveRequest(
                    messages=(
                        CognitiveMessage(
                            role=CognitiveRole.USER,
                            content=user_input,
                        ),
                    ),
                )

                response = self._application.runtime.respond(
                    request
                )

                self._output(f"Sofía > {response.content}")
        finally:
            self._application.shutdown()