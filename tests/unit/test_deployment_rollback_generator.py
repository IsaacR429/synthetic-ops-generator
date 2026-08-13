import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.domain.enums import (
    Environment,
    OperationalState,
    RiskLevel,
)
from synthetic_ops_generator.generators.deployment import (
    DeploymentGenerator,
)
from synthetic_ops_generator.scenarios.context import ScenarioContext
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    SourceDomain,
)

BASE_TIME = datetime(
    2026,
    8,
    13,
    10,
    0,
    tzinfo=UTC,
)


def build_context(
    *,
    deployment_id: str | None = "DEP0000001",
    state: OperationalState = OperationalState.ROLLBACK,
) -> ScenarioContext:
    return ScenarioContext(
        scenario_id="TEST-ROLLBACK",
        run_id="RUN0000001",
        chg_id="CHG0000001",
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        risk=RiskLevel.MEDIUM,
        deployment_id=deployment_id,
        scenario_state=state,
        simulation_time=BASE_TIME,
        random_seed=42,
    )


def build_behaviour() -> ScenarioBehaviour:
    return ScenarioBehaviour(
        source=SourceDomain.DEPLOYMENT,
        during_state=OperationalState.ROLLBACK,
        profile_id="successful_rollback",
        description="Rollback the deployed release.",
    )


async def collect_events(
    generator: DeploymentGenerator,
    context: ScenarioContext,
):
    events = []

    async for event in generator.generate(context):
        events.append(event)

        context.simulation_time = (
            context.simulation_time
            + timedelta(seconds=5)
        )

    return events


def test_successful_rollback_uses_existing_deployment_id() -> None:
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

    assert len(events) == 2

    assert [
        event.event_type
        for event in events
    ] == [
        "cicd.deployment.rollback_started",
        "cicd.deployment.rollback_completed",
    ]

    assert {
        event.data["deployment"]["deployment_id"]
        for event in events
    } == {"DEP0000001"}

    assert context.deployment_id == "DEP0000001"


def test_successful_rollback_emits_expected_lifecycle() -> None:
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

    started = events[0].data["deployment"]
    completed = events[1].data["deployment"]

    assert started["status"] == "rollback"
    assert started["outcome"] is None

    assert completed["status"] == "rolled_back"
    assert completed["outcome"] == "rolled_back"

    assert (
        completed["completion_time"]
        > completed["start_time"]
    )


def test_rollback_requires_existing_deployment() -> None:
    context = build_context(
        deployment_id=None,
    )

    generator = DeploymentGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        artifact="payment-api",
        artifact_version="2.5.0",
    )

    async def execute() -> None:
        async for _ in generator.generate(context):
            pass

    with pytest.raises(
        ValueError,
        match="existing Deployment ID",
    ):
        asyncio.run(execute())


def test_rollback_does_not_run_in_wrong_state() -> None:
    context = build_context(
        state=OperationalState.OBSERVING,
    )

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

    assert events == []
