"""Deferred real NEURO shared-workspace broadcast and downstream read receipts."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from sofia.application.conversation_service import ConversationService
from sofia.neuro import NeuralSignal, NeuroRuntime
from sofia.neuro.store import NeuroObservabilityStore
from sofia.neuro.workspace import NeuroSharedWorkspace

pytestmark=pytest.mark.pkg_core
NOW=datetime(2026,10,11,12,tzinfo=timezone.utc)


def _signal(name, *, offset=0):
    return NeuralSignal(
        source=name,kind="goal",value=.8,confidence=.9,
        novelty=.7,urgency=.6,observed_at=NOW+timedelta(seconds=offset),
        ttl_seconds=300,
    )


def test_workspace_never_carries_more_than_three_eligible_nodes(tmp_path):
    store=NeuroObservabilityStore(tmp_path/"sofia.db")
    neuro=NeuroRuntime(observability=store)
    for i in range(7):
        neuro.observe_signal(_signal(f"project-{i}",offset=i))
    workspace=neuro.read_workspace(
        consumer="conversation",at=NOW+timedelta(seconds=7),
    )
    assert workspace is not None
    assert 0 < len(workspace.items) <= 3
    assert workspace.selection_method in {
        "salience-v1","connectome-competition-v0.1",
    }
    assert all(item.kind=="goal" for item in workspace.items)
    assert len(workspace.generation)==24
    assert neuro.read_workspace(
        consumer="personality",at=NOW+timedelta(seconds=8),
    ) is not None
    history={row["consumer"]:row for row in store.workspace_consumption()}
    assert history["conversation"]["observed_reads"]==1
    assert history["personality"]["observed_reads"]==1
    assert neuro.read_workspace(
        consumer="conversation",at=NOW+timedelta(seconds=200),
    ) is None
    assert {
        row["consumer"]:row["observed_reads"]
        for row in store.workspace_consumption()
    }=={"conversation":1,"personality":1}


def test_workspace_refuses_unknown_consumers_and_fabricated_future_reads(tmp_path):
    runtime=NeuroRuntime()
    runtime.observe_signal(_signal("important-project"))
    with pytest.raises(PermissionError,match="downstream"):
        runtime.read_workspace(consumer="training",at=NOW)
    with pytest.raises(ValueError,match="timezone"):
        runtime.read_workspace(consumer="conversation",at=NOW.replace(tzinfo=None))
    assert runtime.read_workspace(
        consumer="conversation",at=NOW-timedelta(seconds=1),
    ) is None


def test_conversation_service_reads_actual_published_workspace_not_parallel_context(tmp_path):
    store=NeuroObservabilityStore(tmp_path/"sofia.db")
    neuro=NeuroRuntime(observability=store)
    snapshot=neuro.observe_turn(
        content="Return to the model train wiring issue",
        created_at=NOW,channel="desktop",turn=None,
    )
    service=object.__new__(ConversationService)
    service._current_neuro_snapshot=snapshot
    service._current_neuro_message_id="message-1"
    service._current_matrix_message_id="message-1"
    service._neuro_runtime=neuro
    projected=ConversationService._neuro_context_message(
        service,current_user=SimpleNamespace(id="message-1",created_at=NOW),
    )
    assert projected is not None
    assert "NEURAL ATTENTION CONTEXT" in projected.content
    assert store.workspace_consumption()[0]["consumer"]=="conversation"
    assert store.workspace_consumption()[0]["observed_reads"]==1


def test_workspace_reset_does_not_mutate_underlying_neuro_facts():
    workspace=NeuroSharedWorkspace(max_items=2,ttl_seconds=2)
    runtime=NeuroRuntime()
    snapshot=runtime.observe_signal(_signal("confirmed"))
    broadcast=workspace.publish(snapshot)
    assert broadcast.items[0].key==snapshot.focus.key
    assert workspace.read(consumer="act",at=NOW) is not None
    workspace.clear()
    assert workspace.read(consumer="act",at=NOW) is None
    assert runtime.last_snapshot.focus.key==snapshot.focus.key


@pytest.mark.parametrize("ttl",[0,121,-1])
def test_workspace_rejects_unbounded_lifetime(ttl):
    with pytest.raises(ValueError,match="lifetime"):
        NeuroSharedWorkspace(ttl_seconds=ttl)
