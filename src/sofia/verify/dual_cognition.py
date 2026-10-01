"""Live dual-LLM verification canary for Sofía production cognition.

This command exercises the already-composed production cognitive router without
creating conversation messages. It verifies that the configured primary and
secondary roles are distinct and that FAST, DEEP, and VERIFY execute the
expected model-role paths.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path

from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveRole,
)
from sofia.cognition.routing import (
    CognitiveRoute,
    RoutingCognitiveEngine,
    RoutingExecution,
)
from sofia.composition.root import compose
from sofia.config import create_production_configuration
from sofia.config.cognitive_models import CognitiveModelSelection


@dataclass(frozen=True, slots=True)
class DualCognitionCanary:
    primary_model: str
    secondary_model: str
    fast: RoutingExecution
    deep: RoutingExecution
    verify: RoutingExecution
    failures: tuple[str, ...]

    @property
    def accepted(self) -> bool:
        return not self.failures

    @staticmethod
    def _step_payload(execution: RoutingExecution) -> list[dict[str, object]]:
        return [
            {
                "role": step.role,
                "model": step.model,
                "host": step.host,
                "succeeded": step.succeeded,
            }
            for step in execution.steps
        ]

    def payload(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "primary_model": self.primary_model,
            "secondary_model": self.secondary_model,
            "fast": {
                "route": self.fast.route.value,
                "steps": self._step_payload(self.fast),
                "fallback_count": self.fast.fallback_count,
                "verification_passes": self.fast.verification_passes,
            },
            "deep": {
                "route": self.deep.route.value,
                "steps": self._step_payload(self.deep),
                "fallback_count": self.deep.fallback_count,
                "verification_passes": self.deep.verification_passes,
            },
            "verify": {
                "route": self.verify.route.value,
                "steps": self._step_payload(self.verify),
                "fallback_count": self.verify.fallback_count,
                "verification_passes": self.verify.verification_passes,
            },
            "failures": list(self.failures),
        }


def _request(route: str) -> CognitiveRequest:
    prompt = {
        "fast": "Reply briefly: FAST canary.",
        "deep": "Reply briefly: DEEP canary.",
        "verify": "Reply briefly: VERIFY canary.",
    }[route]
    return CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content=prompt,
            ),
        ),
        tools=(),
        allow_tools=False,
        route_hint=route,
    )


def _exercise(
    engine: RoutingCognitiveEngine,
    route: str,
) -> RoutingExecution:
    before = (
        0
        if engine.last_execution is None
        else engine.last_execution.serial
    )
    engine.respond(_request(route))
    execution = engine.last_execution
    if execution is None or execution.serial <= before:
        raise RuntimeError(
            f"{route} did not produce a fresh routing execution record"
        )
    return execution


def assess_dual_cognition(
    *,
    primary_model: str,
    secondary_model: str,
    fast: RoutingExecution,
    deep: RoutingExecution,
    verify: RoutingExecution,
) -> DualCognitionCanary:
    failures: list[str] = []

    if primary_model == secondary_model:
        failures.append("primary_and_secondary_models_are_not_distinct")

    expected = {
        "fast": (
            fast,
            CognitiveRoute.FAST,
            ("secondary",),
            (secondary_model,),
            0,
            0,
        ),
        "deep": (
            deep,
            CognitiveRoute.DEEP,
            ("primary",),
            (primary_model,),
            0,
            0,
        ),
        "verify": (
            verify,
            CognitiveRoute.VERIFY,
            ("primary", "secondary", "primary"),
            (primary_model, secondary_model, primary_model),
            0,
            2,
        ),
    }

    for name, (
        execution,
        route,
        roles,
        models,
        fallback_count,
        verification_passes,
    ) in expected.items():
        successful = execution.successful_steps
        actual_roles = tuple(step.role for step in successful)
        actual_models = tuple(step.model for step in successful)
        if execution.route is not route:
            failures.append(f"{name}_actual_route={execution.route.value}")
        if actual_roles != roles:
            failures.append(
                f"{name}_roles={'>' .join(actual_roles) or 'none'}"
            )
        if actual_models != models:
            failures.append(
                f"{name}_models="
                + ">".join(model or "unknown" for model in actual_models)
            )
        if execution.fallback_count != fallback_count:
            failures.append(
                f"{name}_fallback_count={execution.fallback_count}"
            )
        if execution.verification_passes != verification_passes:
            failures.append(
                f"{name}_verification_passes="
                f"{execution.verification_passes}"
            )
        if any(not step.succeeded for step in execution.steps):
            failures.append(f"{name}_contains_failed_model_call")

    return DualCognitionCanary(
        primary_model=primary_model,
        secondary_model=secondary_model,
        fast=fast,
        deep=deep,
        verify=verify,
        failures=tuple(failures),
    )


def run_live_canary(
    *,
    state_path: Path | None = None,
) -> DualCognitionCanary:
    configuration = create_production_configuration(
        **({} if state_path is None else {"state_path": state_path})
    )
    selection = CognitiveModelSelection.from_configuration(configuration)
    if not selection.routing_enabled or selection.secondary is None:
        raise RuntimeError(
            "production dual cognition is not enabled with both model roles"
        )

    runtime = compose(configuration)
    engine = runtime.cognitive_system.engine
    if not isinstance(engine, RoutingCognitiveEngine):
        raise RuntimeError(
            "production cognition did not compose RoutingCognitiveEngine"
        )

    fast = _exercise(engine, "fast")
    deep = _exercise(engine, "deep")
    verify = _exercise(engine, "verify")

    return assess_dual_cognition(
        primary_model=selection.primary.model,
        secondary_model=selection.secondary.model,
        fast=fast,
        deep=deep,
        verify=verify,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.verify.dual_cognition"
    )
    parser.add_argument(
        "--state-path",
        type=Path,
        default=None,
        help=(
            "Optional canonical sofia.db path. Omit to use production "
            "configuration."
        ),
    )
    parser.add_argument(
        "--evidence-path",
        type=Path,
        default=None,
        help="Optional path for JSON evidence output.",
    )
    args = parser.parse_args(argv)

    try:
        result = run_live_canary(state_path=args.state_path)
    except Exception as exc:
        payload = {
            "accepted": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        rendered = json.dumps(payload, indent=2, sort_keys=True)
        print(rendered)
        if args.evidence_path is not None:
            args.evidence_path.parent.mkdir(parents=True, exist_ok=True)
            args.evidence_path.write_text(rendered + "\n", encoding="utf-8")
        return 3

    rendered = json.dumps(result.payload(), indent=2, sort_keys=True)
    print(rendered)
    if args.evidence_path is not None:
        args.evidence_path.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_path.write_text(rendered + "\n", encoding="utf-8")
    return 0 if result.accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
