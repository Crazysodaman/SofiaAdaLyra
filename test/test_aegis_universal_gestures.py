"""UC-03..UC-06 universal gesture, personal boundary and playback receipts."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from uuid import UUID

import pytest

from sofia.core.multicore.gestures import (
    DuplicateGestureVariant,
    GestureLibrary,
    GestureLibraryError,
    GestureUsePreference,
    InMemoryGestureRepository,
    OwnerPrivateGestureStore,
    PersonalGestureVariant,
    share_personal_gesture,
)
from sofia.modules.interaction import registry as legacy
from sofia.modules.interaction.core import GESTURES as LIVE_GESTURES
from sofia.modules.interaction.gesture_catalog import (
    DEFAULT_GESTURE_CATALOG,
    GestureCatalogError,
    InteractionGestureCatalog,
)
from sofia.sdk.core_capabilities import (
    BodyCapability,
    BodyCapabilityProfile,
    CapabilityOutcome,
    RendererCapability,
)
from sofia.sdk.gesture_contract import (
    ADULT_REVIEWED_POLICY,
    AdultEligibility,
    AdultSceneRequest,
    GestureClass,
    GestureCompatibilityStatus,
    GestureDefinition,
    GestureError,
    GestureEvidence,
    GestureExecution,
    GestureParty,
    GesturePlaybackReceipt,
    GesturePrivacy,
    GestureStateError,
    IntimacyDimensions,
    SceneAudience,
    evaluate_adult_scene,
    resolve_gesture_compatibility,
)

SOFIA_ID = UUID("4d1b7a5c-6e8f-4081-acb3-be2f3a4b5c6d")
MACK_ID = UUID("2b9f5e3a-4c6d-4e7f-8a91-9c0d1e2f3a4b")
NOVA_ID = UUID("3c0a6f4b-5d7e-4f80-9ba2-ad1e2f3a4b5c")
VERA_ID = UUID("6f3d9c80-8a1b-4c2d-9e4f-5a6b7c8d9e0f")
NOW = datetime(2026, 11, 18, 18, 30, tzinfo=timezone.utc)


def _personal_definition() -> GestureDefinition:
    return GestureDefinition(
        gesture_id="sofia-tail-flick",
        version=1,
        gesture_class=GestureClass.PERSONAL,
        actor=GestureParty.core(SOFIA_ID),
        target=GestureParty.any_core(),
        required_body=(BodyCapability.FOX_TAIL,),
        renderer_capabilities=(RendererCapability.TEXT,),
        privacy=GesturePrivacy.PRIVATE,
        provenance="aegis.test.personal.v1",
        aliases=("tail flick", "personal tail flick"),
        semantic_parameters={"style": "distinctive"},
    )


def test_uc03_anatomy_specific_motion_is_rejected_for_human_only_rig():
    human = BodyCapabilityProfile.human_only()
    sofia_body = BodyCapabilityProfile.sofia_fox()
    wave = DEFAULT_GESTURE_CATALOG.entry("gesture", "wave").definition
    ears = DEFAULT_GESTURE_CATALOG.entry("expression", "ear-perk").definition
    tail = DEFAULT_GESTURE_CATALOG.entry("expression", "tail-swish").definition

    assert wave.gesture_class is GestureClass.UNIVERSAL
    assert resolve_gesture_compatibility(
        wave, body=human, renderers=(RendererCapability.TEXT,)
    ).accepted

    for anatomy in (ears, tail):
        assert anatomy.gesture_class is GestureClass.ANATOMY_SPECIFIC
        rejected = resolve_gesture_compatibility(
            anatomy, body=human, renderers=(RendererCapability.TEXT,)
        )
        assert rejected.status is GestureCompatibilityStatus.ANATOMY_MISMATCH
        assert rejected.accepted is False
        assert rejected.definition.gesture_id == anatomy.gesture_id
        assert rejected.missing_body
        assert "anatomy" in rejected.reason

        accepted = resolve_gesture_compatibility(
            anatomy, body=sofia_body, renderers=(RendererCapability.TEXT,)
        )
        assert accepted.accepted is True

    assert ears.required_body == (BodyCapability.FOX_EARS,)
    assert tail.required_body == (BodyCapability.FOX_TAIL,)
    assert ears.gesture_id != "touch"


def test_uc03_unavailable_renderer_never_becomes_textual_playback():
    wave = DEFAULT_GESTURE_CATALOG.entry("gesture", "wave").definition
    result = resolve_gesture_compatibility(
        wave, body=BodyCapabilityProfile.human_only(), renderers=()
    )
    assert result.status is GestureCompatibilityStatus.RENDERER_UNAVAILABLE
    assert result.accepted is False
    assert result.missing_renderers == (RendererCapability.TEXT,)


def _learned_sofia_library() -> tuple[GestureLibrary, PersonalGestureVariant]:
    library = GestureLibrary.empty(SOFIA_ID)
    variant_id = UUID("8a4e0d21-9b3c-4d5e-8f6a-7b8c9d0e1f2a")
    library = library.learn(
        _personal_definition(),
        style="gentle, quick",
        intensity=0.4,
        pacing=0.65,
        use=GestureUsePreference.WELCOMED,
        at=NOW,
        variant_id=variant_id,
    )
    return library, library.variant(variant_id)


def test_uc04_sharing_creates_new_nova_variant_without_mutating_origin():
    sofa_library, sofa_variant = _learned_sofia_library()
    original_preference = sofa_variant.preference
    original_digest = sofa_variant.digest
    original_count = len(sofa_library.variants)

    nova_library = GestureLibrary.empty(NOVA_ID)
    nova_library = share_personal_gesture(
        sofa_library,
        sofa_variant.variant_id,
        nova_library,
        at=NOW,
        style="precise",
        intensity=0.8,
        pacing=0.3,
        use=GestureUsePreference.NEUTRAL,
    )
    nova_variant = nova_library.variants_for("sofia-tail-flick")[0]

    assert nova_variant.variant_id != sofa_variant.variant_id
    assert nova_variant.owner_core_id == NOVA_ID
    assert nova_variant.preference.core_id == NOVA_ID
    assert nova_variant.preference.style == "precise"
    assert nova_variant.preference.intensity == 0.8
    assert nova_variant.preference.pacing == 0.3
    assert nova_variant.origin.origin_core_id == SOFIA_ID
    assert nova_variant.origin.origin_variant_id == sofa_variant.variant_id
    assert nova_variant.origin.origin_digest == sofa_variant.definition.digest
    assert nova_variant.origin.method is sofa_variant.origin.method
    assert nova_variant.origin == sofa_variant.origin

    assert len(sofa_library.variants) == original_count
    assert sofa_library.variant(sofa_variant.variant_id) == sofa_variant
    assert sofa_variant.preference == original_preference
    assert sofa_variant.digest == original_digest
    assert nova_variant.definition.digest == sofa_variant.definition.digest


def test_uc04_library_owner_isolation_and_duplicate_rejection():
    sofa_library, sofa_variant = _learned_sofia_library()
    with pytest.raises(GestureLibraryError):
        GestureLibrary(core_id=NOVA_ID, variants={sofa_variant.variant_id: sofa_variant})
    with pytest.raises(DuplicateGestureVariant):
        sofa_library.with_variant(sofa_variant)
    with pytest.raises(GestureLibraryError):
        sofa_library.teach(sofa_variant, at=NOW)


def test_uc04_injectable_and_owner_private_stores_round_trip(tmp_path):
    sofa_library, _ = _learned_sofia_library()
    memory = InMemoryGestureRepository()
    memory.save(sofa_library)
    assert memory.load(SOFIA_ID) == sofa_library
    assert memory.load(NOVA_ID) == GestureLibrary.empty(NOVA_ID)

    store = OwnerPrivateGestureStore(tmp_path / "gestures")
    store.save(sofa_library)
    assert store.load(SOFIA_ID) == sofa_library
    assert store.load(NOVA_ID).variants == {}
    on_disk = json.loads((tmp_path / "gestures" / f"{SOFIA_ID}.json").read_text("utf-8"))
    assert on_disk["schema"] == "aegis.core.gesture_library.v1"
    assert on_disk["core_id"] == str(SOFIA_ID)
    assert str(NOVA_ID) not in json.dumps(on_disk)


def _scene(
    *,
    audience: SceneAudience = SceneAudience.PRIVATE,
    actor_eligibility: AdultEligibility = AdultEligibility.ADULT,
    partner_eligibility: AdultEligibility = AdultEligibility.ADULT,
    actor_state: IntimacyDimensions | None = None,
    partner_state: IntimacyDimensions | None = None,
    policy: str = ADULT_REVIEWED_POLICY,
    actor_stop: bool = False,
    partner_stop: bool = False,
) -> AdultSceneRequest:
    willing = IntimacyDimensions(
        attraction=0.6, desire=0.5, arousal=0.4, comfort=0.9, willingness=True
    )
    return AdultSceneRequest(
        core_id=SOFIA_ID,
        partner_core_id=NOVA_ID,
        scene_ref="scene:private:1",
        audience=audience,
        actor_eligibility=actor_eligibility,
        partner_eligibility=partner_eligibility,
        actor_state=willing if actor_state is None else actor_state,
        partner_state=willing if partner_state is None else partner_state,
        occurred_at=NOW,
        policy=policy,
        actor_stop=actor_stop,
        partner_stop=partner_stop,
    )


def test_uc05_default_dimensions_do_not_automatically_consent_or_arouse():
    dimensions = IntimacyDimensions()
    assert dimensions.attraction == 0.0
    assert dimensions.desire == 0.0
    assert dimensions.arousal == 0.0
    assert dimensions.comfort == 0.0
    assert dimensions.willingness is False
    with pytest.raises(GestureError):
        IntimacyDimensions(arousal=1.1)


@pytest.mark.parametrize(
    "request_kwargs,expected",
    [
        ({"audience": SceneAudience.PUBLIC}, CapabilityOutcome.DECLINED),
        ({"actor_eligibility": AdultEligibility.UNKNOWN}, CapabilityOutcome.DECLINED),
        ({"partner_eligibility": AdultEligibility.MINOR}, CapabilityOutcome.DECLINED),
        ({"policy": "aegis.adult.unreviewed.v1"}, CapabilityOutcome.UNAVAILABLE),
        ({"partner_state": IntimacyDimensions()}, CapabilityOutcome.DECLINED),
        ({"actor_stop": True}, CapabilityOutcome.DECLINED),
        ({"partner_stop": True}, CapabilityOutcome.DECLINED),
    ],
)
def test_uc05_adult_gates_decline_or_unavailable_without_rendered_claim(
    request_kwargs, expected
):
    decision = evaluate_adult_scene(_scene(**request_kwargs))
    assert decision.outcome is expected
    assert decision.claims_playback is False
    assert decision.receipt.claims_playback is False
    assert decision.receipt.outcome is expected
    payload = json.dumps(decision.receipt.to_payload(), sort_keys=True)
    assert str(NOVA_ID) not in payload
    assert "scene:private:1" not in payload
    assert "rendered" not in payload


def test_uc05_bilateral_willingness_is_semantics_only_not_playback():
    decision = evaluate_adult_scene(_scene())
    assert decision.outcome is CapabilityOutcome.AUTHORIZED
    assert decision.allowed is True
    assert decision.claims_playback is False
    assert decision.receipt.claims_playback is False
    assert decision.receipt.reason_code == "reviewed_adult_semantics_authorized"
    assert "rendered" not in json.dumps(decision.receipt.to_payload())


def _wave() -> GestureDefinition:
    return DEFAULT_GESTURE_CATALOG.entry("gesture", "wave").definition


def _proposed() -> GestureExecution:
    return GestureExecution.propose(
        core_id=SOFIA_ID,
        definition=_wave(),
        event_ref="event:wave:1",
        generation=7,
        occurred_at=NOW,
    )


def test_uc06_authenticated_verified_renderer_yields_exact_playback_receipt():
    execution = _proposed()
    assert execution.outcome is CapabilityOutcome.PROPOSED
    assert execution.to_receipt().claims_playback is False

    with pytest.raises(GestureStateError):
        execution.authorize(authenticated=False, occurred_at=NOW)

    authorized = execution.authorize(authenticated=True, occurred_at=NOW)
    assert authorized.outcome is CapabilityOutcome.AUTHORIZED
    with pytest.raises(GestureStateError):
        authorized.queue(
            renderer=RendererCapability.TEXT,
            evidence=GestureEvidence.DESCRIPTION,
            occurred_at=NOW,
        )

    queued = authorized.queue(
        renderer=RendererCapability.TEXT,
        evidence=GestureEvidence.RENDERER,
        occurred_at=NOW,
    )
    with pytest.raises(GestureStateError):
        queued.render(
            asset_ref="asset:wave:1",
            evidence=GestureEvidence.DESCRIPTION,
            occurred_at=NOW,
        )

    rendered = queued.render(
        asset_ref="asset:wave:1",
        evidence=GestureEvidence.PLAYBACK,
        occurred_at=NOW,
    )
    receipt = rendered.to_receipt()
    assert receipt.outcome is CapabilityOutcome.RENDERED
    assert receipt.claims_playback is True
    assert receipt.event_ref == "event:wave:1"
    assert receipt.renderer is RendererCapability.TEXT
    assert receipt.asset_ref == "asset:wave:1"
    assert receipt.generation == 7
    assert receipt.stopped is False
    assert receipt.authenticated is True
    assert receipt.evidence is GestureEvidence.PLAYBACK
    assert receipt.gesture_id == "wave"
    assert receipt.gesture_version == 1
    assert "rendered" in receipt.to_payload()["outcome"]
    with pytest.raises(GestureStateError):
        rendered.cancel(reason="late STOP", occurred_at=NOW)


def test_uc06_description_is_not_playback_proof():
    receipt = _proposed().to_receipt()
    assert receipt.evidence is GestureEvidence.DESCRIPTION
    with pytest.raises(GestureError):
        GesturePlaybackReceipt(
            receipt_id=receipt.receipt_id,
            core_id=SOFIA_ID,
            gesture_id="wave",
            gesture_version=1,
            outcome=CapabilityOutcome.RENDERED,
            event_ref="event:wave:1",
            renderer=RendererCapability.TEXT,
            asset_ref="asset:wave:1",
            generation=1,
            stopped=False,
            authenticated=True,
            evidence=GestureEvidence.DESCRIPTION,
            reason="typed description",
            occurred_at=NOW,
        )


def test_uc06_stop_forbids_late_success_and_cancel_is_terminal():
    authorized = _proposed().authorize(authenticated=True, occurred_at=NOW)
    queued = authorized.queue(
        renderer=RendererCapability.TEXT,
        evidence=GestureEvidence.RENDERER,
        occurred_at=NOW,
    )
    canceled = queued.cancel(reason="participant STOP", occurred_at=NOW)
    receipt = canceled.to_receipt()
    assert receipt.outcome is CapabilityOutcome.CANCELED
    assert receipt.stopped is True
    assert receipt.claims_playback is False
    with pytest.raises(GestureStateError):
        canceled.render(
            asset_ref="asset:wave:1",
            evidence=GestureEvidence.PLAYBACK,
            occurred_at=NOW,
        )
    with pytest.raises(GestureStateError):
        _proposed().render(
            asset_ref="asset:wave:1",
            evidence=GestureEvidence.PLAYBACK,
            occurred_at=NOW,
        )


def test_uc06_direct_render_and_undeclared_renderer_are_rejected():
    with pytest.raises(GestureStateError):
        _proposed().queue(
            renderer=RendererCapability.THREE_D,
            evidence=GestureEvidence.RENDERER,
            occurred_at=NOW,
        )
    with pytest.raises(GestureStateError):
        _proposed().render(
            asset_ref="asset:wave:1",
            evidence=GestureEvidence.PLAYBACK,
            occurred_at=NOW,
        )
    unavailable = _proposed().unavailable(
        reason="renderer absent", occurred_at=NOW
    )
    assert unavailable.outcome is CapabilityOutcome.UNAVAILABLE
    assert unavailable.to_receipt().claims_playback is False


def test_uc06_decline_is_honest_and_never_rendered():
    declined = _proposed().decline(reason="not desired", occurred_at=NOW)
    receipt = declined.to_receipt()
    assert receipt.outcome is CapabilityOutcome.DECLINED
    assert receipt.claims_playback is False


def test_registry_bridge_preserves_legacy_vocabulary_and_classifies_entries():
    legacy_gestures = len(legacy.GESTURE_DEFINITIONS)
    legacy_actions = len(legacy.ACTION_DEFINITIONS)
    catalog = InteractionGestureCatalog()

    assert catalog.resolve("gesture", "rubbing") == "rub"
    assert catalog.resolve("action", "embrace") == "hug"
    assert catalog.resolve("expression", "ears perk") == "ear-perk"
    assert catalog.resolve("gesture", "hug") is None
    assert catalog.resolve("gesture", "unknown intimate act") is None
    assert catalog.entry("expression", "ear-perk").gesture_class is GestureClass.ANATOMY_SPECIFIC
    assert catalog.entry("expression", "tail-swish").required_body == (
        BodyCapability.FOX_TAIL,
    )
    assert catalog.entry("gesture", "intimate-touch").privacy is GesturePrivacy.ADULT_PRIVATE
    assert catalog.entry("action", "sexual-intercourse").privacy is GesturePrivacy.ADULT_PRIVATE
    assert catalog.entry("gesture", "wave").gesture_class is GestureClass.UNIVERSAL
    assert catalog.resolve("gesture", "waving") == "wave"
    assert catalog.entry("expression", "ear-perk").definition.provenance.startswith(
        legacy.CATALOG_VERSION
    )
    assert catalog.aliases_for("gesture")["pat"] == "pat"

    declared = catalog.declare(
        "gesture",
        "nova-finger-wiggle",
        aliases=("finger wiggle",),
        gesture_class=GestureClass.PERSONAL,
        privacy=GesturePrivacy.PRIVATE,
        provenance="aegis.test.personal.v1",
    )
    assert declared.gesture_class is GestureClass.PERSONAL
    assert catalog.personal() == (declared,)
    assert catalog.resolve("gesture", "finger wiggle") == "nova-finger-wiggle"

    assert len(legacy.GESTURE_DEFINITIONS) == legacy_gestures
    assert len(legacy.ACTION_DEFINITIONS) == legacy_actions
    assert "wave" not in LIVE_GESTURES
    assert "caress" not in LIVE_GESTURES


def test_registry_bridge_rejects_alias_collisions():
    catalog = InteractionGestureCatalog()
    with pytest.raises(GestureCatalogError):
        catalog.declare(
            "gesture",
            "touch",
            aliases=("pat",),
            gesture_class=GestureClass.UNIVERSAL,
        )
    with pytest.raises(GestureCatalogError):
        catalog.declare("not-a-category", "wave-2")
