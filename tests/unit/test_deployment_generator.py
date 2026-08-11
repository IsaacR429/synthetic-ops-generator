import asyncio
from datetime import UTC, datetime

import pytest

from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.domain.enums import (
    Environment,
    OperationalState,
    RiskLevel,
)
from synthetic_ops_generator.generators.deployment import DeploymentGenerator
from synthetic_ops_generator.scenarios.context import ScenarioContext
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    SourceDomain,
)


def build_context(
    *,
    state: OperationalState = OperationalState.IMPLEMENTING,
) -> ScenarioContext:
    return ScenarioContext(
        scenario_id="BANK-01",
        run_id="RUN0000001",
        chg_id="CHG0000001",
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        risk=RiskLevel.MEDIUM,
        scenario_state=state,
        simulation_time=datetime(
            2026,
            8,
            11,
            10,
            0,
            tzinfo=UTC,
        ),
        random_seed=42,
    )


def build_behaviour() -> ScenarioBehaviour:
    return ScenarioBehaviour(
        source=SourceDomain.DEPLOYMENT,
        during_state=OperationalState.IMPLEMENTING,
        profile_id="successful_deployment",
    )


from datetime import timedelta


async def collect_events(
    generator: DeploymentGenerator,
    context: ScenarioContext,
    step_seconds: float = 5.0,
):
    events = []
    async for event in generator.generate(context):
        events.append(event)
        context.simulation_time += timedelta(seconds=step_seconds)
    return events


def test_successful_deployment_generates_three_events() -> None:
    generator = DeploymentGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        artifact="payment-api",
        artifact_version="2.5.0",
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    assert len(events) == 3

    assert events[0].event_type == "cicd.deployment.created"
    assert events[1].event_type == "cicd.deployment.started"
    assert events[2].event_type == "cicd.deployment.completed"


def test_deployment_events_share_run_and_change_correlation() -> None:
    context = build_context()

    generator = DeploymentGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        artifact="payment-api",
        artifact_version="2.5.0",
    )

    events = asyncio.run(
        collect_events(
            generator,
            context,
        )
    )

    assert {
        event.scenario_id for event in events
    } == {"BANK-01"}

    assert {
        event.run_id for event in events
    } == {"RUN0000001"}

    assert {
        event.chg_id for event in events
    } == {"CHG0000001"}

    assert {
        event.business_stream for event in events
    } == {"payments"}

    assert {
        event.service for event in events
    } == {"payment_service"}

    assert {
        event.environment for event in events
    } == {Environment.PRODUCTION}


def test_deployment_events_use_canonical_identifiers_and_sequence() -> None:
    context = build_context()

    generator = DeploymentGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        artifact="payment-api",
        artifact_version="2.5.0",
    )

    events = asyncio.run(
        collect_events(
            generator,
            context,
        )
    )

    assert events[0].event_id == "EVT0000001"
    assert events[1].event_id == "EVT0000002"
    assert events[2].event_id == "EVT0000003"

    assert events[0].sequence_number == 1
    assert events[1].sequence_number == 2
    assert events[2].sequence_number == 3

    assert context.sequence_number == 3
    assert context.deployment_id == "DEP0000001"


def test_created_deployment_event_contains_expected_domain_data() -> None:
    generator = DeploymentGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        artifact="payment-api",
        artifact_version="2.5.0",
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    created_data = events[0].data["deployment"]

    assert created_data["deployment_id"] == "DEP0000001"
    assert created_data["chg_id"] == "CHG0000001"
    assert created_data["artifact"] == "payment-api"
    assert created_data["artifact_version"] == "2.5.0"
    assert created_data["service"] == "payment_service"
    assert created_data["component"] == "payment_api"
    assert created_data["status"] == "created"


def test_completed_deployment_has_successful_outcome() -> None:
    generator = DeploymentGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        artifact="payment-api",
        artifact_version="2.5.0",
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    completed = events[2].data["deployment"]

    assert completed["status"] == "completed"
    assert completed["outcome"] == "successful"

    assert completed["start_time"] is not None
    assert completed["completion_time"] is not None


def test_deployment_event_times_progress() -> None:
    generator = DeploymentGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        artifact="payment-api",
        artifact_version="2.5.0",
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    assert events[0].event_time < events[1].event_time
    assert events[1].event_time < events[2].event_time


def test_deployment_generator_does_not_generate_outside_state() -> None:
    generator = DeploymentGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        artifact="payment-api",
        artifact_version="2.5.0",
    )

    context = build_context(
        state=OperationalState.NORMAL,
    )

    events = asyncio.run(
        collect_events(
            generator,
            context,
        )
    )

    assert events == []
    assert context.deployment_id is None
    assert context.sequence_number == 0


def test_deployment_generator_rejects_non_deployment_behaviour() -> None:
    behaviour = ScenarioBehaviour(
        source=SourceDomain.ITSM,
        during_state=OperationalState.IMPLEMENTING,
        profile_id="approved_change",
    )

    with pytest.raises(
        ValueError,
        match="requires a deployment behaviour",
    ):
        DeploymentGenerator(
            ids=IdFactory(),
            behaviour=behaviour,
            artifact="payment-api",
            artifact_version="2.5.0",
        )


def test_deployment_generator_rejects_unknown_profile() -> None:
    behaviour = ScenarioBehaviour(
        source=SourceDomain.DEPLOYMENT,
        during_state=OperationalState.IMPLEMENTING,
        profile_id="unknown_profile",
    )

    generator = DeploymentGenerator(
        ids=IdFactory(),
        behaviour=behaviour,
        artifact="payment-api",
        artifact_version="2.5.0",
    )

    with pytest.raises(
        ValueError,
        match="Unsupported Deployment behaviour profile",
    ):
        asyncio.run(
            collect_events(
                generator,
                build_context(),
            )
        )
