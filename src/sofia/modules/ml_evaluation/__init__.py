"""Isolated module-owned ALPHA reviewer: MOD-ML."""
from .analysis import review_ml_evaluation, capability_registrations as _analysis_registrations
from .evaluation import validate_evaluation_evidence, capability_registrations as _evaluation_registrations


def capability_registrations():
    return _analysis_registrations() + _evaluation_registrations()


__all__ = ['review_ml_evaluation', 'validate_evaluation_evidence', 'capability_registrations']
