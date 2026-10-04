"""Live application wiring for Sofía-accepted generated wardrobe pieces."""
from pathlib import Path
from threading import RLock
from types import SimpleNamespace

from sofia.application.bootstrap import SofiaApplication
from sofia.avatar.authoring import GarmentDesignRequest, WardrobeStudio
from sofia.avatar.presentation_runtime import load_or_bootstrap_presentation
from sofia.avatar.wardrobe_design import GraphicDesign
from sofia.avatar.wardrobe_generated_store import (
    SofiaGarmentAcceptance,
    SofiaGarmentDecision,
)
from sofia.embodiment.store import EmbodimentStore


ROOT = Path(__file__).resolve().parents[1]
AVATAR_PATH = ROOT / "src" / "sofia" / "embodiment" / "avatar.json"


class _Runtime:
    def __init__(self, embodiment):
        self.embodiment = embodiment
        self.presentation = None
        self.matrix_builder = None

    def set_avatar_presentation(self, authority):
        self.presentation = authority

    def set_avatar_matrix_builder(self, builder):
        self.matrix_builder = builder


class _Conversation:
    def __init__(self):
        self.clothing_handler = None

    def set_clothing_action_handler(self, handler):
        self.clothing_handler = handler


def _draft(catalog):
    studio = WardrobeStudio(catalog)
    return studio.design_piece(
        GarmentDesignRequest(
            item_id="generated.sofia.live_refresh_tee",
            name="Live-refresh soft tee",
            garment_type="t_shirt",
            fit="relaxed",
            rise=None,
            length="hip",
            sleeve_length="short",
            material="soft cotton-modal knit",
            primary="black",
            accent="dark_violet",
            pattern="solid",
            graphic=GraphicDesign(),
            features=("soft_hem",),
            style_tags=("generated", "casual"),
            description=(
                "A generated soft black tee with violet trim used to verify "
                "live wardrobe ownership refresh."
            ),
        )
    )


def test_accepted_generated_piece_refreshes_live_application_bundle(tmp_path):
    state_path = tmp_path / "sofia.db"
    embodiment = EmbodimentStore(AVATAR_PATH).load()
    bundle = load_or_bootstrap_presentation(
        embodiment=embodiment,
        state_path=state_path,
    )

    app = object.__new__(SofiaApplication)
    app._model_lock = RLock()
    app._configuration = SimpleNamespace(
        state_path=state_path,
        avatar_private_adult_verified=False,
    )
    app._runtime = _Runtime(embodiment)
    app._conversation_service = _Conversation()
    app._presentation_bundle = bundle
    app._presentation_routine = None
    app._clothing_action_service = None

    result = app.decide_generated_wardrobe_piece(
        _draft(bundle.catalog),
        SofiaGarmentAcceptance(
            SofiaGarmentDecision.ACCEPT,
            "I like this enough to keep it in my wardrobe.",
        ),
    )

    assert result.persisted is True
    refreshed = app._presentation_bundle
    assert refreshed is not bundle
    assert any(
        blueprint.garment.item_id == "generated.sofia.live_refresh_tee"
        for blueprint in refreshed.catalog.blueprints
    )
    assert app._runtime.presentation is refreshed.authority
    assert callable(app._runtime.matrix_builder)
    assert callable(app._conversation_service.clothing_handler)


def test_unsure_generated_piece_does_not_refresh_or_persist(tmp_path):
    state_path = tmp_path / "sofia.db"
    embodiment = EmbodimentStore(AVATAR_PATH).load()
    bundle = load_or_bootstrap_presentation(
        embodiment=embodiment,
        state_path=state_path,
    )

    app = object.__new__(SofiaApplication)
    app._model_lock = RLock()
    app._configuration = SimpleNamespace(
        state_path=state_path,
        avatar_private_adult_verified=False,
    )
    app._runtime = _Runtime(embodiment)
    app._conversation_service = _Conversation()
    app._presentation_bundle = bundle
    app._presentation_routine = None
    app._clothing_action_service = None

    result = app.decide_generated_wardrobe_piece(
        _draft(bundle.catalog),
        SofiaGarmentAcceptance(
            SofiaGarmentDecision.ASK_SPARKS,
            "I am not sure whether I want to keep this one.",
        ),
    )

    assert result.ask_sparks is True
    assert result.persisted is False
    assert app._presentation_bundle is bundle
