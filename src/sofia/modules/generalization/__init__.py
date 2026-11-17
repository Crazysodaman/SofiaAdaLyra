"""Isolated module-owned ALPHA reviewer: MOD-GENERALIZATION."""
from .analysis import review_generalization, capability_registrations as _analysis_registrations
from .transfer import validate_transfer_evidence, capability_registrations as _transfer_registrations


def capability_registrations():
    return _analysis_registrations() + _transfer_registrations()


__all__ = ['review_generalization', 'validate_transfer_evidence', 'capability_registrations']
