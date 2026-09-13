from pathlib import Path

from sofia.application import ConversationLoop, SofiaApplication
from sofia.config.model import (
    ProviderConfiguration,
    SofiaConfiguration,
)


PROJECT_ROOT = Path(__file__).resolve().parent

CONSTITUTION_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "constitution"
    / "constitution.md"
)

CONSTITUTION_HASH_PATH = (
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

PERSONALITY_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "personality"
    / "personality.json"
)


def create_configuration() -> SofiaConfiguration:
    """
    Create Sofía's runtime configuration.

    This is the executable entry point's configuration boundary.
    """

    return SofiaConfiguration(
        constitution_path=str(CONSTITUTION_PATH),
        constitution_hash_path=str(CONSTITUTION_HASH_PATH),
        identity_path=str(IDENTITY_PATH),
        personality_path=str(PERSONALITY_PATH),
        provider=ProviderConfiguration(
            provider="ollama",
            model="qwen3:14b",
        ),
    )


def create_application() -> SofiaApplication:
    """
    Construct the canonical Sofía application.
    """

    return SofiaApplication(
        create_configuration()
    )


def main() -> None:
    """
    Start Sofía's interactive terminal session.
    """

    application = create_application()

    conversation = ConversationLoop(
        application=application,
    )

    conversation.run()


if __name__ == "__main__":
    main()