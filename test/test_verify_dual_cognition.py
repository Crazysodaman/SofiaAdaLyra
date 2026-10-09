from sofia.cognition.routing import (
    CognitiveRoute,
    RoutingExecution,
    RoutingExecutionStep,
)
from sofia.verify.dual_cognition import assess_dual_cognition


def execution(
    route,
    *steps,
    fallback_count=0,
    verification_passes=0,
    serial=1,
):
    return RoutingExecution(
        serial=serial,
        route=route,
        steps=tuple(steps),
        fallback_count=fallback_count,
        verification_passes=verification_passes,
    )


def step(role, model, host="venus", succeeded=True):
    return RoutingExecutionStep(
        role=role,
        model=model,
        host=host,
        succeeded=succeeded,
    )


def test_dual_cognition_canary_accepts_expected_live_paths():
    primary = "owner/primary:9b"
    secondary = "owner/secondary:4b"

    result = assess_dual_cognition(
        primary_model=primary,
        secondary_model=secondary,
        fast=execution(
            CognitiveRoute.FAST,
            step("secondary", secondary),
        ),
        deep=execution(
            CognitiveRoute.DEEP,
            step("primary", primary),
            step("secondary", secondary),
            step("primary", primary),
            verification_passes=2,
        ),
        verify=execution(
            CognitiveRoute.VERIFY,
            step("primary", primary),
            step("secondary", secondary),
            step("primary", primary),
            verification_passes=2,
        ),
    )

    assert result.accepted is True
    assert result.failures == ()
    payload = result.payload()
    assert payload["accepted"] is True
    assert [item["role"] for item in payload["verify"]["steps"]] == [
        "primary",
        "secondary",
        "primary",
    ]


def test_dual_cognition_canary_rejects_fallback_or_wrong_model_path():
    primary = "owner/primary:9b"
    secondary = "owner/secondary:4b"

    result = assess_dual_cognition(
        primary_model=primary,
        secondary_model=secondary,
        fast=execution(
            CognitiveRoute.FAST,
            step("secondary", secondary, succeeded=False),
            step("primary", primary),
            fallback_count=1,
        ),
        deep=execution(
            CognitiveRoute.DEEP,
            step("primary", primary),
            step("secondary", secondary),
            step("primary", primary),
            verification_passes=2,
        ),
        verify=execution(
            CognitiveRoute.VERIFY,
            step("primary", primary),
            step("primary", primary),
            verification_passes=1,
        ),
    )

    assert result.accepted is False
    assert "fast_fallback_count=1" in result.failures
    assert "fast_contains_failed_model_call" in result.failures
    assert any(item.startswith("verify_roles=") for item in result.failures)
    assert any(
        item.startswith("verify_verification_passes=")
        for item in result.failures
    )


def test_dual_cognition_canary_requires_distinct_model_roles():
    model = "owner/same:9b"

    result = assess_dual_cognition(
        primary_model=model,
        secondary_model=model,
        fast=execution(
            CognitiveRoute.FAST,
            step("secondary", model),
        ),
        deep=execution(
            CognitiveRoute.DEEP,
            step("primary", model),
            step("secondary", model),
            step("primary", model),
            verification_passes=2,
        ),
        verify=execution(
            CognitiveRoute.VERIFY,
            step("primary", model),
            step("secondary", model),
            step("primary", model),
            verification_passes=2,
        ),
    )

    assert result.accepted is False
    assert "primary_and_secondary_models_are_not_distinct" in result.failures
