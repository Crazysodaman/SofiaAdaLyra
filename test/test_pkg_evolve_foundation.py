import pytest

from sofia.package_foundations.evolve import AmendmentDomain, AmendmentProposal


def test_protected_changes_require_procedure_and_never_self_apply():
    for domain in (AmendmentDomain.CONSTITUTION, AmendmentDomain.PROTECTED_IDENTITY):
        proposal = AmendmentProposal(domain, 'a' * 64, 'Review change', ('evidence-1',))
        assert proposal.protected_procedure_required
        assert not proposal.automatically_applicable


def test_mutable_changes_are_still_not_automatically_applied():
    proposal = AmendmentProposal(AmendmentDomain.MUTABLE_PREFERENCE,
                                 'b' * 64, 'Review preference', ('evidence-2',))
    assert not proposal.protected_procedure_required
    assert not proposal.automatically_applicable


def test_unpinned_source_rejected():
    with pytest.raises(ValueError):
        AmendmentProposal(AmendmentDomain.CONSTITUTION, 'unknown', 'change', ('evidence-1',))
