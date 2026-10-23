from types import SimpleNamespace
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sofia.platform.application.memory_review import MemoryReviewService
from sofia.core.memory.originals import SourceMessage
from sofia.core.memory.provenance import MemoryCandidate
from sofia.core.social.model import AudienceKind, PrincipalContext
from sofia.core.social.principals import local_sparks_principal


class CandidateStoreStub:
    def __init__(self):
        self.calls = []
        self.original_checks = []

    def get(self, candidate_id):
        reviewer = local_sparks_principal()
        now = datetime(2026, 10, 12, tzinfo=timezone.utc)
        return MemoryCandidate(
            candidate_id=candidate_id,
            content="Synthetic evidence-bound fact",
            sources=(SourceMessage(
                "fixture-message", "fixture-session", "user",
                "Synthetic original text", now, 0,
            ),),
            created_at=now,
            principal_id=reviewer.principal_id,
            audience_id=reviewer.audience_id,
        )

    def require_current_original_at_recall(self, candidate_id, **scope):
        self.original_checks.append((candidate_id, scope))

    def promote(self, candidate_id):
        self.calls.append(("promote", candidate_id))

    def reject(self, candidate_id):
        self.calls.append(("reject", candidate_id))

    def revoke(self, candidate_id):
        self.calls.append(("revoke", candidate_id))


def service_with_stub():
    service = object.__new__(MemoryReviewService)
    service._candidates = CandidateStoreStub()
    service._workflow = SimpleNamespace()
    service._social = SimpleNamespace(
        get=lambda session_id: local_sparks_principal(),
    )
    service._originals = SimpleNamespace(
        retrieve=lambda request: SimpleNamespace(
            selected=service._candidates.get(uuid4()).sources,
            missing_ids=(),
            omitted_ids=(),
        ),
    )
    return service


def test_memory_review_rejects_display_name_string_as_authority():
    service = service_with_stub()

    with pytest.raises(TypeError, match="PrincipalContext"):
        service.promote(
            uuid4(),
            approved_by="Sparks",
        )

    assert service._candidates.calls == []


def test_memory_review_requires_private_authenticated_sparks_principal():
    service = service_with_stub()
    candidate_id = uuid4()

    shared = PrincipalContext(
        principal_id="person:sparks",
        audience_id="shared:test",
        audience_kind=AudienceKind.SHARED,
        display_name="Sparks",
    )

    with pytest.raises(PermissionError, match="private Sparks"):
        service.promote(
            candidate_id,
            approved_by=shared,
        )

    reviewer = local_sparks_principal()
    service.promote(candidate_id, approved_by=reviewer)
    service.reject(candidate_id, approved_by=reviewer)
    service.revoke(candidate_id, approved_by=reviewer)

    assert service._candidates.calls == [
        ("promote", candidate_id),
        ("reject", candidate_id),
        ("revoke", candidate_id),
    ]
    assert len(service._candidates.original_checks) == 1
    assert service._candidates.original_checks[0][0] == candidate_id
