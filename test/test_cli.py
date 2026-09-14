from pathlib import Path

from sofia.config.model import (
    ProviderConfiguration,
    SofiaConfiguration,
)
from sofia.runtime.model import RuntimeState
from sofia.__main__ import main


PROJECT_ROOT = Path(__file__).parent.parent

CONSTITUTION_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "constitution"
    / "constitution.md"
)

HASH_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "constitution"
    / "constitution.sha256"
)

IDENTITY_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "identity"
    / "identity.json"
)

AVATAR_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "data"
    / "avatar.json"
)


def create_configuration(
    tmp_path: Path,
) -> SofiaConfiguration:
    personality_path = (
        tmp_path
        / "personality.json"
    )

    personality_path.write_text(
        """
{
    "name": "Sofía",
    "traits": [
        "rigorous",
        "analytical",
        "curious"
    ],
    "communication_style": "Clear and analytical."
}
""".strip(),
        encoding="utf-8",
    )

    return SofiaConfiguration(
        constitution_path=CONSTITUTION_PATH,
        constitution_hash_path=HASH_PATH,
        identity_path=IDENTITY_PATH,
        personality_path=personality_path,
        avatar_path=AVATAR_PATH,
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(
            provider="test",
            model="cli-test",
        ),
        filesystem_root=PROJECT_ROOT,
    )


def test_cli_runs_conversation_and_exits(
    tmp_path: Path,
):
    configuration = create_configuration(
        tmp_path
    )

    inputs = iter(
        [
            "Hello, Sofía.",
            "exit",
        ]
    )

    outputs: list[str] = []

    result = main(
        configuration=configuration,
        input_function=lambda _: next(inputs),
        output_function=outputs.append,
    )

    assert result == 0
    assert any(
        "Test cognitive response."
        in output
        for output in outputs
    )


def test_cli_exits_cleanly_on_eof(
    tmp_path: Path,
):
    configuration = create_configuration(
        tmp_path
    )

    def raise_eof(_: str) -> str:
        raise EOFError

    outputs: list[str] = []

    result = main(
        configuration=configuration,
        input_function=raise_eof,
        output_function=outputs.append,
    )

    assert result == 0
    assert outputs == []


def test_cli_configuration_failure_returns_error(
    tmp_path: Path,
):
    configuration = SofiaConfiguration(
        constitution_path=tmp_path / "missing.md",
        constitution_hash_path=tmp_path / "missing.sha256",
        identity_path=tmp_path / "missing.json",
        personality_path=tmp_path / "missing-personality.json",
        avatar_path=tmp_path / "missing-avatar.json",
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(
            provider="test",
            model="cli-test",
        ),
        filesystem_root=tmp_path,
    )

    outputs: list[str] = []

    result = main(
        configuration=configuration,
        output_function=outputs.append,
    )

    assert result == 1
    assert len(outputs) == 1
    assert "failed" in outputs[0].lower()