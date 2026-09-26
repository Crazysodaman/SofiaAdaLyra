import pytest

from sofia.ui.delivery import (
    ExpressionDelivery,
    PresentationChannel,
    PresentationStatus,
)


def test_delivery_distinguishes_planned_from_acknowledged():
    delivery = ExpressionDelivery(
        planned_channels=(
            PresentationChannel.TEXT,
            PresentationChannel.AVATAR,
        ),
        acknowledged_channels=(
            PresentationChannel.TEXT,
        ),
    )

    assert delivery.status(
        PresentationChannel.TEXT
    ) is PresentationStatus.REPORTED_ACKNOWLEDGED_UNVERIFIED
    assert delivery.status(
        PresentationChannel.AVATAR
    ) is PresentationStatus.PENDING
    assert delivery.status(
        PresentationChannel.VOICE
    ) is PresentationStatus.NOT_REQUESTED


def test_delivery_rejects_unplanned_acknowledgement():
    with pytest.raises(ValueError):
        ExpressionDelivery(
            planned_channels=(PresentationChannel.TEXT,),
            acknowledged_channels=(PresentationChannel.VOICE,),
        )


def test_delivery_rejects_duplicate_channels():
    with pytest.raises(ValueError):
        ExpressionDelivery(
            planned_channels=(
                PresentationChannel.TEXT,
                PresentationChannel.TEXT,
            )
        )


def test_delivery_status_requires_typed_channel():
    delivery = ExpressionDelivery(
        planned_channels=(PresentationChannel.TEXT,)
    )

    with pytest.raises(TypeError):
        delivery.status("text")
