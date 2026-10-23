"""Independent evidence-only quality assurance for Sofía.

No model-initiated commands, scheduler, DB writers or permission owner.
"""
from .audit import MentorAuditError, audit_checkout, compare_reports

__all__ = ["MentorAuditError", "audit_checkout", "compare_reports"]
