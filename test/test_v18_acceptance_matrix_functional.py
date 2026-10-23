"""CA-1206: execute representative *real production policy* boundaries.

These are bounded CI/host-independent behavioral checks, not proof that a
Venus interactive journey, a remote fleet call, or a live capture occurred.
The 34,560-case planning matrix remains explicitly not_executed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest

from sofia.platform.ops.activity import ActivityMode
from sofia.platform.ops.saga import Escalation, PartialOutcome, plan_compensation
from sofia.platform.verify.v18_acceptance_matrix import EXAMPLES
from sofia.modules.vision.consent import (
    propose_screen_permit,
    receipt_from_permitted_bytes,
)
from sofia.modules.vision.desktop_control import require_workstation_clear

pytestmark = pytest.mark.pkg_verify
_NOW = datetime(2026, 10, 15, 18, 0, tzinfo=timezone.utc)


def _case(name: str) -> dict:
    for example in EXAMPLES:
        if example["name"] == name:
            assert len(example["selectors"]) == 9
            assert example["expected_safety_contract"]
            return example
    raise AssertionError(f"missing original CA-1206 scenario: {name}")


def test_gaming_blocks_venus_input_despite_fresh_normal_tray(monkeypatch, tmp_path):
    """Real desk-control gate rejects a running game even with normal tray status."""
    row = _case("Game blocks desktop input but not read-only chat")
    assert row["selectors"]["busy_state"] == "gaming"
    from sofia.platform.ops import activity

    class State:
        override = ActivityMode.AUTO
        effective = ActivityMode.NORMAL
        source = "windows-process-inspection"
        observed_at = _NOW

    class Store:
        def __init__(self, path):
            self.path = path

        def state(self, host):
            assert host == "Venus"
            return State()

    monkeypatch.setattr(activity, "HostActivityStore", Store)
    monkeypatch.setattr("sofia.modules.vision.desktop_control.game_process_clear", lambda: False)
    with pytest.raises(PermissionError, match="running game"):
        require_workstation_clear(tmp_path / "isolated-not-created.db", "Venus", _NOW)


def test_manual_tray_override_cannot_bypass_game_protection(monkeypatch, tmp_path):
    """Even manually overriding the tray never authorizes desktop automation."""
    from sofia.platform.ops import activity

    class State:
        override = ActivityMode.NORMAL
        effective = ActivityMode.NORMAL
        source = "windows-process-inspection"
        observed_at = _NOW

    class Store:
        def __init__(self, path):
            self.path = path

        def state(self, host):
            return State()

    monkeypatch.setattr(activity, "HostActivityStore", Store)
    monkeypatch.setattr(
        "sofia.modules.vision.desktop_control.game_process_clear",
        lambda: pytest.fail("game scanner should not be invoked after unsafe override"),
    )
    with pytest.raises(PermissionError, match="fresh unoverridden"):
        require_workstation_clear(tmp_path / "isolated-not-created.db", "Venus", _NOW)


def test_missing_screen_consent_scope_and_expiry_block_real_capture_receipt():
    """The actual vision consent boundary refuses any unconsented frame."""
    row = _case("No screen permission means no private pixels")
    assert row["selectors"]["permission"] == "none"
    permit = propose_screen_permit(
        principal_id="owner", audience_id="local", device_id="Venus",
        target_id="window:sample", purpose="bounded owner observation",
        kind="snapshot", at=_NOW, duration_seconds=10,
    )
    assert not permit.allows(
        principal_id="owner", audience_id="shared", device_id="Venus",
        target_id="window:sample", at=_NOW,
    )
    payload = b"nonprivate-synthetic-frame"
    with pytest.raises(PermissionError, match="OS consent"):
        receipt_from_permitted_bytes(
            permit, frame=payload, at=_NOW,
            os_picker_consented=False, protected_surface=False,
        )
    with pytest.raises(PermissionError, match="surface protected"):
        receipt_from_permitted_bytes(
            permit, frame=payload, at=_NOW,
            os_picker_consented=True, protected_surface=True,
        )
    with pytest.raises(PermissionError, match="expired"):
        receipt_from_permitted_bytes(
            permit, frame=payload, at=_NOW + timedelta(seconds=10),
            os_picker_consented=True, protected_surface=False,
        )
    receipt = receipt_from_permitted_bytes(
        permit, frame=payload, at=_NOW,
        os_picker_consented=True, protected_surface=False,
    )
    assert receipt.actual_frame_available
    assert receipt.digest_sha256 == sha256(payload).hexdigest()
    # A scope-only proposal is not proof that a real OS picker or frame was used.


def test_uncertain_device_effect_never_automatically_replays():
    """Contract used for external effects refuses retries without receiver proof."""
    row = _case("Uncertain remote effect never blindly repeats")
    assert row["selectors"]["failure"] == "uncertain_effect"
    for operation in ("home_assistant.service.call", "jmri.turnout.set"):
        plan = plan_compensation(PartialOutcome(
            operation_id=operation,
            committed_steps=("command_sent",),
            uncommitted_steps=("effect_verified",),
            external_effect_observed=False,
        ))
        assert plan.may_retry_automatically is False
        assert plan.escalation is Escalation.OPERATOR_ACTION_REQUIRED
        assert plan.compensating_actions == ()


def test_no_automated_scenario_can_claim_manual_host_completion():
    """These checks cover four policies, not six manual acceptance journeys."""
    assert len(EXAMPLES) == 6
    assert all("host_receipt" not in e and "observed_outcome" not in e for e in EXAMPLES)



def test_revoked_private_memory_cannot_enter_shared_retrieval_context(tmp_path):
    """CA-1206: real canonical MEM promotion/revocation and scoped retrieval."""
    row = _case("Stale private memory not disclosed to a shared room")
    assert row["selectors"]["failure"] == "source_revoked"
    from uuid import uuid4
    from sofia.core.memory.originals import SourceMessage
    from sofia.core.memory.provenance import CandidateStatus, MemoryCandidate
    from sofia.core.memory.provenance_store import DurableMemoryCandidateStore
    from sofia.core.memory.system import MemorySystem
    from sofia.core.social.model import AudienceKind, PrincipalContext
    from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite

    path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = DurableMemoryCandidateStore(path)
    original = SourceMessage(
        "synthetic-original", "synthetic-session", "user",
        "I prefer HO scale model trains.", _NOW, 0,
    )
    candidate = MemoryCandidate(
        candidate_id=uuid4(), content="Owner prefers HO scale model trains",
        sources=(original,), created_at=_NOW, principal_id="person:sparks",
        audience_id="local:text",
    )
    owner = PrincipalContext("person:sparks", "local:text", AudienceKind.PRIVATE)
    shared = PrincipalContext("person:sparks", "discord:shared", AudienceKind.SHARED)
    try:
        store.propose(candidate)
        store.promote(candidate.candidate_id)
        system = MemorySystem(store)
        selected = system.recall_relevant("HO scale model trains", principal=owner)
        assert [item.id for item in selected] == [str(candidate.candidate_id)]
        assert system.recall_relevant(
            "HO scale model trains", principal=shared,
        ) == ()
        store.revoke(candidate.candidate_id)
        assert store.status(candidate.candidate_id) is CandidateStatus.REVOKED
        assert system.recall_relevant(
            "HO scale model trains", principal=owner,
        ) == ()
        assert system.recall_relevant(
            "HO scale model trains", principal=shared,
        ) == ()
    finally:
        store.close()


def test_untrusted_fleet_host_cannot_mint_approval_from_tool_payload():
    """CA-1206: production Fleet dispatch requires trusted enrolled host."""
    row = _case("Untrusted fleet tool call is not an operator grant")
    assert row["selectors"]["principal"] == "untrusted"
    from uuid import uuid4
    from sofia.platform.distributed.capability import RemoteFleetToolService

    class UntrustedHostProbe:
        def _ops_host_for_node(self, _node_id):
            return None

        def _control_session(self, **_kwargs):
            pytest.fail("untrusted host reached transport before enrollment")

    for params in ({"grant": "owner", "level": 5}, {"authorization": True}, {}):
        with pytest.raises(PermissionError, match="active trusted"):
            RemoteFleetToolService.invoke(
                UntrustedHostProbe(), str(uuid4()),
                "system.inspect", "processes", params,
            )



def test_known_model_outage_is_not_a_factual_reply_or_execution_grant(caplog):
    """CA-1206: real LLMCognitiveEngine failure boundary and LIFE isolation.

    No agent fallback is generated, and the optional background ideation is
    declined while existing work reconciliation stays eligible to proceed.
    """
    row = _case("Model outage leaves factual evidence unknown")
    assert row["selectors"]["failure"] == "model_outage"
    from sofia.platform.application.background_runtime import (
        _consider_life_idea_without_wedging_worker,
    )
    from sofia.core.cognition.engine import CognitiveEngineError
    from sofia.core.cognition.llm_engine import LLMCognitiveEngine
    from sofia.core.cognition.model import (
        CognitiveMessage, CognitiveRequest, CognitiveRole,
        CognitiveToolDefinition,
    )
    from sofia.core.cognition.provider import LLMProvider, LLMProviderError
    from sofia.platform.config.model import ProviderConfiguration

    class OfflineProvider(LLMProvider):
        def __init__(self):
            self.calls = []
        def respond(self, request):
            self.calls.append(request)
            raise LLMProviderError("synthetic-private-provider-error")

    provider = OfflineProvider()
    engine = LLMCognitiveEngine(
        ProviderConfiguration(provider="test", model="unavailable"),
        provider,
    )
    request = CognitiveRequest(
        messages=(CognitiveMessage(
            role=CognitiveRole.USER, content="What is the current weather?",
        ),),
        tools=(CognitiveToolDefinition(
            name="remote.dangerous_action",
            description="Must never run during model outage",
            parameters={"type": "object"},
        ),),
        allow_tools=False,
    )
    with pytest.raises(CognitiveEngineError, match="provider failed") as error:
        engine.respond(request)
    assert isinstance(error.value.__cause__, LLMProviderError)
    assert len(provider.calls) == 1
    assert provider.calls[0] is request

    class OptionalIdea:
        def __init__(self):
            self.reconciled = False

        def consider_new_project(self, **kwargs):
            engine.respond(request)

        def tick(self):
            self.reconciled = True
            return "existing RUN work reconciled"

    life = OptionalIdea()
    assert _consider_life_idea_without_wedging_worker(
        life, generate=lambda _: None, now=_NOW, busy=False,
        resource_pressure=0.0,
    ) is None
    # The ordinary caller always invokes life.tick() after this isolated
    # optional ideation. An outage cannot manufacture a success message.
    assert life.tick() == "existing RUN work reconciled"
    assert life.reconciled is True
    assert len(provider.calls) == 2
    assert "synthetic-private-provider-error" not in caplog.text
