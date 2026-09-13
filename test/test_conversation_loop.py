from pathlib import Path

from sofia.application import ConversationLoop, SofiaApplication
from sofia.cognition.model import CognitiveResponse
from sofia.config.model import ProviderConfiguration, SofiaConfiguration


CONSTITUTION_PATH = (
    Path(__file__).parent.parent
    / "src"
    / "sofia"
    / "constitution"
    / "constitution.md"
)

HASH_PATH = (
    Path(__file__).parent.parent
    / "src"
    / "sofia"
    / "constitution"
    / "constitution.sha256"
)

IDENTITY_PATH = (
    Path(__file__).parent.parent
    / "src"
    / "sofia"
    / "identity"
    / "identity.json"
)

AVATAR_PATH = (
    Path(__file__).parent.parent
    / "src"
    / "sofia"
    / "data"
    / "avatar.json"
)


def create_application(
    personality_path: Path,
    state_path: Path,
) -> SofiaApplication:
    configuration = SofiaConfiguration(
        constitution_path=str(CONSTITUTION_PATH),
        constitution_hash_path=str(HASH_PATH),
        identity_path=str(IDENTITY_PATH),
        personality_path=str(personality_path),
        avatar_path=str(AVATAR_PATH),
        state_path=str(state_path),
        provider=ProviderConfiguration(
            provider="test",
            model="test",
        ),
    )

    return SofiaApplication(configuration)


def create_personality(
    tmp_path: Path,
) -> Path:
    path = tmp_path / "personality.json"

    path.write_text(
        """
{
    "name": "Sofía",
    "traits": [
        "rigorous",
        "curious",
        "direct"
    ],
    "communication_style": "Clear, direct, and analytical."
}
""".strip(),
        encoding="utf-8",
    )

    return path


def test_conversation_loop_processes_user_input(
    tmp_path: Path,
):
    application = create_application(
        create_personality(tmp_path),
        tmp_path / "sofia.db",
    )

    inputs = iter(
        [
            "Hello, Sofía.",
            "exit",
        ]
    )

    outputs: list[str] = []

    loop = ConversationLoop(
        application=application,
        input_function=lambda _: next(inputs),
        output_function=outputs.append,
    )

    loop.run()

    assert outputs


def test_conversation_loop_ignores_empty_input(
    tmp_path: Path,
):
    application = create_application(
        create_personality(tmp_path),
        tmp_path / "sofia.db",
    )

    inputs = iter(
        [
            "",
            "   ",
            "Hello, Sofía.",
            "quit",
        ]
    )

    outputs: list[str] = []

    loop = ConversationLoop(
        application=application,
        input_function=lambda _: next(inputs),
        output_function=outputs.append,
    )

    loop.run()

    assert len(outputs) == 1


def test_conversation_loop_exits_on_eof(
    tmp_path: Path,
):
    application = create_application(
        create_personality(tmp_path),
        tmp_path / "sofia.db",
    )

    def raise_eof(_: str) -> str:
        raise EOFError

    loop = ConversationLoop(
        application=application,
        input_function=raise_eof,
        output_function=lambda _: None,
    )

    loop.run()

    assert application.runtime.state.value == "stopped"