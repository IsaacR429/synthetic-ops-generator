from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.domain.enums import (
    Environment,
    OperationalState,
    RiskLevel,
    SourceDomain,
)
from synthetic_ops_generator.domain.resilience import (
    ServiceAvailabilityObservation,
    ServiceAvailabilityState,
)
from synthetic_ops_generator.generators.resilience import (
    ResilienceGenerator,
)
from synthetic_ops_generator.scenarios.context import (
    ScenarioContext,
    ScenarioExecutionTarget,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
)
from synthetic_ops_generator.scenarios.profile_contracts import (
    SERVICE_AVAILABLE,
    SERVICE_UNAVAILABLE,
    SUPPORTED_PROFILES_BY_SOURCE,
)


BASE_TIME = datetime(
    2026,
    10,
    19,
    10,
    0,
    tzinfo=UTC,
)


def _context(
    *,
    state: OperationalState,
    site_id: str = "bank_primary",
    instance_id: str = "payment_api_primary",
) -> ScenarioContext:
    return ScenarioContext(
        scenario_id="BANK-06-T3A2A",
        run_id="RUN-T3A2A-001",
        chg_id=None,
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        site_id=site_id,
        service_instance_id=instance_id,
        risk=RiskLevel.CRITICAL,
        scenario_state=state,
        simulation_time=BASE_TIME,
        random_seed=42,
    )


def _behaviour(
    *,
    profile_id: str,
    state: OperationalState,
) -> ScenarioBehaviour:
    return ScenarioBehaviour(
        behaviour_id=f"fixture_{profile_id}",
        source=SourceDomain.RESILIENCE,
        during_state=state,
        profile_id=profile_id,
    )


async def _collect(
    generator: ResilienceGenerator,
    context: ScenarioContext,
):
    return [
        event
        async for event in generator.generate(context)
    ]


def test_availability_profiles_are_registered_centrally() -> None:
    supported = SUPPORTED_PROFILES_BY_SOURCE[
        SourceDomain.RESILIENCE
    ]

    assert SERVICE_UNAVAILABLE in supported
    assert SERVICE_AVAILABLE in supported


@pytest.mark.parametrize(
    "profile_id, scenario_state, expected_state",
    [
        (
            SERVICE_UNAVAILABLE,
            OperationalState.FAILURE,
            ServiceAvailabilityState.UNAVAILABLE,
        ),
        (
            SERVICE_AVAILABLE,
            OperationalState.RECOVERY,
            ServiceAvailabilityState.AVAILABLE,
        ),
    ],
)
def test_availability_profile_emits_factual_observation(
    profile_id: str,
    scenario_state: OperationalState,
    expected_state: ServiceAvailabilityState,
) -> None:
    context = _context(
        state=scenario_state,
    )

    generator = ResilienceGenerator(
        ids=IdFactory(),
        behaviour=_behaviour(
            profile_id=profile_id,
            state=scenario_state,
        ),
    )

    events = asyncio.run(
        _collect(
            generator,
            context,
        )
    )

    assert len(events) == 1

    event = events[0]

    assert event.event_type == f"resilience.{profile_id}"
    assert event.source_domain == SourceDomain.RESILIENCE

    observation = (
        ServiceAvailabilityObservation.model_validate(
            event.data["service_availability_observation"]
        )
    )

    assert (
        observation.availability_state
        == expected_state
    )

    assert observation.service == "payment_service"
    assert observation.component == "payment_api"
    assert observation.site_id == "bank_primary"
    assert (
        observation.service_instance_id
        == "payment_api_primary"
    )

    assert observation.observed_at == BASE_TIME
    assert observation.observed_at == event.event_time


def test_available_profile_can_observe_secondary_instance() -> None:
    context = _context(
        state=OperationalState.RECOVERY,
        site_id="bank_secondary",
        instance_id="payment_api_secondary",
    )

    generator = ResilienceGenerator(
        ids=IdFactory(),
        behaviour=_behaviour(
            profile_id=SERVICE_AVAILABLE,
            state=OperationalState.RECOVERY,
        ),
    )

    event = asyncio.run(
        _collect(
            generator,
            context,
        )
    )[0]

    observation = (
        ServiceAvailabilityObservation.model_validate(
            event.data["service_availability_observation"]
        )
    )

    assert observation.site_id == "bank_secondary"
    assert (
        observation.service_instance_id
        == "payment_api_secondary"
    )


def test_availability_profile_rejects_transition_target() -> None:
    target = ScenarioExecutionTarget(
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        site_id="bank_secondary",
        service_instance_id="payment_api_secondary",
    )

    generator = ResilienceGenerator(
        ids=IdFactory(),
        behaviour=_behaviour(
            profile_id=SERVICE_UNAVAILABLE,
            state=OperationalState.FAILURE,
        ),
        transition_target=target,
    )

    with pytest.raises(
        ValueError,
        match=(
            "availability.*cannot use a transition target"
        ),
    ):
        asyncio.run(
            _collect(
                generator,
                _context(
                    state=OperationalState.FAILURE,
                ),
            )
        )


def test_availability_generator_does_not_run_outside_state() -> None:
    generator = ResilienceGenerator(
        ids=IdFactory(),
        behaviour=_behaviour(
            profile_id=SERVICE_UNAVAILABLE,
            state=OperationalState.FAILURE,
        ),
    )

    events = asyncio.run(
        _collect(
            generator,
            _context(
                state=OperationalState.REMEDIATION,
            ),
        )
    )

    assert events == []


def test_availability_payload_remains_factual_only() -> None:
    generator = ResilienceGenerator(
        ids=IdFactory(),
        behaviour=_behaviour(
            profile_id=SERVICE_AVAILABLE,
            state=OperationalState.RECOVERY,
        ),
    )

    event = asyncio.run(
        _collect(
            generator,
            _context(
                state=OperationalState.RECOVERY,
            ),
        )
    )[0]

    payload = event.data[
        "service_availability_observation"
    ]

    forbidden = {
        "recovery_duration",
        "rto_met",
        "rpo_met",
        "dr_success",
        "compliant",
        "blocking",
        "decision",
    }

    assert forbidden.isdisjoint(payload)
