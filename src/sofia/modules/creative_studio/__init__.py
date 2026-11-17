"""Isolated module-owned ALPHA reviewer: MOD-CREATIVE."""
from .analysis import review_creative_studio, capability_registrations as _analysis_registrations
from .assets import validate_asset_manifest, capability_registrations as _asset_registrations


def capability_registrations():
    return _analysis_registrations() + _asset_registrations()


__all__ = ['review_creative_studio', 'validate_asset_manifest', 'capability_registrations']
