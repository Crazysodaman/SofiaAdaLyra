"""Isolated module-owned ALPHA reviewer: MOD-DESKTOP-ACT."""
from .analysis import review_desktop_automation, capability_registrations as _act_registrations
from .receipts import reconcile_desktop_receipts, capability_registrations as _receipt_registrations


def capability_registrations():
    return _act_registrations() + _receipt_registrations()


__all__ = ['review_desktop_automation', 'reconcile_desktop_receipts',
           'capability_registrations']
