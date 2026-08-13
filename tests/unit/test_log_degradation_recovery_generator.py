import asyncio
from datetime import UTC, datetime, timedelta

from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.domain.enums import (
    Environment,
    OperationalState,
    RiskLevel,
)
from synthetic_ops_generator.generators.log import LogGenerator
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
    state: OperationalState,
) -> ScenarioContext:
    return ScenarioContext(
        scenario_id="TEST-LOG-LIFECYCLE",
        run_id="RUN0000001",
        chg_id="CHG0000001",
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        risk=RiskLevel.MEDIUM,
        scenario_state=state,
        simulation_time=BASE_TIME,
        random_seed=42,
    )


def build_behaviour(
    *,
    profile_id: str,
    state: OperationalState,
) -> ScenarioBehaviour:
    return ScenarioBehaviour(
        source=SourceDomain.LOG,
        during_state=state,
        profile_id=profile_id,
    )


async def collect_events(
    generator: LogGenerator,
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


def test_degradation_profile_emits_error_evidence() -> None:
    generator = LogGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(
            profile_id="degradation_error_logs",
            state=OperationalState.DEGRADED,
        ),
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(
                state=OperationalState.DEGRADED,
            ),
        )
    )

    assert len(events) == 3

    assert [
        event.data["log"]["log_type"]
        for event in events
    ] == [
        "request_timeout",
        "dependency_error",
        "service_health",
    ]

    assert [
        event.data["log"]["severity"]
        for event in events
    ] == [
        "error",
        "error",
        "warning",
    ]


def test_degradation_logs_preserve_profile_and_state() -> None:
    generator = LogGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(
            profile_id="degradation_error_logs",
            state=OperationalState.DEGRADED,
        ),
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(
                state=OperationalState.DEGRADED,
            ),
        )
    )

    assert {
        event.data["behaviour_profile_id"]
        for event in events
    } == {"degradation_error_logs"}

    assert {
        event.data["scenario_state"]
        for event in events
    } == {"degraded"}

    health_event = events[-1]

    assert (
        health_event.data["log"]["attributes"][
            "health_status"
        ]
        == "degraded"
    )

    assert health_event.component is None


def test_recovery_profile_emits_recovery_evidence() -> None:
    generator = LogGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(
            profile_id="recovery_operational_logs",
            state=OperationalState.RECOVERY,
        ),
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(
                state=OperationalState.RECOVERY,
            ),
        )
    )

    assert len(events) == 3

    assert [
        event.data["log"]["log_type"]
        for event in events
    ] == [
        "request_completed",
        "dependency_recovered",
        "service_health",
    ]

    assert {
        event.data["log"]["severity"]
        for event in events
    } == {"info"}

    assert {
        event.data["behaviour_profile_id"]
        for event in events
    } == {"recovery_operational_logs"}

    assert {
        event.data["scenario_state"]
        for event in events
    } == {"recovery"}


def test_log_profile_does_not_run_in_wrong_state() -> None:
    generator = LogGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(
            profile_id="degradation_error_logs",
            state=OperationalState.DEGRADED,
        ),
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(
                state=OperationalState.NORMAL,
            ),
        )
    )

    assert events == []