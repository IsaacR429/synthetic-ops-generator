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
    ResilienceObservation,
    ResilienceObservationType,
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
    FAILOVER_INITIATED,
    INSTANCE_ACTIVATED,
    INSTANCE_SERVING,
    REPLICATION_OBSERVED,
    SERVICE_AVAILABLE,
    SERVICE_UNAVAILABLE,
    SUPPORTED_PROFILES_BY_SOURCE,
    TRAFFIC_SWITCH_COMPLETED,
    TRAFFIC_SWITCH_STARTED,
)


BASE_TIME = datetime(
    2026,
    10,
    11,
    22,
    0,
    tzinfo=UTC,
)


RESILIENCE_PROFILES = frozenset(
    {
        FAILOVER_INITIATED,
        TRAFFIC_SWITCH_STARTED,
        TRAFFIC_SWITCH_COMPLETED,
        INSTANCE_ACTIVATED,
        INSTANCE_SERVING,
        SERVICE_UNAVAILABLE,
        SERVICE_AVAILABLE,
        REPLICATION_OBSERVED,
    }
)


TRANSITION_PROFILES = (
    FAILOVER_INITIATED,
    TRAFFIC_SWITCH_STARTED,
    TRAFFIC_SWITCH_COMPLETED,
)


INSTANCE_STATE_PROFILES = (
    INSTANCE_ACTIVATED,
    INSTANCE_SERVING,
)


def build_primary_context(
    *,
    state: OperationalState = OperationalState.REMEDIATION,
    chg_id: str | None = None,
) -> ScenarioContext:
    return ScenarioContext(
        scenario_id="BANK-06-TEST",
        run_id="RUN0000001",
        chg_id=chg_id,
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        site_id="bank_primary",
        service_instance_id="payment_api_primary",
        risk=RiskLevel.CRITICAL,
        scenario_state=state,
        simulation_time=BASE_TIME,
        random_seed=42,
    )


def build_secondary_context(
    *,
    state: OperationalState = OperationalState.REMEDIATION,
) -> ScenarioContext:
    return ScenarioContext(
        scenario_id="BANK-06-TEST",
        run_id="RUN0000001",
        chg_id=None,
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        site_id="bank_secondary",
        service_instance_id="payment_api_secondary",
        risk=RiskLevel.CRITICAL,
        scenario_state=state,
        simulation_time=BASE_TIME,
        random_seed=42,
    )


def build_secondary_target() -> ScenarioExecutionTarget:
    return ScenarioExecutionTarget(
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        site_id="bank_secondary",
        service_instance_id="payment_api_secondary",
    )


def build_behaviour(
    profile_id: str = FAILOVER_INITIATED,
) -> ScenarioBehaviour:
    return ScenarioBehaviour(
        behaviour_id="fixture_test_resilience_generator_01",
        source=SourceDomain.RESILIENCE,
        during_state=OperationalState.REMEDIATION,
        profile_id=profile_id,
    )


async def collect_events(
    generator: ResilienceGenerator,
    context: ScenarioContext,
):
    return [
        event
        async for event in generator.generate(context)
    ]


def test_resilience_profiles_are_registered_centrally() -> None:
    assert (
        SUPPORTED_PROFILES_BY_SOURCE[
            SourceDomain.RESILIENCE
        ]
        == RESILIENCE_PROFILES
    )


def test_resilience_observation_ids_use_central_factory() -> None:
    ids = IdFactory()

    assert (
        ids.resilience_observation_id()
        == "RSO0000001"
    )
    assert (
        ids.resilience_observation_id()
        == "RSO0000002"
    )


@pytest.mark.parametrize(
    "profile_id, observation_type",
    [
        (
            FAILOVER_INITIATED,
            ResilienceObservationType.FAILOVER_INITIATED,
        ),
        (
            TRAFFIC_SWITCH_STARTED,
            ResilienceObservationType.TRAFFIC_SWITCH_STARTED,
        ),
        (
            TRAFFIC_SWITCH_COMPLETED,
            ResilienceObservationType.TRAFFIC_SWITCH_COMPLETED,
        ),
    ],
)
def test_transition_profile_emits_factual_transition(
    profile_id: str,
    observation_type: ResilienceObservationType,
) -> None:
    context = build_primary_context()

    generator = ResilienceGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(profile_id),
        transition_target=build_secondary_target(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            context,
        )
    )

    assert len(events) == 1

    event = events[0]

    assert event.event_type == f"resilience.{profile_id}"
    assert event.source_system == "synthetic_resilience"
    assert event.source_domain == SourceDomain.RESILIENCE

    assert event.site_id == "bank_primary"
    assert (
        event.service_instance_id
        == "payment_api_primary"
    )

    observation = ResilienceObservation.model_validate(
        event.data["resilience_observation"]
    )

    assert observation.observation_type == observation_type

    assert observation.from_site_id == "bank_primary"
    assert (
        observation.from_service_instance_id
        == "payment_api_primary"
    )

    assert observation.to_site_id == "bank_secondary"
    assert (
        observation.to_service_instance_id
        == "payment_api_secondary"
    )


@pytest.mark.parametrize(
    "profile_id, observation_type",
    [
        (
            INSTANCE_ACTIVATED,
            ResilienceObservationType.INSTANCE_ACTIVATED,
        ),
        (
            INSTANCE_SERVING,
            ResilienceObservationType.INSTANCE_SERVING,
        ),
    ],
)
def test_instance_state_profile_observes_current_instance(
    profile_id: str,
    observation_type: ResilienceObservationType,
) -> None:
    context = build_secondary_context()

    generator = ResilienceGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(profile_id),
    )

    events = asyncio.run(
        collect_events(
            generator,
            context,
        )
    )

    assert len(events) == 1

    event = events[0]

    assert event.site_id == "bank_secondary"
    assert (
        event.service_instance_id
        == "payment_api_secondary"
    )

    observation = ResilienceObservation.model_validate(
        event.data["resilience_observation"]
    )

    assert observation.observation_type == observation_type

    assert observation.from_site_id is None
    assert observation.from_service_instance_id is None

    assert observation.to_site_id == "bank_secondary"
    assert (
        observation.to_service_instance_id
        == "payment_api_secondary"
    )


def test_transition_profile_requires_resolved_peer_target() -> None:
    generator = ResilienceGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(
            FAILOVER_INITIATED
        ),
    )

    with pytest.raises(
        ValueError,
        match=(
            "Resilience transition profile requires "
            "a transition target"
        ),
    ):
        asyncio.run(
            collect_events(
                generator,
                build_primary_context(),
            )
        )


def test_instance_state_profile_rejects_transition_target() -> None:
    generator = ResilienceGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(
            INSTANCE_SERVING
        ),
        transition_target=build_secondary_target(),
    )

    with pytest.raises(
        ValueError,
        match=(
            "Instance-state Resilience profile "
            "cannot use a transition target"
        ),
    ):
        asyncio.run(
            collect_events(
                generator,
                build_secondary_context(),
            )
        )


def test_resilience_event_preserves_run_and_service_correlation() -> None:
    context = build_primary_context(
        chg_id="CHG0000001"
    )

    generator = ResilienceGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        transition_target=build_secondary_target(),
    )

    event = asyncio.run(
        collect_events(
            generator,
            context,
        )
    )[0]

    assert event.scenario_id == "BANK-06-TEST"
    assert event.run_id == "RUN0000001"
    assert event.chg_id == "CHG0000001"

    assert event.business_stream == "payments"
    assert event.service == "payment_service"
    assert event.component == "payment_api"
    assert event.environment == Environment.PRODUCTION


def test_resilience_observation_uses_central_id() -> None:
    generator = ResilienceGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        transition_target=build_secondary_target(),
    )

    event = asyncio.run(
        collect_events(
            generator,
            build_primary_context(),
        )
    )[0]

    assert (
        event.data["resilience_observation"][
            "observation_id"
        ]
        == "RSO0000001"
    )


def test_resilience_observation_timestamp_matches_event_time() -> None:
    generator = ResilienceGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        transition_target=build_secondary_target(),
    )

    event = asyncio.run(
        collect_events(
            generator,
            build_primary_context(),
        )
    )[0]

    observation = ResilienceObservation.model_validate(
        event.data["resilience_observation"]
    )

    assert observation.observed_at == event.event_time
    assert event.event_time == BASE_TIME


def test_resilience_event_uses_scenario_sequence() -> None:
    context = build_primary_context()

    generator = ResilienceGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        transition_target=build_secondary_target(),
    )

    event = asyncio.run(
        collect_events(
            generator,
            context,
        )
    )[0]

    assert event.sequence_number == 1
    assert context.sequence_number == 1


def test_generator_does_not_run_outside_behaviour_state() -> None:
    context = build_primary_context(
        state=OperationalState.FAILURE
    )

    generator = ResilienceGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        transition_target=build_secondary_target(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            context,
        )
    )

    assert events == []
    assert context.sequence_number == 0


def test_generator_rejects_wrong_source_domain() -> None:
    behaviour = ScenarioBehaviour(
        behaviour_id="fixture_test_resilience_generator_02",
        source=SourceDomain.LOG,
        during_state=OperationalState.REMEDIATION,
        profile_id=FAILOVER_INITIATED,
    )

    with pytest.raises(
        ValueError,
        match="requires a Resilience behaviour",
    ):
        ResilienceGenerator(
            ids=IdFactory(),
            behaviour=behaviour,
            transition_target=build_secondary_target(),
        )


def test_generator_rejects_unknown_profile() -> None:
    generator = ResilienceGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(
            "unknown_resilience_profile"
        ),
        transition_target=build_secondary_target(),
    )

    with pytest.raises(
        ValueError,
        match="Unsupported Resilience behaviour profile",
    ):
        asyncio.run(
            collect_events(
                generator,
                build_primary_context(),
            )
        )


def test_payload_carries_profile_and_scenario_state() -> None:
    generator = ResilienceGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(
            TRAFFIC_SWITCH_COMPLETED
        ),
        transition_target=build_secondary_target(),
    )

    event = asyncio.run(
        collect_events(
            generator,
            build_primary_context(),
        )
    )[0]

    assert (
        event.data["behaviour_profile_id"]
        == TRAFFIC_SWITCH_COMPLETED
    )
    assert (
        event.data["scenario_state"]
        == OperationalState.REMEDIATION.value
    )
