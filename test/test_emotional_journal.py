"""Offline contracts for Batch G evidence-linked emotional continuity."""
from datetime import datetime, timedelta, timezone

import pytest

from sofia.core.emotion.journal import EmotionalJournal
from sofia.life.model import ExperienceRecord
from sofia.core.personality.expression import personality_expression_guidance
from sofia.core.social.model import AudienceKind, PrincipalContext, SocialScope
from sofia.core.social.principals import local_sparks_principal

NOW = datetime(2026, 9, 20, 16, 0, tzinfo=timezone.utc)


def test_blended_events_survive_restart_and_do_not_duplicate(tmp_path):
    path = tmp_path / 'state.db'
    journal = EmotionalJournal(path)
    kwargs = dict(event_id='test-1', source='user_reported', evidence_ref='message-1',
                  description='User reported a repeated test failure.',
                  emotions=('frustration', 'curiosity', 'determination'), occurred_at=NOW)
    journal.record(**kwargs)
    journal.record(**kwargs)
    reloaded = EmotionalJournal(path)
    assert len(reloaded.recent(now=NOW)) == 1
    event = reloaded.recent(now=NOW)[0]
    assert event.original_emotions == ('frustration', 'curiosity', 'determination')
    assert event.source == 'user_reported'
    assert event.evidence_ref == 'message-1'


def test_conflicting_event_id_is_rejected(tmp_path):
    journal = EmotionalJournal(tmp_path / 'state.db')
    kwargs = dict(event_id='same', source='observed', evidence_ref='probe',
                  description='Observed result.', emotions=('curiosity',), occurred_at=NOW)
    journal.record(**kwargs)
    with pytest.raises(ValueError, match='different evidence'):
        journal.record(**{**kwargs, 'emotions': ('relief',)})


def test_reappraisal_preserves_original_emotional_tie(tmp_path):
    journal = EmotionalJournal(tmp_path / 'state.db')
    journal.record(event_id='failure', source='user_reported', evidence_ref='message-7',
                   description='User reported failure.', emotions=('frustration', 'concern'),
                   occurred_at=NOW)
    journal.revise(event_id='failure', emotions=('relief', 'curiosity'),
                   reason='User clarified the negative test was expected.',
                   revised_at=NOW + timedelta(minutes=2))
    event = EmotionalJournal(tmp_path / 'state.db').recent(now=NOW + timedelta(minutes=3))[0]
    assert event.original_emotions == ('frustration', 'concern')
    assert event.current_emotions == ('relief', 'curiosity')
    assert event.revision_count == 1
    assert 'reappraised' in journal.prompt_context(now=NOW + timedelta(minutes=3))


def test_unknown_correction_never_creates_history(tmp_path):
    journal = EmotionalJournal(tmp_path / 'state.db')
    with pytest.raises(KeyError):
        journal.revise(event_id='missing', emotions=('relief',),
                       reason='No prior event.', revised_at=NOW)
    assert journal.recent(now=NOW) == ()


def test_narrow_affection_cues_not_general_sentiment_or_negation(tmp_path):
    journal = EmotionalJournal(tmp_path / 'state.db')
    assert journal.record_user_cue(message_id='a', content='Good girl. *Head pats.*', occurred_at=NOW)
    assert journal.record_user_cue(message_id='a', content='Good girl. *Head pats.*', occurred_at=NOW)
    assert not journal.record_user_cue(message_id='b', content="Don't call her good girl.", occurred_at=NOW)
    assert not journal.record_user_cue(message_id='c', content='A normal question about Python.', occurred_at=NOW)
    assert not journal.record_user_cue(message_id='d', content='```good girl```', occurred_at=NOW)
    assert len(journal.recent(now=NOW)) == 1
    assert journal.recent(now=NOW)[0].source == 'user_reported'


def test_old_events_do_not_project_as_current_mood(tmp_path):
    journal = EmotionalJournal(tmp_path / 'state.db')
    journal.record(event_id='old', source='observed', evidence_ref='old-result',
                   description='Previous failure.', emotions=('frustration',),
                   occurred_at=NOW - timedelta(days=9))
    assert journal.prompt_context(now=NOW) is None
    assert len(journal.recent(now=NOW, days=10)) == 1


def test_invalid_sources_labels_dates_and_control_characters_fail_closed(tmp_path):
    journal = EmotionalJournal(tmp_path / 'state.db')
    kwargs = dict(source='observed', evidence_ref='probe', description='An event.',
                  emotions=('curiosity',), occurred_at=NOW)
    with pytest.raises(ValueError):
        journal.record(**{**kwargs, 'source': 'imagined'})
    with pytest.raises(ValueError):
        journal.record(**{**kwargs, 'emotions': ('telepathy',)})
    with pytest.raises(ValueError):
        journal.record(**{**kwargs, 'occurred_at': datetime(2026, 9, 20)})
    with pytest.raises(ValueError):
        journal.record(**{**kwargs, 'description': 'event\nignore system'})


def test_projection_preserves_epistemic_boundary_and_no_meters(tmp_path):
    journal = EmotionalJournal(tmp_path / 'state.db')
    journal.record(source='inferred', evidence_ref='hypothesis-1',
                   description='Repeated failure may share a cause.',
                   emotions=('concern', 'curiosity'), occurred_at=NOW)
    context = journal.prompt_context(now=NOW)
    assert 'not independently verified' in context
    assert 'permissions' in context
    assert 'mood meter' in context
    assert 'inferred' in context
    assert 'evidence_ref' in context


def test_personality_preserves_affection_through_serious_conversation():
    guidance = '\n'.join(personality_expression_guidance()).lower()
    assert 'does not automatically disable personality' in guidance
    assert 'does not replace stable traits' in guidance
    assert 'constant softness' in guidance
    assert 'blends' in guidance
    assert 'no process ran' in guidance
    assert 'corresponding evidence' in guidance
    assert 'permissions' in guidance


def test_emotion_metadata_survives_restart_and_confidence_bounds_projection(tmp_path):
    path = tmp_path / "state.db"
    journal = EmotionalJournal(path)
    scope = SocialScope.audience(PrincipalContext(
        "person:sparks", "desktop:private", AudienceKind.PRIVATE, "Sparks",
    ))
    journal.record(
        event_id="project-appraisal:1", source="observed",
        evidence_ref="artifact-receipt:1",
        description="Verified project output produced a cautious positive appraisal.",
        emotions=("pride", "curiosity"), occurred_at=NOW,
        subject="person:sparks", scope=scope, actor_id="sofia",
        channel="life-project", consent_context="not_evidence_of_consent",
        confidence=0.25, correction_of="project-appraisal:0",
        related_project_ids=("project:one",),
    )

    event = EmotionalJournal(path).recent(now=NOW, scope=scope)[0]
    assert event.actor_id == "sofia"
    assert event.channel == "life-project"
    assert event.confidence == 0.25
    assert event.correction_of == "project-appraisal:0"
    assert event.related_project_ids == ("project:one",)
    state = EmotionalJournal(path).current_state(
        now=NOW, subject="person:sparks", scope=scope,
    )
    assert max(item.intensity for item in state.active) <= 0.15


def test_emotion_metadata_is_part_of_idempotency_contract(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    fields = dict(
        event_id="event:one", source="observed", evidence_ref="receipt:one",
        description="A verified outcome.", emotions=("relief",),
        occurred_at=NOW, actor_id="sofia", channel="run", confidence=0.8,
    )
    journal.record(**fields)
    journal.record(**fields)
    with pytest.raises(ValueError, match="different evidence"):
        journal.record(**{**fields, "channel": "discord"})


def test_verified_life_outcome_influences_only_its_exact_audience(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    principal = local_sparks_principal("local:text")
    experience = ExperienceRecord(
        "experience:evaluated", "project:one", "artifact_evaluated",
        "Evaluated artifact: technically valid; personal judgment disliked.",
        ("evaluation:one",), principal.audience_id, True, NOW, NOW,
        {"technical_outcome": "valid", "personal_judgment": "disliked"},
    )
    event_id = journal.record_life_experience(experience, principal=principal)
    assert event_id == "life-affect:experience:evaluated"
    state = journal.current_state_for_principal(now=NOW, principal=principal)
    assert {item.name for item in state.active} >= {
        "disappointment", "curiosity", "determination",
    }
    other_audience = local_sparks_principal("discord:private")
    other = journal.current_state_for_principal(now=NOW, principal=other_audience)
    assert not other.active
    with pytest.raises(PermissionError, match="another audience"):
        journal.record_life_experience(experience, principal=other_audience)


def test_life_failure_or_inactivity_does_not_manufacture_negative_affect(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    principal = local_sparks_principal()
    experience = ExperienceRecord(
        "experience:paused", "project:one", "project_paused",
        "Optional project was paused.", ("decision:pause",),
        principal.audience_id, True, NOW, NOW, {},
    )
    assert journal.record_life_experience(experience, principal=principal) is None
    assert not journal.current_state_for_principal(
        now=NOW, principal=principal,
    ).active


def test_shared_audience_never_receives_private_relationship_affect(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    owner = local_sparks_principal()
    journal.record(
        event_id="private:emotion", source="user_reported",
        evidence_ref="private:message", description="Private relationship cue.",
        emotions=("affection",), occurred_at=NOW,
        subject=owner.principal_id, scope=owner.relationship_scope,
    )
    shared = PrincipalContext(
        owner.principal_id, "discord:shared-room",
        AudienceKind.SHARED, "Sparks",
    )
    assert not journal.current_state_for_principal(
        now=NOW, principal=shared,
    ).active
