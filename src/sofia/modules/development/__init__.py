"""Isolated module-owned ALPHA reviewer: MOD-DEV."""
from .analysis import review_development, capability_registrations as _analysis_registrations
from .changes import validate_change_manifest, capability_registrations as _change_registrations


def capability_registrations():
    return _analysis_registrations() + _change_registrations()


__all__ = ['review_development', 'validate_change_manifest', 'capability_registrations']
