"""Cognitive garment generation stays typed and separate from ownership."""
import pytest

from sofia.avatar.generated_proposal import (
    GarmentGenerationBrief,
    GeneratedGarmentProposalService,
)
from sofia.avatar.wardrobe import WardrobeError
from sofia.avatar.wardrobe_design import ContentRating
from sofia.cognition.model import CognitiveResponse


VALID_TEE = """{
  "slug": "violet_soft_tee",
  "name": "Violet Soft Tee",
  "garment_type": "t_shirt",
  "fit": "relaxed",
  "rise": null,
  "length": "hip",
  "sleeve_length": "short",
  "material": "soft cotton-modal knit",
  "primary": "dark_violet",
  "accent": "cyan",
  "pattern": "solid",
  "features": ["soft_hem"],
  "style_tags": ["casual", "soft", "violet"],
  "description": "A relaxed violet tee with a small cyan technical accent.",
  "exposure": []
}"""


def test_generated_proposal_builds_typed_request_without_ownership():
    captured = []

    def respond(request):
        captured.append(request)
        return CognitiveResponse(content=VALID_TEE)

    proposal = GeneratedGarmentProposalService(respond).generate(
        GarmentGenerationBrief(
            "Design a soft violet casual tee with a small cyan accent."
        )
    )

    assert proposal.item_id == "generated.sofia.violet_soft_tee"
    assert proposal.garment_type == "t_shirt"
    assert proposal.sleeve_length == "short"
    assert proposal.content_rating is ContentRating.STANDARD
    assert proposal.private_only is False
    assert len(captured) == 1
    request = captured[0]
    assert request.allow_tools is False
    assert request.capability_allowlist == ()
    assert "does NOT mean Sofía owns it" in request.messages[0].content


def test_generator_host_normalizes_fields_unsupported_by_type():
    content = VALID_TEE.replace(
        '"garment_type": "t_shirt"',
        '"garment_type": "tank_top"',
    )
    proposal = GeneratedGarmentProposalService.parse(
        content,
        GarmentGenerationBrief("Design a simple tank top."),
    )

    assert proposal.garment_type == "tank_top"
    assert proposal.sleeve_length is None
    assert proposal.rise is None


def test_private_rating_is_host_controlled():
    brief = GarmentGenerationBrief(
        "Design a private violet accessory.",
        content_rating=ContentRating.LEWD,
    )

    assert brief.private_only is True
    proposal = GeneratedGarmentProposalService.parse(
        VALID_TEE,
        brief,
    )
    assert proposal.private_only is True
    assert proposal.content_rating is ContentRating.LEWD


def test_non_explicit_generation_rejects_exposure():
    content = VALID_TEE.replace(
        '"exposure": []',
        '"exposure": ["nipples"]',
    )

    with pytest.raises(WardrobeError, match="cannot expose"):
        GeneratedGarmentProposalService.parse(
            content,
            GarmentGenerationBrief("Design a standard tee."),
        )


def test_generated_proposal_requires_exact_schema():
    with pytest.raises(WardrobeError, match="wrong schema"):
        GeneratedGarmentProposalService.parse(
            '{"slug":"incomplete"}',
            GarmentGenerationBrief("Design a tee."),
        )


def test_generator_uses_one_schema_repair_attempt():
    requests = []
    responses = iter(("{}", VALID_TEE))

    def respond(request):
        requests.append(request)
        return CognitiveResponse(content=next(responses))

    proposal = GeneratedGarmentProposalService(respond).generate(
        GarmentGenerationBrief("Design a violet tee.")
    )

    assert proposal.item_id == "generated.sofia.violet_soft_tee"
    assert len(requests) == 2
    repair_text = "\n".join(
        message.content
        for message in requests[1].messages
        if message.role.value == "system"
    )
    assert "WARDROBE DESIGN SCHEMA REPAIR" in repair_text


def test_generator_stops_after_failed_schema_repair():
    service = GeneratedGarmentProposalService(
        lambda request: CognitiveResponse(content="{}")
    )

    with pytest.raises(WardrobeError, match="after one repair"):
        service.generate(
            GarmentGenerationBrief("Design a violet tee.")
        )
