"""Deterministic, headless scene transitions; receipts are simulated."""
from copy import deepcopy
import pytest
from sofia.avatar.scene import Actor, Action, Prop, Scene, SceneConflict, SceneDenied, SceneError


def scene():
    return Scene((Prop("mug", "Virtual mug"),))


def plan(s, operation_id="pickup", actor=Actor.SPARKS, action=Action.PICK_UP,
         revision=1, recipient=None):
    return s.propose(operation_id=operation_id, prop_id="mug", actor=actor,
                     action=action, expected_revision=revision, recipient=recipient)


def picked_up(s):
    plan(s)
    return s.acknowledge(operation_id="pickup", renderer_succeeded=True)


def offered(s):
    picked_up(s)
    plan(s, "offer", Actor.SPARKS, Action.OFFER, 2, Actor.SOFIA)
    return s.acknowledge(operation_id="offer", renderer_succeeded=True)


def test_proposal_is_not_claimed_completed_motion():
    s = scene()
    plan(s)
    assert s.read("mug").holder is None
    with pytest.raises(SceneConflict):
        s.snapshot()


def test_failed_renderer_ack_keeps_original_state():
    s = scene()
    plan(s)
    state = s.acknowledge(operation_id="pickup", renderer_succeeded=False)
    assert state.holder is None and state.revision == 1
    with pytest.raises(SceneConflict):
        s.acknowledge(operation_id="pickup", renderer_succeeded=True)


def test_pick_up_offer_accept_requires_two_explicit_moves():
    s = scene()
    offer = offered(s)
    assert offer.holder is Actor.SPARKS and offer.offered_to is Actor.SOFIA
    plan(s, "accept", Actor.SOFIA, Action.ACCEPT, 3)
    assert s.read("mug").holder is Actor.SPARKS
    result = s.acknowledge(operation_id="accept", renderer_succeeded=True)
    assert result.holder is Actor.SOFIA and result.offered_to is None
    assert result.revision == 4


def test_decline_releases_offer_without_changing_holder():
    s = scene()
    offered(s)
    plan(s, "decline", Actor.SOFIA, Action.DECLINE, 3)
    result = s.acknowledge(operation_id="decline", renderer_succeeded=True)
    assert result.holder is Actor.SPARKS and result.offered_to is None


def test_place_frees_object_after_ack():
    s = scene()
    picked_up(s)
    plan(s, "place", Actor.SPARKS, Action.PLACE, 2)
    assert s.acknowledge(operation_id="place", renderer_succeeded=True).holder is None


@pytest.mark.parametrize("actor,action,revision,recipient", [
    (Actor.SOFIA, Action.PLACE, 1, None),
    (Actor.SOFIA, Action.ACCEPT, 1, None),
    (Actor.SPARKS, Action.OFFER, 1, Actor.SOFIA),
    (Actor.SPARKS, Action.PICK_UP, 1, Actor.SOFIA),
    (Actor.SPARKS, Action.PICK_UP, True, None),
    ("sparks", Action.PICK_UP, 1, None),
])
def test_invalid_actor_holder_action_or_revision_denied(actor, action, revision, recipient):
    s = scene()
    with pytest.raises((SceneDenied, SceneConflict)):
        plan(s, actor=actor, action=action, revision=revision, recipient=recipient)


def test_receiver_cannot_accept_before_offer_ack():
    s = scene()
    picked_up(s)
    plan(s, "offer", Actor.SPARKS, Action.OFFER, 2, Actor.SOFIA)
    with pytest.raises((SceneDenied, SceneConflict)):
        plan(s, "accept", Actor.SOFIA, Action.ACCEPT, 2)


def test_wrong_receiver_cannot_accept():
    s = scene()
    offered(s)
    with pytest.raises(SceneDenied):
        plan(s, "accept", Actor.SPARKS, Action.ACCEPT, 3)


def test_duplicate_or_concurrent_operations_fail():
    s = scene()
    plan(s)
    with pytest.raises(SceneConflict):
        plan(s, "other")
    with pytest.raises(SceneConflict):
        plan(s)
    s.acknowledge(operation_id="pickup", renderer_succeeded=True)
    with pytest.raises(SceneConflict):
        plan(s)


def test_cancel_does_not_mutate_prop_and_blocks_late_ack():
    s = scene()
    plan(s)
    s.cancel(operation_id="pickup")
    assert s.read("mug").revision == 1
    with pytest.raises(SceneConflict):
        s.acknowledge(operation_id="pickup", renderer_succeeded=True)


def test_stop_cancels_unacknowledged_proposals():
    s = scene()
    plan(s)
    s.stop()
    assert s.read("mug").holder is None
    with pytest.raises(SceneDenied):
        s.acknowledge(operation_id="pickup", renderer_succeeded=True)
    with pytest.raises(SceneDenied):
        plan(s, "other")


def test_non_boolean_ack_is_not_accepted():
    s = scene()
    plan(s)
    with pytest.raises(SceneDenied):
        s.acknowledge(operation_id="pickup", renderer_succeeded=1)
    assert s.read("mug").holder is None


def test_snapshot_restore_retains_holder_offer_and_replay_defense():
    s = scene()
    offered(s)
    data = s.snapshot()
    restored = Scene.restore(data)
    assert restored.snapshot() == data
    with pytest.raises(SceneConflict):
        plan(restored, "pickup", Actor.SPARKS, Action.PICK_UP, 3)
    plan(restored, "accept", Actor.SOFIA, Action.ACCEPT, 3)
    assert restored.acknowledge(operation_id="accept", renderer_succeeded=True).holder is Actor.SOFIA


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(schema=2),
    lambda d: d["props"].append(dict(d["props"][0])),
    lambda d: d["props"][0].update(holder="unknown"),
    lambda d: d["props"][0].update(offered_to="sparks"),
    lambda d: d["props"][0].update(revision=True),
    lambda d: d["finished"].append(d["finished"][0]),
])
def test_bad_restore_rejected(mutate):
    s = scene()
    picked_up(s)
    data = deepcopy(s.snapshot())
    mutate(data)
    with pytest.raises(SceneError):
        Scene.restore(data)
