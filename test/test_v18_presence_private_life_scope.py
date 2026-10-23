"""Phase 08: private LIFE accomplishment cannot leak through implicit audience."""
from dataclasses import replace
from pathlib import Path
import sqlite3

import pytest

from sofia.platform.application.presence import PresenceInitiativeEngine
from sofia.social.principals import SPARKS_PRINCIPAL_ID
from test.test_presence_initiative import event, configured, policy


@pytest.mark.parametrize(
    ("audience", "recipient"),
    [
        (None, SPARKS_PRINCIPAL_ID),
        ("sparks", SPARKS_PRINCIPAL_ID),
        ("discord:dm:other", SPARKS_PRINCIPAL_ID),
        ("local:text", "untrusted-principal"),
    ],
)
def test_verified_life_milestone_rejects_implicit_or_foreign_audience(
    tmp_path: Path, audience: str | None, recipient: str,
):
    state = tmp_path / "sofia.db"
    with sqlite3.connect(state) as db:
        db.execute("CREATE TABLE conversation_messages(id TEXT PRIMARY KEY, role TEXT)")
    out = []
    service = configured(
        state, out, outreach_policy=policy(recipient_id=SPARKS_PRINCIPAL_ID),
    )
    presence = PresenceInitiativeEngine(state_path=state, act_service=service)
    original = event(f"life-audience-{recipient}-{audience}", recipient=recipient)
    proposal = replace(
        original, trigger_kind="task_completed",
        observation=replace(original.observation, audience_id=audience),
    )
    decision = presence.consider(proposal)
    assert decision.status == "suppressed"
    assert decision.reason == "private_milestone_requires_exact_local_owner"
    assert decision.notice_id is None
    assert presence.consider(proposal) == decision
    assert service.has_pending() is False
    assert out == []


def test_exact_private_life_owner_scope_retains_existing_act_controls(tmp_path):
    state = tmp_path / "sofia.db"
    with sqlite3.connect(state) as db:
        db.execute("CREATE TABLE conversation_messages(id TEXT PRIMARY KEY, role TEXT)")
    service = configured(
        state, [], outreach_policy=policy(recipient_id=SPARKS_PRINCIPAL_ID),
    )
    presence = PresenceInitiativeEngine(state_path=state, act_service=service)
    original = event("life-owner-exact", recipient=SPARKS_PRINCIPAL_ID)
    proposed = replace(
        original, trigger_kind="task_completed",
        observation=replace(original.observation, audience_id="local:text"),
    )
    assert presence.consider(proposed).status == "queued"
