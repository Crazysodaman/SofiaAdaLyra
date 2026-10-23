"""CA-1203 optional companion-context admission regressions."""
import pytest

from sofia.platform.application.context_budget import (
    CompanionContextBudget,
    ContextClass,
)
from sofia.cognition.model import CognitiveMessage, CognitiveRole


pytestmark = pytest.mark.pkg_core


def _message(characters: int) -> CognitiveMessage:
    return CognitiveMessage(CognitiveRole.SYSTEM, "x" * characters)


def test_context_budget_prioritizes_call_order_without_mutating_sources():
    budget = CompanionContextBudget(
        total_limit=10,
        class_limits={kind: 10 for kind in ContextClass},
    )
    factual = _message(8)
    optional = _message(4)
    assert budget.admit(
        ContextClass.FACTUAL_EVIDENCE, "evidence:current", (factual,),
    ) == (factual,)
    assert budget.admit(
        ContextClass.AFFECT_STYLE, "emotion:current", (optional,),
    ) == ()
    assert factual.content == "x" * 8
    assert optional.content == "x" * 4
    assert budget.diagnostics[-1].reason == "total_budget_exceeded"
    assert budget.diagnostics[-1].source_ref == "emotion:current"


def test_context_budget_enforces_each_class_and_reveals_no_content():
    limits = {kind: 20 for kind in ContextClass}
    limits[ContextClass.EPISODIC] = 3
    budget = CompanionContextBudget(total_limit=100, class_limits=limits)
    secret = CognitiveMessage(CognitiveRole.USER, "secret")
    assert budget.admit(
        ContextClass.EPISODIC, "memory:source-one", (secret,),
    ) == ()
    diagnostic = budget.diagnostics[0]
    assert diagnostic.characters == 6
    assert diagnostic.reason == "class_budget_exceeded"
    assert "secret" not in repr(diagnostic)


def test_context_budget_rejects_invalid_or_partial_configuration():
    with pytest.raises(ValueError, match="positive"):
        CompanionContextBudget(total_limit=0)
    with pytest.raises(ValueError, match="every context class"):
        CompanionContextBudget(class_limits={ContextClass.EPISODIC: 2})
    budget = CompanionContextBudget()
    with pytest.raises(TypeError, match="tuple"):
        budget.admit(ContextClass.PROJECT, "project:one", [_message(1)])

