from datetime import datetime, timezone

import pytest

from sofia.personality.preferences import (
    PreferenceDisposition, PreferenceRegistry, PreferenceSubject,
)


NOW = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)
pytestmark = [pytest.mark.pkg_core, pytest.mark.pkg_rel]


def scope(subject=PreferenceSubject.SOFIA):
    return dict(
        subject=subject, category="decor.color", target_id="deep-violet",
        context="studio", audience_id="local:text",
    )


def test_preferences_preserve_subject_scope_evidence_and_revision_history(tmp_path):
    registry = PreferenceRegistry(tmp_path / "sofia.db")
    first = registry.revise(
        **scope(), disposition=PreferenceDisposition.LIKE, strength=.7,
        confidence=.8, reason="The palette fits my established presentation.",
        evidence_ref="reflection:color-1", expected_revision=None, now=NOW,
    )
    second = registry.revise(
        **scope(), disposition=PreferenceDisposition.FAVORITE, strength=.95,
        confidence=.9, reason="Repeated reviewed choices favored it.",
        evidence_ref="choice:color-2", expected_revision=1, now=NOW,
    )

    assert registry.current(**scope()) == second
    assert [item.disposition for item in registry.history(**scope())] == [
        PreferenceDisposition.LIKE, PreferenceDisposition.FAVORITE,
    ]
    assert first.evidence_ref != second.evidence_ref
    assert PreferenceRegistry(tmp_path / "sofia.db").current(**scope()) == second


def test_sofia_sparks_and_shared_preferences_never_collapse(tmp_path):
    registry = PreferenceRegistry(tmp_path / "sofia.db")
    for subject, disposition in (
        (PreferenceSubject.SOFIA, PreferenceDisposition.LIKE),
        (PreferenceSubject.SPARKS, PreferenceDisposition.DISLIKE),
        (PreferenceSubject.SHARED, PreferenceDisposition.INDIFFERENT),
    ):
        registry.revise(
            **scope(subject), disposition=disposition, strength=.6,
            confidence=.8, reason=f"Reviewed {subject.value} preference.",
            evidence_ref=f"evidence:{subject.value}", expected_revision=None, now=NOW,
        )
    assert registry.current(**scope(PreferenceSubject.SOFIA)).disposition is PreferenceDisposition.LIKE
    assert registry.current(**scope(PreferenceSubject.SPARKS)).disposition is PreferenceDisposition.DISLIKE
    assert registry.current(**scope(PreferenceSubject.SHARED)).disposition is PreferenceDisposition.INDIFFERENT


def test_only_positive_confident_preferences_influence_eligible_choices(tmp_path):
    registry = PreferenceRegistry(tmp_path / "sofia.db")
    for target, disposition, confidence in (
        ("violet", PreferenceDisposition.FAVORITE, .9),
        ("orange", PreferenceDisposition.STRONG_AVERSION, .99),
        ("green", PreferenceDisposition.LIKE, .3),
    ):
        registry.revise(
            subject=PreferenceSubject.SOFIA, category="decor.color",
            target_id=target, context="studio", disposition=disposition,
            strength=.8, confidence=confidence, reason="Reviewed fixture.",
            evidence_ref=f"evidence:{target}", audience_id="local:text",
            expected_revision=None, now=NOW,
        )
    assert [item.target_id for item in registry.eligible_choices(
        subject=PreferenceSubject.SOFIA, category="decor.color",
        context="studio", audience_id="local:text",
    )] == ["violet"]


def test_stale_preference_revision_cannot_overwrite(tmp_path):
    registry = PreferenceRegistry(tmp_path / "sofia.db")
    registry.revise(
        **scope(), disposition=PreferenceDisposition.LIKE, strength=.5,
        confidence=.7, reason="Reviewed.", evidence_ref="evidence:1",
        expected_revision=None, now=NOW,
    )
    with pytest.raises(RuntimeError, match="revision changed"):
        registry.revise(
            **scope(), disposition=PreferenceDisposition.DISLIKE, strength=.5,
            confidence=.7, reason="Stale.", evidence_ref="evidence:2",
            expected_revision=None, now=NOW,
        )
