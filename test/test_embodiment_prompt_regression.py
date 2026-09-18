import os
from pathlib import Path

import pytest

from sofia.cognition.llm_engine import LLMCognitiveEngine
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
)
from sofia.cognition.provider import LLMProvider
from sofia.cognition.providers.ollama_provider import OllamaProvider
from sofia.composition.root import compose
from sofia.config.model import (
    ProviderConfiguration,
    SofiaConfiguration,
)


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

AVATAR_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "data"
    / "avatar.json"
)

OLLAMA_MODEL = os.getenv(
    "SOFIA_OLLAMA_MODEL",
    "qwen3:14b",
)


class CapturingProvider(LLMProvider):
    """
    Deterministic provider used to capture the exact cognitive
    request presented to the LLM provider boundary.
    """

    def __init__(self) -> None:
        self.requests: list[CognitiveRequest] = []

    def respond(
        self,
        request: CognitiveRequest,
    ) -> CognitiveResponse:
        self.requests.append(request)

        return CognitiveResponse(
            content="Captured.",
        )


def create_configuration(
    tmp_path,
) -> SofiaConfiguration:
    identity_path = tmp_path / "identity.json"

    identity_path.write_text(
        '{"name": "Sofía Ada Lyra"}',
        encoding="utf-8",
    )

    personality_path = tmp_path / "personality.json"

    personality_path.write_text(
        """
        {
            "name": "Sofía Ada Lyra",
            "traits": [
                "rigorous",
                "direct",
                "curious"
            ],
            "communication_style":
                "Clear, direct, evidence-driven, and conversational."
        }
        """,
        encoding="utf-8",
    )

    return SofiaConfiguration(
        constitution_path=CONSTITUTION_PATH,
        constitution_hash_path=HASH_PATH,
        identity_path=identity_path,
        personality_path=personality_path,
        avatar_path=AVATAR_PATH,
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(
            provider="ollama",
            model=OLLAMA_MODEL,
        ),
        filesystem_root=PROJECT_ROOT,
    )


def capture_current_request(
    tmp_path,
) -> CognitiveRequest:
    configuration = create_configuration(
        tmp_path
    )

    runtime = compose(configuration)
    runtime.start()

    provider = CapturingProvider()

    runtime.cognitive_system.engine = LLMCognitiveEngine(
        configuration=configuration.provider,
        provider=provider,
    )

    runtime.respond(
        CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="What are your measurements?",
                ),
            ),
        )
    )

    assert len(provider.requests) == 1

    request = provider.requests[0]

    runtime.shutdown()

    return request


def system_content(
    request: CognitiveRequest,
) -> str:
    return next(
        message.content
        for message in request.messages
        if message.role is CognitiveRole.SYSTEM
    )


def remove_section(
    content: str,
    heading: str,
    next_heading: str,
) -> str:
    start_marker = f"\n{heading}\n"
    end_marker = f"\n{next_heading}\n"

    start = content.index(start_marker)
    end = content.index(
        end_marker,
        start + len(start_marker),
    )

    return (
        content[:start]
        + content[end:]
    )


def build_variant_request(
    request: CognitiveRequest,
    *,
    remove_self_model: bool,
    remove_semantic_contract: bool,
) -> CognitiveRequest:
    content = system_content(request)

    if remove_self_model:
        content = remove_section(
            content,
            "AUTHORITATIVE SELF MODEL",
            "SELF-DESCRIPTION AND EMBODIMENT SEMANTIC CONTRACT",
        )

    if remove_semantic_contract:
        content = remove_section(
            content,
            "SELF-DESCRIPTION AND EMBODIMENT SEMANTIC CONTRACT",
            "OPERATIONAL STATE",
        )

    non_system_messages = tuple(
        message
        for message in request.messages
        if message.role is not CognitiveRole.SYSTEM
    )

    return CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.SYSTEM,
                content=content,
            ),
            *non_system_messages,
        ),
    )


def create_ollama_provider() -> OllamaProvider:
    return OllamaProvider(
        configuration=ProviderConfiguration(
            provider="ollama",
            model=OLLAMA_MODEL,
        )
    )


@pytest.mark.integration
def test_embodiment_prompt_regression_variants(
    tmp_path,
) -> None:
    request = capture_current_request(
        tmp_path
    )

    current = request

    without_self_model = build_variant_request(
        request,
        remove_self_model=True,
        remove_semantic_contract=False,
    )

    without_semantic_contract = build_variant_request(
        request,
        remove_self_model=False,
        remove_semantic_contract=True,
    )

    without_both = build_variant_request(
        request,
        remove_self_model=True,
        remove_semantic_contract=True,
    )

    variants = (
        (
            "CURRENT",
            current,
        ),
        (
            "WITHOUT_AUTHORITATIVE_SELF_MODEL",
            without_self_model,
        ),
        (
            "WITHOUT_SEMANTIC_CONTRACT",
            without_semantic_contract,
        ),
        (
            "WITHOUT_BOTH",
            without_both,
        ),
    )

    provider = create_ollama_provider()

    for name, variant in variants:
        response = provider.respond(
            variant
        )

        print(
            "\n"
            + "=" * 80
            + f"\n{name}\n"
            + "=" * 80
            + f"\n{response.content.strip()}\n"
        )

        assert response.content.strip()