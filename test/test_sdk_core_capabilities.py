"""UC-01/UC-02 universal Core capability contracts (source tests only)."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from uuid import UUID, uuid4

import pytest

from sofia.core.multicore.profiles import mack_core_profile
from sofia.sdk.core_capabilities import (
    BodyCapability,
    BodyCapabilityProfile,
    CapabilityError,
    CapabilityFamily,
    CapabilityOutcome,
    CapabilityReceipt,
    CapabilityState,
    CoreCapabilityContract,
    RendererCapability,
    derive_core_capability_contract,
    definition_digest_for,
    unavailable_receipt,
)

MACK_ID = UUID("2b9f5e3a-4c6d-4e7f-8a91-9c0d1e2f3a4b")
OTHER_ID = UUID("3c0a6f4b-5d7e-4f80-9ba2-ad1e2f3a4b5c")
NOW = datetime(2026, 11, 18, 18, 0, tzinfo=timezone.utc)


def _mack_definition(core_id: UUID = MACK_ID):
    profile = mack_core_profile(core_id)
    return profile.core_definition(revision=1, runtime_release_sha256="a" * 64)


def test_every_core_definition_gets_the_same_declared_interface():
    definition = _mack_definition()
    contract = derive_core_capability_contract(definition, core_number=2)

    assert contract.core_id == MACK_ID
    assert contract.core_number == 2
    assert contract.definition_digest == definition.digest
    assert set(contract.states) == set(CapabilityFamily)
    assert len(contract.states) == 16
    for family in CapabilityFamily:
        state = contract.state(family)
        assert state.declared is True
        assert state.installed is False
        assert state.available is False
        assert state.authorized is False
        assert state.effective is False
        assert contract.supports(family) is True
        assert contract.is_effective(family) is False


def test_two_cores_share_interface_without_cloning_uuid_or_state():
    first = derive_core_capability_contract(_mack_definition(MACK_ID), core_number=2)
    second = derive_core_capability_contract(
        _mack_definition(OTHER_ID), core_number=2
    )

    assert first.core_id != second.core_id
    assert first.states.keys() == second.states.keys()
    assert first.digest != second.digest
    for family in CapabilityFamily:
        assert first.state(family) == CapabilityState.declared_only()
        assert second.state(family) == CapabilityState.declared_only()
        assert first.state(family).effective is False
        assert second.state(family).effective is False


def test_profile_like_source_uses_supplied_identity_and_asset_digests():
    profile = mack_core_profile(MACK_ID)
    contract = derive_core_capability_contract(profile)

    assert contract.core_id == MACK_ID
    assert contract.core_number == 2
    assert contract.definition_digest == definition_digest_for(profile)
    assert len(contract.definition_digest) == 64
    with pytest.raises(CapabilityError):
        derive_core_capability_contract(profile, core_id=OTHER_ID)


def test_conflicting_or_missing_identity_is_rejected_not_substituted():
    definition = _mack_definition()
    with pytest.raises(CapabilityError):
        derive_core_capability_contract(
            definition, core_id=OTHER_ID, core_number=2
        )
    with pytest.raises(CapabilityError):
        derive_core_capability_contract(object(), core_number=2)
    with pytest.raises(CapabilityError):
        derive_core_capability_contract(definition)
    with pytest.raises(CapabilityError):
        derive_core_capability_contract(
            definition, core_number=2, definition_digest="A" * 64
        )


def test_body_and_anatomy_capability_predicates():
    human = BodyCapabilityProfile.human_only()
    sofia = BodyCapabilityProfile.sofia_fox()

    assert human.supports(BodyCapability.HUMAN_FORM)
    assert not human.supports(BodyCapability.FOX_EARS)
    assert human.missing(
        (BodyCapability.HUMAN_FORM, BodyCapability.FOX_TAIL)
    ) == (BodyCapability.FOX_TAIL,)
    assert sofia.supports_all(
        (
            BodyCapability.HUMAN_FORM,
            BodyCapability.FOX_EARS,
            BodyCapability.FOX_TAIL,
        )
    )
    with pytest.raises(CapabilityError):
        BodyCapabilityProfile(frozenset())
    with pytest.raises(CapabilityError):
        human.supports("fox_ears")  # type: ignore[arg-type]

    contract = derive_core_capability_contract(
        _mack_definition(), core_number=2
    )
    assert contract.body_supports(human, (BodyCapability.HUMAN_FORM,))
    assert not contract.body_supports(human, (BodyCapability.FOX_EARS,))


def test_text_core_starts_while_optional_rendering_is_unavailable():
    contract = CoreCapabilityContract.universal(
        core_id=MACK_ID,
        core_number=2,
        definition_digest="b" * 64,
        renderers=(RendererCapability.TEXT,),
    )
    assert contract.renderer_available(RendererCapability.TEXT)
    assert not contract.renderer_available(RendererCapability.THREE_D)
    assert not contract.renderer_available(RendererCapability.VTUBE)
    assert contract.supports(CapabilityFamily.CONVERSATION)
    assert contract.missing_renderers(
        (RendererCapability.TEXT, RendererCapability.THREE_D)
    ) == (RendererCapability.THREE_D,)

    voice = unavailable_receipt(
        receipt_id=uuid4(),
        core_id=MACK_ID,
        family=CapabilityFamily.VOICE,
        reason="optional voice assets are not installed",
        evidence_ref="install:text-only",
        occurred_at=NOW,
    )
    avatar = unavailable_receipt(
        receipt_id=uuid4(),
        core_id=MACK_ID,
        family=CapabilityFamily.AVATAR,
        reason="no verified avatar renderer or asset is available",
        evidence_ref="install:text-only",
        occurred_at=NOW,
        renderer=RendererCapability.THREE_D,
    )
    sexual = unavailable_receipt(
        receipt_id=uuid4(),
        core_id=MACK_ID,
        family=CapabilityFamily.SEXUALITY,
        reason="no reviewed adult renderer surface is available",
        evidence_ref="install:text-only",
        occurred_at=NOW,
        renderer=RendererCapability.TWO_D,
    )

    for receipt in (voice, avatar, sexual):
        assert receipt.outcome is CapabilityOutcome.UNAVAILABLE
        assert receipt.claims_rendered is False
        assert receipt.core_id == MACK_ID
    assert json.loads(json.dumps(avatar.to_payload()))["outcome"] == "unavailable"
    assert CapabilityReceipt.from_payload(avatar.to_payload()) == avatar


def test_effective_state_cannot_be_claimed_from_declaration_alone():
    contract = CoreCapabilityContract.universal(
        core_id=MACK_ID,
        core_number=2,
        definition_digest="c" * 64,
    )
    with pytest.raises(CapabilityError):
        CapabilityState(
            declared=True,
            installed=False,
            available=False,
            authorized=False,
            effective=True,
        )
    updated = contract.with_state(
        CapabilityFamily.GESTURE,
        CapabilityState(declared=True, installed=True, available=True),
    )
    assert updated.is_effective(CapabilityFamily.GESTURE) is False
    assert updated.revision == contract.revision + 1
