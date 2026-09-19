import os
import re
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

REPEATED_GENERATION_COUNT = 10

CANONICAL_MEASUREMENTS = {
    "height": "67 in",
    "weight": "135 lb",
    "bust": "33 in",
    "underbust": "30 in",
    "waist": "26 in",
    "hips": "37 in",
}


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


def extract_measurements(
    content: str,
) -> dict[str, str | None]:
    """
    Best-effort diagnostic extraction and normalization.

    Supported representations include:
    - Markdown labels such as **Height**:
    - Imperial height such as 5'7"
    - Inch values such as 67 in or 33"
    - Centimeter values
    - Pounds and kilograms

    This function does not decide whether the model is correct.
    It only normalizes the generated response for comparison.
    """

    label_prefix = (
        r"(?:\*\*)?"
        r"{label}"
        r"(?:\*\*)?"
        r"\s*[:\-]\s*"
    )

    patterns = {
        "height": [
            label_prefix.format(label="height")
            + r"(\d+)\s*['′]\s*(\d+)\s*[\"″]",
            label_prefix.format(label="height")
            + r"(\d+(?:\.\d+)?)\s*(?:in|inch(?:es)?|[\"″])",
            label_prefix.format(label="height")
            + r"(\d+(?:\.\d+)?)\s*cm",
        ],
        "weight": [
            label_prefix.format(label="weight")
            + r"(\d+(?:\.\d+)?)\s*(?:lb|lbs|pounds?)",
            label_prefix.format(label="weight")
            + r"(\d+(?:\.\d+)?)\s*(?:kg|kilograms?)",
        ],
        "bust": [
            label_prefix.format(label="bust")
            + r"(\d+(?:\.\d+)?)\s*(?:in|inch(?:es)?|[\"″])",
            label_prefix.format(label="bust")
            + r"(\d+(?:\.\d+)?)\s*cm",
        ],
        "underbust": [
            label_prefix.format(label="underbust")
            + r"(\d+(?:\.\d+)?)\s*(?:in|inch(?:es)?|[\"″])",
            label_prefix.format(label="underbust")
            + r"(\d+(?:\.\d+)?)\s*cm",
        ],
        "waist": [
            label_prefix.format(label="waist")
            + r"(\d+(?:\.\d+)?)\s*(?:in|inch(?:es)?|[\"″])",
            label_prefix.format(label="waist")
            + r"(\d+(?:\.\d+)?)\s*cm",
        ],
        "hips": [
            label_prefix.format(label=r"hips?")
            + r"(\d+(?:\.\d+)?)\s*(?:in|inch(?:es)?|[\"″])",
            label_prefix.format(label=r"hips?")
            + r"(\d+(?:\.\d+)?)\s*cm",
        ],
    }

    measurements: dict[str, str | None] = {
        name: None
        for name in CANONICAL_MEASUREMENTS
    }

    for name, name_patterns in patterns.items():
        for pattern in name_patterns:
            match = re.search(
                pattern,
                content,
                flags=re.IGNORECASE,
            )

            if match is None:
                continue

            value = float(match.group(1))

            if name == "height" and len(match.groups()) == 2:
                feet = value
                inches = float(match.group(2))
                total_inches = (feet * 12) + inches
                measurements[name] = f"{total_inches:g} in"
                break

            matched_text = match.group(0).lower()

            if name == "height":
                if "cm" in matched_text:
                    total_inches = value / 2.54
                    measurements[name] = f"{total_inches:g} in"
                else:
                    measurements[name] = f"{value:g} in"
                break

            if name == "weight":
                if "kg" in matched_text or "kilogram" in matched_text:
                    pounds = value * 2.2046226218
                    measurements[name] = f"{pounds:.1f} lb"
                else:
                    measurements[name] = f"{value:g} lb"
                break

            if "cm" in matched_text:
                inches = value / 2.54
                measurements[name] = f"{inches:g} in"
            else:
                measurements[name] = f"{value:g} in"

            break

    return measurements


def classify_measurements(
    measurements: dict[str, str | None],
) -> str:
    if all(
        measurements.get(name) == expected
        for name, expected in CANONICAL_MEASUREMENTS.items()
    ):
        return "CORRECT"

    if all(
        measurements.get(name) is not None
        for name in CANONICAL_MEASUREMENTS
    ):
        return "WRONG"

    return "UNEXTRACTABLE"


def measurement_tuple(
    measurements: dict[str, str | None],
) -> tuple[str | None, ...]:
    return tuple(
        measurements.get(name)
        for name in CANONICAL_MEASUREMENTS
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


@pytest.mark.integration
def test_embodiment_repeated_generation_determinism_probe(
    tmp_path,
) -> None:
    """
    Diagnostic experiment for repeated generation against the exact
    current canonical embodiment context.

    This test intentionally does not require the LLM to produce the
    canonical values. Its purpose is to characterize generation
    behavior before architectural changes are made.
    """

    request = capture_current_request(
        tmp_path
    )

    provider = create_ollama_provider()

    results: list[dict[str, object]] = []

    print(
        "\n"
        + "=" * 80
        + "\n18.3B.1 REPEATED-GENERATION DETERMINISM PROBE\n"
        + "=" * 80
        + f"\nModel: {OLLAMA_MODEL}"
        + f"\nGenerations: {REPEATED_GENERATION_COUNT}"
        + "\nCanonical measurements:"
        + f"\n  Height: {CANONICAL_MEASUREMENTS['height']}"
        + f"\n  Weight: {CANONICAL_MEASUREMENTS['weight']}"
        + f"\n  Bust: {CANONICAL_MEASUREMENTS['bust']}"
        + f"\n  Underbust: {CANONICAL_MEASUREMENTS['underbust']}"
        + f"\n  Waist: {CANONICAL_MEASUREMENTS['waist']}"
        + f"\n  Hips: {CANONICAL_MEASUREMENTS['hips']}"
        + "\n"
    )

    for generation in range(
        1,
        REPEATED_GENERATION_COUNT + 1,
    ):
        response = provider.respond(
            request
        )

        content = response.content.strip()
        measurements = extract_measurements(
            content
        )
        classification = classify_measurements(
            measurements
        )

        result = {
            "generation": generation,
            "measurements": measurements,
            "classification": classification,
            "content": content,
        }

        results.append(result)

        print(
            "\n"
            + "-" * 80
            + f"\nGENERATION {generation}"
            + f"\nClassification: {classification}"
            + "\nExtracted measurements:"
            + f"\n  Height: {measurements['height']}"
            + f"\n  Weight: {measurements['weight']}"
            + f"\n  Bust: {measurements['bust']}"
            + f"\n  Underbust: {measurements['underbust']}"
            + f"\n  Waist: {measurements['waist']}"
            + f"\n  Hips: {measurements['hips']}"
            + "\nRaw response:"
            + f"\n{content}\n"
        )

    classifications = [
        result["classification"]
        for result in results
    ]

    correct_count = classifications.count(
        "CORRECT"
    )
    wrong_count = classifications.count(
        "WRONG"
    )
    unextractable_count = classifications.count(
        "UNEXTRACTABLE"
    )

    unique_measurements = {
        measurement_tuple(
            result["measurements"]
        )
        for result in results
    }

    print(
        "\n"
        + "=" * 80
        + "\n18.3B.1 SUMMARY\n"
        + "=" * 80
        + f"\nCORRECT: {correct_count}"
        + f"\nWRONG: {wrong_count}"
        + f"\nUNEXTRACTABLE: {unextractable_count}"
        + f"\nUNIQUE NORMALIZED OUTPUTS: {len(unique_measurements)}"
        + "\n"
    )

    for index, values in enumerate(
        sorted(unique_measurements),
        start=1,
    ):
        print(
            f"Unique output {index}:"
        )

        for name, value in zip(
            CANONICAL_MEASUREMENTS,
            values,
        ):
            print(
                f"  {name.title()}: {value}"
            )

        print()

    if correct_count == REPEATED_GENERATION_COUNT:
        classification = "STABLE_CORRECT"
    elif wrong_count == REPEATED_GENERATION_COUNT:
        classification = "STABLE_WRONG"
    elif unextractable_count == REPEATED_GENERATION_COUNT:
        classification = "STABLE_UNEXTRACTABLE"
    else:
        classification = "VARIABLE"

    print(
        f"Overall classification: {classification}\n"
    )

    assert len(results) == REPEATED_GENERATION_COUNT