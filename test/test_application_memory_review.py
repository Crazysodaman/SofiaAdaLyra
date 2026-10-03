from types import SimpleNamespace
from uuid import uuid4

import pytest

from sofia.application.memory_review import MemoryReviewService
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.principals import local_sparks_principal


class CandidateStoreStub:
    def __init__(self):
        self.calls = []

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
