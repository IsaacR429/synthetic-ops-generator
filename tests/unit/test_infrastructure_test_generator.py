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
from synthetic_ops_generator.generators.infrastructure_test import (
    InfrastructureCheckDefinition,
    InfrastructureTestGenerator,
)
from synthetic_ops_generator.scenarios.context import ScenarioContext
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    SourceDomain,
)


def build_context(
    *,
    state: OperationalState = OperationalState.NORMAL,
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
        source=SourceDomain.INFRASTRUCTURE_TEST,
        during_state=OperationalState.NORMAL,
        profile_id="all_required_checks_pass",
    )


async def collect_events(
    generator: InfrastructureTestGenerator,
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


def test_required_checks_generate_planned_and_passed_events() -> None:
    generator = InfrastructureTestGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    assert len(events) == 6

    assert [
        event.event_type for event in events
    ] == [
        "infrastructure_test.planned",
        "infrastructure_test.passed",
        "infrastructure_test.planned",
        "infrastructure_test.passed",
        "infrastructure_test.planned",
        "infrastructure_test.passed",
    ]


def test_each_check_reuses_its_test_id() -> None:
    generator = InfrastructureTestGenerator(
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
        events[0].data["test"]["test_id"]
        == events[1].data["test"]["test_id"]
        == "TST0000001"
    )

    assert (
        events[2].data["test"]["test_id"]
        == events[3].data["test"]["test_id"]
        == "TST0000002"
    )

    assert (
        events[4].data["test"]["test_id"]
        == events[5].data["test"]["test_id"]
        == "TST0000003"
    )


def test_infrastructure_events_share_correlation() -> None:
    generator = InfrastructureTestGenerator(
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


def test_passed_events_contain_executed_pass_result() -> None:
    generator = InfrastructureTestGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    passed_events = events[1::2]

    for event in passed_events:
        test_data = event.data["test"]

        assert test_data["category"] == "infrastructure"
        assert test_data["mandatory"] is True
        assert test_data["status"] == "executed"
        assert test_data["result"] == "passed"
        assert test_data["executed_at"] is not None


def test_sequence_numbers_are_monotonic() -> None:
    context = build_context()

    generator = InfrastructureTestGenerator(
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
        event.sequence_number for event in events
    ] == [1, 2, 3, 4, 5, 6]

    assert context.sequence_number == 6


def test_event_times_progress() -> None:
    generator = InfrastructureTestGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    event_times = [
        event.event_time for event in events
    ]

    assert event_times == sorted(event_times)
    assert len(set(event_times)) == 6


def test_custom_check_definitions_are_supported() -> None:
    checks = (
        InfrastructureCheckDefinition(
            test_type="dns",
            name="DNS resolution",
        ),
        InfrastructureCheckDefinition(
            test_type="certificate",
            name="Certificate validity",
        ),
    )

    generator = InfrastructureTestGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        checks=checks,
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    assert len(events) == 4

    assert events[0].data["test"]["test_type"] == "dns"
    assert (
        events[2].data["test"]["test_type"]
        == "certificate"
    )


def test_generator_does_not_run_outside_behaviour_state() -> None:
    context = build_context(
        state=OperationalState.OBSERVING,
    )

    generator = InfrastructureTestGenerator(
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
        source=SourceDomain.APPLICATION_TEST,
        during_state=OperationalState.NORMAL,
        profile_id="all_required_checks_pass",
    )

    with pytest.raises(
        ValueError,
        match="requires an infrastructure-test behaviour",
    ):
        InfrastructureTestGenerator(
            ids=IdFactory(),
            behaviour=behaviour,
        )


def test_generator_rejects_unknown_profile() -> None:
    behaviour = ScenarioBehaviour(
        source=SourceDomain.INFRASTRUCTURE_TEST,
        during_state=OperationalState.NORMAL,
        profile_id="unknown_profile",
    )

    generator = InfrastructureTestGenerator(
        ids=IdFactory(),
        behaviour=behaviour,
    )

    with pytest.raises(
        ValueError,
        match="Unsupported Infrastructure Test behaviour profile",
    ):
        asyncio.run(
            collect_events(
                generator,
                build_context(),
            )
        )