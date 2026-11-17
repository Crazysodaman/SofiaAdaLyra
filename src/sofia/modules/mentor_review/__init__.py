"""Isolated module-owned ALPHA reviewer: MOD-MENTOR."""
from .analysis import review_mentor_review, capability_registrations as _analysis_registrations
from .independent import validate_review_evidence, capability_registrations as _review_registrations


def capability_registrations():
    return _analysis_registrations() + _review_registrations()


__all__ = ['review_mentor_review', 'validate_review_evidence', 'capability_registrations']
