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
from synthetic_ops_generator.generators.manual_validation import (
    ManualValidationDefinition,
    ManualValidationGenerator,
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
        scenario_id="TEST-MANUAL-01",
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
            12,
            12,
            0,
            tzinfo=UTC,
        ),
        random_seed=42,
    )


def build_behaviour(
    *,
    profile_id: str = "all_required_validations_pass",
) -> ScenarioBehaviour:
    return ScenarioBehaviour(
        source=SourceDomain.MANUAL_VALIDATION,
        during_state=OperationalState.OBSERVING,
        profile_id=profile_id,
    )


async def collect_events(
    generator: ManualValidationGenerator,
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


def test_required_validations_generate_request_and_completion() -> None:
    generator = ManualValidationGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    assert len(events) == 4

    assert [
        event.event_type
        for event in events
    ] == [
        "manual_validation.requested",
        "manual_validation.completed",
        "manual_validation.requested",
        "manual_validation.completed",
    ]


def test_each_validation_reuses_same_validation_id() -> None:
    generator = ManualValidationGenerator(
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
        events[0].data["validation"]["validation_id"]
        == events[1].data["validation"]["validation_id"]
        == "VAL0000001"
    )

    assert (
        events[2].data["validation"]["validation_id"]
        == events[3].data["validation"]["validation_id"]
        == "VAL0000002"
    )


def test_manual_validation_events_preserve_correlation() -> None:
    generator = ManualValidationGenerator(
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
    } == {"TEST-MANUAL-01"}

    assert {
        event.run_id
        for event in events
    } == {"RUN0000001"}

    assert {
        event.chg_id
        for event in events
    } == {"CHG0000001"}

    assert {
        event.source_domain
        for event in events
    } == {SourceDomain.MANUAL_VALIDATION}

    assert {
        event.service
        for event in events
    } == {"payment_service"}


def test_requested_events_are_pending_without_result() -> None:
    generator = ManualValidationGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    requested_events = events[0::2]

    for event in requested_events:
        validation = event.data["validation"]

        assert validation["status"] == "pending"
        assert validation["result"] is None
        assert validation["completed_at"] is None
        assert validation["validated_by"] is None


def test_completed_events_are_passed() -> None:
    generator = ManualValidationGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    completed_events = events[1::2]

    for event in completed_events:
        validation = event.data["validation"]

        assert validation["status"] == "completed"
        assert validation["result"] == "passed"
        assert validation["completed_at"] is not None
        assert (
            validation["validated_by"]
            == "synthetic_operations_validator"
        )


def test_generator_does_not_create_evidence() -> None:
    generator = ManualValidationGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    assert all(
        event.data["validation"]["evidence_reference"]
        is None
        for event in events
    )


def test_default_validations_support_service_and_component_scope() -> None:
    generator = ManualValidationGenerator(
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
        None,
        None,
        "payment_api",
        "payment_api",
    ]


def test_validation_sequence_and_time_progress() -> None:
    context = build_context()

    generator = ManualValidationGenerator(
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
    ] == [1, 2, 3, 4]

    event_times = [
        event.event_time
        for event in events
    ]

    assert event_times == sorted(event_times)
    assert len(set(event_times)) == 4

    assert context.sequence_number == 4


def test_custom_manual_validation_definitions_are_supported() -> None:
    validations = (
        ManualValidationDefinition(
            validation_type="customer_journey",
            name="Customer journey validation",
            mandatory=False,
            component_scoped=True,
            validated_by="business_operator",
        ),
    )

    generator = ManualValidationGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        validations=validations,
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    assert len(events) == 2

    completed = events[1].data["validation"]

    assert (
        completed["validation_type"]
        == "customer_journey"
    )

    assert completed["mandatory"] is False

    assert (
        completed["validated_by"]
        == "business_operator"
    )


def test_generator_does_not_run_outside_behaviour_state() -> None:
    context = build_context(
        state=OperationalState.NORMAL,
    )

    generator = ManualValidationGenerator(
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
        source=SourceDomain.LOG,
        during_state=OperationalState.OBSERVING,
        profile_id="all_required_validations_pass",
    )

    with pytest.raises(
        ValueError,
        match="requires a Manual Validation behaviour",
    ):
        ManualValidationGenerator(
            ids=IdFactory(),
            behaviour=behaviour,
        )


def test_generator_rejects_unknown_profile() -> None:
    generator = ManualValidationGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(
            profile_id="unknown_validation_profile",
        ),
    )

    with pytest.raises(
        ValueError,
        match="Unsupported Manual Validation behaviour profile",
    ):
        asyncio.run(
            collect_events(
                generator,
                build_context(),
            )
        )