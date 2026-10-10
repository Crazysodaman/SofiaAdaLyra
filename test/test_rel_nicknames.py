from datetime import datetime, timezone

import pytest

from sofia.rel.nicknames import NicknameRegistry, NicknameStatus
from sofia.social.model import AudienceKind, PrincipalContext


NOW = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)
pytestmark = [pytest.mark.pkg_rel, pytest.mark.pkg_social]


def sparks(audience="local:text"):
    return PrincipalContext("person:sparks", audience, AudienceKind.PRIVATE, "Sparks")


def test_sofia_can_propose_but_recipient_controls_acceptance_and_context(tmp_path):
    registry = NicknameRegistry(tmp_path / "sofia.db")
    proposal = registry.propose(
        proposer_id="sofia", recipient=sparks(), target_id="person:sparks",
        nickname="Sparks", contexts=("private", "casual"),
        evidence_ref="conversation:proposal-1", now=NOW,
    )
    assert proposal.status is NicknameStatus.PROPOSED
    assert registry.active_for(
        recipient=sparks(), target_id="person:sparks", context="private",
    ) == ()
    accepted = registry.respond(
        proposal.proposal_id, recipient=sparks(), accept=True,
        evidence_ref="ui:accept-1", now=NOW,
    )
    assert accepted.status is NicknameStatus.ACCEPTED
    assert registry.active_for(
        recipient=sparks(), target_id="person:sparks", context="private",
    ) == (accepted,)
    assert registry.active_for(
        recipient=sparks(), target_id="person:sparks", context="public",
    ) == ()


def test_declined_nickname_is_not_reused(tmp_path):
    registry = NicknameRegistry(tmp_path / "sofia.db")
    proposal = registry.propose(
        proposer_id="sofia", recipient=sparks(), target_id="person:sparks",
        nickname="Captain", contexts=("casual",), evidence_ref="proposal:1", now=NOW,
    )
    registry.respond(
        proposal.proposal_id, recipient=sparks(), accept=False,
        evidence_ref="ui:decline-1", now=NOW,
    )
    with pytest.raises(ValueError, match="already proposed"):
        registry.propose(
            proposer_id="sofia", recipient=sparks(), target_id="person:sparks",
            nickname=" captain ", contexts=("casual",), evidence_ref="proposal:2", now=NOW,
        )


def test_wrong_audience_cannot_accept_or_observe_nickname(tmp_path):
    registry = NicknameRegistry(tmp_path / "sofia.db")
    proposal = registry.propose(
        proposer_id="sofia", recipient=sparks(), target_id="sofia",
        nickname="Vix", contexts=("private",), evidence_ref="proposal:1", now=NOW,
    )
    wrong = sparks("discord:dm:1")
    with pytest.raises(PermissionError, match="another recipient scope"):
        registry.respond(
            proposal.proposal_id, recipient=wrong, accept=True,
            evidence_ref="ui:wrong-accept", now=NOW,
        )
    assert registry.active_for(recipient=wrong, target_id="sofia", context="private") == ()


def test_accepted_nickname_can_be_retired_or_revoked(tmp_path):
    registry = NicknameRegistry(tmp_path / "sofia.db")
    proposal = registry.propose(
        proposer_id="sofia", recipient=sparks(), target_id="sofia",
        nickname="Vix", contexts=("private",), evidence_ref="proposal:1", now=NOW,
    )
    registry.respond(
        proposal.proposal_id, recipient=sparks(), accept=True,
        evidence_ref="ui:accept-1", now=NOW,
    )
    retired = registry.retire(
        proposal.proposal_id, recipient=sparks(), revoke=False,
        evidence_ref="ui:retire-1", now=NOW,
    )
    assert retired.status is NicknameStatus.RETIRED
    assert registry.active_for(recipient=sparks(), target_id="sofia", context="private") == ()
    assert [event.to_status for event in registry.history(
        proposal.proposal_id, recipient=sparks(),
    )] == [NicknameStatus.PROPOSED, NicknameStatus.ACCEPTED, NicknameStatus.RETIRED]
