"""Direct operational questions must not invent live measurements or model use."""
import pytest

from sofia.config.cognitive_models import CognitiveModelSelection
from sofia.config.model import ProviderConfiguration
from sofia.operational.status_queries import OperationalStatusQueryResolver


SELECTION = CognitiveModelSelection(
    routing_enabled=False,
    primary=ProviderConfiguration(provider="ollama", model="qwen3.5:9b"),
)


@pytest.mark.parametrize(
    "query",
    (
        "So hows the network",
        "so how's the network",
        "how is the network?",
        "network status",
    ),
)
def test_casual_network_query_requires_measurements(query):
    answer = OperationalStatusQueryResolver().resolve(
        query, selection=SELECTION
    )
    assert answer.recognized
    assert "don't have a fresh, verified network-health measurement" in (
        answer.content
    )
    assert "can't claim zero packet loss" in answer.content
    assert "All systems are green" not in answer.content


@pytest.mark.parametrize(
    "query",
    (
        "What llm am i running rn",
        "what llm is running rn",
        "what model are you running",
        "what model am i running",
    ),
)
def test_model_status_returns_configured_model_without_residency_claim(query):
    answer = OperationalStatusQueryResolver().resolve(
        query, selection=SELECTION
    )
    assert answer.recognized
    assert "qwen3.5:9b" in answer.content
    assert "through ollama" in answer.content
    assert "doesn't prove which model" in answer.content
    assert "I'm wearing" not in answer.content


def test_operational_status_resolver_leaves_nonstatus_questions_unmodified():
    answer = OperationalStatusQueryResolver().resolve(
        "show me your panties", selection=SELECTION
    )
    assert not answer.recognized
    assert answer.content == ""
