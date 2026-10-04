"""Conversation routing for generated garments."""
from sofia.avatar.authoring import GarmentDesignRequest, WardrobeStudio
from sofia.avatar.generation_conversation import (
    WardrobeGenerationConversationService,
)
from sofia.avatar.generated_proposal import GarmentGenerationBrief
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.avatar.wardrobe_design import ContentRating, GraphicDesign
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.principals import local_sparks_principal
from sofia.avatar.wardrobe_generated_store import (
    GarmentAcceptanceResult,
    SofiaGarmentDecision,
)


def _blueprint():
    return WardrobeStudio(build_starter_wardrobe()).design_piece(
        GarmentDesignRequest(
            item_id="generated.sofia.chat_tee",
            name="Chat Violet Tee",
            garment_type="t_shirt",
            fit="relaxed",
            rise=None,
            length="hip",
            sleeve_length="short",
            material="soft cotton-modal knit",
            primary="dark_violet",
            accent="cyan",
            pattern="solid",
            graphic=GraphicDesign(),
            features=("soft_hem",),
            style_tags=("casual", "violet"),
            description="A soft violet tee generated from a conversation brief.",
        )
    )


def test_direct_generation_request_reaches_pipeline_and_reports_acceptance():
    seen = []

    def generate(brief):
        seen.append(brief)
        return (
            _blueprint(),
            GarmentAcceptanceResult(
                SofiaGarmentDecision.ACCEPT,
                True,
                False,
                "I like the casual violet design enough to keep it.",
            ),
        )

    service = WardrobeGenerationConversationService(generate)
    reply = service.handle(
        content="design yourself a new soft violet tee with cyan trim"
    )

    assert len(seen) == 1
    assert seen[0].content_rating is ContentRating.STANDARD
    assert "Chat Violet Tee" in reply
    assert "want to keep it" in reply
    assert "part of my wardrobe" in reply


def test_unsure_generation_explicitly_asks_sparks_without_claiming_persistence():
    service = WardrobeGenerationConversationService(
        lambda brief: (
            _blueprint(),
            GarmentAcceptanceResult(
                SofiaGarmentDecision.ASK_SPARKS,
                False,
                True,
                "I like parts of it, but I am not sure I want to keep it.",
            ),
        )
    )

    reply = service.handle(
        content="make yourself a new violet tee"
    )

    assert "genuinely unsure" in reply
    assert "asking you before anything is added" in reply


def test_generation_parser_keeps_private_rating_host_owned():
    service = WardrobeGenerationConversationService(
        lambda brief: (_blueprint(), None)
    )

    brief = service.brief_for(
        "design yourself a new private lewd choker"
    )

    assert isinstance(brief, GarmentGenerationBrief)
    assert brief.content_rating is ContentRating.LEWD
    assert brief.private_only is True


def test_multi_question_generation_is_left_for_matrix_composition():
    service = WardrobeGenerationConversationService(
        lambda brief: (_blueprint(), None)
    )

    assert service.handle(
        content=(
            "design yourself a new violet tee, "
            "what time is it?"
        )
    ) is None


def test_non_wardrobe_make_request_is_not_hijacked():
    service = WardrobeGenerationConversationService(
        lambda brief: (_blueprint(), None)
    )

    assert service.handle(
        content="make the server faster"
    ) is None


def test_only_authenticated_sparks_can_resolve_pending_generation():
    blueprint = _blueprint()
    ask_result = GarmentAcceptanceResult(
        SofiaGarmentDecision.ASK_SPARKS,
        False,
        True,
        "I want Sparks' opinion before I decide.",
    )
    accepted = GarmentAcceptanceResult(
        SofiaGarmentDecision.ACCEPT,
        True,
        False,
        "After hearing Sparks, I want to keep it.",
    )
    resolved_inputs = []

    service = WardrobeGenerationConversationService(
        lambda brief: (blueprint, ask_result),
        resolve_pending=lambda value: (
            resolved_inputs.append(value) or (blueprint, accepted)
        ),
    )
    first = service.handle(
        content="design yourself a new violet tee"
    )
    assert "genuinely unsure" in first

    stranger = PrincipalContext(
        principal_id="person:someone-else",
        audience_id="shared:test",
        audience_kind=AudienceKind.SHARED,
    )
    assert service.handle(
        content="yeah keep it",
        previous_assistant_content=first,
        principal=stranger,
    ) is None
    assert resolved_inputs == []

    second = service.handle(
        content="yeah keep it",
        previous_assistant_content=first,
        principal=local_sparks_principal(),
    )
    assert resolved_inputs == ["yeah keep it"]
    assert "want to keep it" in second
    assert "part of my wardrobe" in second


def test_pending_followup_requires_immediately_previous_ask_reply():
    blueprint = _blueprint()
    called = []
    service = WardrobeGenerationConversationService(
        lambda brief: (
            blueprint,
            GarmentAcceptanceResult(
                SofiaGarmentDecision.ASK_SPARKS,
                False,
                True,
                "I am unsure.",
            ),
        ),
        resolve_pending=lambda value: (
            called.append(value) or None
        ),
    )

    assert service.handle(
        content="yes",
        previous_assistant_content="Sure, what else?",
        principal=local_sparks_principal(),
    ) is None
    assert called == []
