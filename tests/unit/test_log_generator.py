import asyncio
from datetime import UTC, datetime

import pytest

from synthetic_ops_generator.core.clock import (
    ManualSimulationClock,
)
from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.domain.enums import (
    Environment,
    OperationalState,
    RiskLevel,
)
from synthetic_ops_generator.domain.operational_log import (
    LogSeverity,
)
from synthetic_ops_generator.generators.log import (
    LogDefinition,
    LogGenerator,
)
from synthetic_ops_generator.scenarios.context import ScenarioContext
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    SourceDomain,
)


def build_context(
    *,
    state: OperationalState = OperationalState.OBSERVING,
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
            12,
            0,
            tzinfo=UTC,
        ),
        random_seed=42,
    )


def build_behaviour(
    *,
    profile_id: str = "normal_operational_logs",
) -> ScenarioBehaviour:
    return ScenarioBehaviour(
        source=SourceDomain.LOG,
        during_state=OperationalState.OBSERVING,
        profile_id=profile_id,
    )


async def collect_events(
    generator: LogGenerator,
    context: ScenarioContext,
):
    clock = ManualSimulationClock(
        context.simulation_time
    )

    events = []

    async for event in generator.generate(context):
        events.append(event)

        clock.advance(5)
        context.simulation_time = clock.now()

    return events


def test_normal_profile_generates_three_log_events() -> None:
    generator = LogGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    assert len(events) == 3

    assert [
        event.event_type
        for event in events
    ] == [
        "log.observed",
        "log.observed",
        "log.observed",
    ]


def test_logs_receive_central_log_ids() -> None:
    generator = LogGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    assert [
        event.data["log"]["log_id"]
        for event in events
    ] == [
        "LOG0000001",
        "LOG0000002",
        "LOG0000003",
    ]


def test_log_events_preserve_run_correlation() -> None:
    generator = LogGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    assert {
        event.scenario_id
        for event in events
    } == {"BANK-01"}

    assert {
        event.run_id
        for event in events
    } == {"RUN0000001"}

    assert {
        event.chg_id
        for event in events
    } == {"CHG0000001"}

    assert {
        event.service
        for event in events
    } == {"payment_service"}


def test_normal_operational_logs_are_info_severity() -> None:
    generator = LogGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    assert {
        event.data["log"]["severity"]
        for event in events
    } == {"info"}

    assert all(
        event.data["log"]["error_code"] is None
        for event in events
    )


def test_default_logs_have_expected_scope() -> None:
    generator = LogGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    assert [
        event.component
        for event in events
    ] == [
        "payment_api",
        "payment_api",
        None,
    ]


def test_log_timestamp_matches_event_time() -> None:
    generator = LogGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    for event in events:
        log_timestamp = datetime.fromisoformat(
            event.data["log"]["timestamp"]
        )

        assert log_timestamp == event.event_time


def test_log_sequence_and_time_progress() -> None:
    context = build_context()

    generator = LogGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            context,
        )
    )

    assert [
        event.sequence_number
        for event in events
    ] == [1, 2, 3]

    event_times = [
        event.event_time
        for event in events
    ]

    assert event_times == sorted(event_times)
    assert len(set(event_times)) == 3

    assert context.sequence_number == 3


def test_log_attributes_are_structured() -> None:
    generator = LogGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    assert (
        events[0].data["log"]["attributes"][
            "operation_status"
        ]
        == "accepted"
    )

    assert (
        events[2].data["log"]["attributes"][
            "health_status"
        ]
        == "normal"
    )


def test_custom_log_definitions_are_supported() -> None:
    logs = (
        LogDefinition(
            log_type="worker_heartbeat",
            severity=LogSeverity.INFO,
            message="Worker heartbeat received.",
            component_scoped=True,
            attributes={
                "worker_status": "healthy",
            },
        ),
    )

    generator = LogGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        logs=logs,
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    assert len(events) == 1

    log_data = events[0].data["log"]

    assert log_data["log_type"] == "worker_heartbeat"
    assert log_data["severity"] == "info"
    assert log_data["component"] == "payment_api"
    assert (
        log_data["attributes"]["worker_status"]
        == "healthy"
    )


def test_generator_does_not_run_outside_behaviour_state() -> None:
    context = build_context(
        state=OperationalState.NORMAL,
    )

    generator = LogGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
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
        source=SourceDomain.METRIC,
        during_state=OperationalState.OBSERVING,
        profile_id="normal_operational_logs",
    )

    with pytest.raises(
        ValueError,
        match="requires a Log behaviour",
    ):
        LogGenerator(
            ids=IdFactory(),
            behaviour=behaviour,
        )


def test_generator_rejects_unknown_profile() -> None:
    generator = LogGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(
            profile_id="unknown_log_profile",
        ),
    )

    with pytest.raises(
        ValueError,
        match="Unsupported Log behaviour profile",
    ):
        asyncio.run(
            collect_events(
                generator,
                build_context(),
            )
        )