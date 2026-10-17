from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest

from synthetic_ops_generator.core.clock import ManualSimulationClock
from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.generators.base import SourceGenerator
from synthetic_ops_generator.generators.bindings import (
    SourceExecutionBinding,
)
from synthetic_ops_generator.scenarios.context import (
    ScenarioContext,
    ScenarioExecutionTarget,
)
from synthetic_ops_generator.domain.enterprise import (
    BusinessStream,
    Component,
    Enterprise,
    Service,
)
from synthetic_ops_generator.domain.enums import (
    Action,
    Criticality,
    Decision,
    Environment,
    Industry,
    OperationalState,
    Outcome,
    RiskLevel,
)
from synthetic_ops_generator.oracle.models import ExpectedScenarioResult
from synthetic_ops_generator.publishers.memory import (
    InMemoryPublisher,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    ScenarioCorrelation,
    ScenarioDefinition,
    ScenarioFamily,
    ScenarioTarget,
    ScenarioTrigger,
    SourceDomain,
)
from synthetic_ops_generator.scenarios.runner import ScenarioRunner


def build_enterprise() -> Enterprise:
    return Enterprise(
        enterprise_id="bank_alpha",
        name="Bank Alpha",
        industry=Industry.BANKING,
        business_streams=[
            BusinessStream(
                stream_id="payments",
                name="Payments",
            )
        ],
        services=[
            Service(
                service_id="payment_service",
                name="Payment Service",
                business_stream_id="payments",
                owner="Payments Operations",
                criticality=Criticality.CRITICAL,
            )
        ],
        components=[
            Component(
                component_id="payment_api",
                name="Payment API",
                component_type="api",
                service_id="payment_service",
                environment=Environment.PRODUCTION,
            )
        ],
    )


def build_scenario() -> ScenarioDefinition:
    return ScenarioDefinition(
        scenario_id="BANK-01",
        name="Successful Payment Release",
        description="Healthy payment-service release.",
        family=ScenarioFamily.CHANGE_VALIDATION,
        industry=Industry.BANKING,
        target=ScenarioTarget(
            enterprise_id="bank_alpha",
            business_stream_id="payments",
            service_id="payment_service",
            component_ids=["payment_api"],
            environment=Environment.PRODUCTION,
        ),
        risk=RiskLevel.MEDIUM,
        initial_conditions=[
            "Change approved",
            "Payment Service healthy",
        ],
        trigger=ScenarioTrigger(
            source=SourceDomain.DEPLOYMENT,
            trigger_type="deployment",
            description="Deploy payment API.",
            artifact="payment-api",
            version="2.5.0",
        ),
        state_sequence=[
            OperationalState.INITIALISING,
            OperationalState.NORMAL,
            OperationalState.IMPLEMENTING,
            OperationalState.OBSERVING,
            OperationalState.COMPLETED,
        ],
        behaviours=[
            ScenarioBehaviour(
                behaviour_id="fixture_test_scenario_runner_01",
                source=SourceDomain.ITSM,
                during_state=OperationalState.NORMAL,
                profile_id="approved_change",
            ),
            ScenarioBehaviour(
                behaviour_id="fixture_test_scenario_runner_02",
                source=SourceDomain.DEPLOYMENT,
                during_state=OperationalState.IMPLEMENTING,
                profile_id="successful_deployment",
            ),
        ],
        expected_result=ExpectedScenarioResult(
            scenario_id="BANK-01",
            expected_decision=Decision.PASS,
            expected_action=Action.PROCEED,
            expected_outcome=Outcome.SUCCESSFUL,
        ),
    )


def test_runner_creates_scenario_context() -> None:
    start = datetime(
        2026,
        8,
        11,
        10,
        0,
        tzinfo=UTC,
    )

    runner = ScenarioRunner(
        ids=IdFactory(),
        clock=ManualSimulationClock(start),
    )

    context = runner.create_context(
        scenario=build_scenario(),
        enterprise=build_enterprise(),
        random_seed=42,
    )

    assert context.scenario_id == "BANK-01"
    assert context.run_id == "RUN0000001"
    assert context.chg_id == "CHG0000001"

    assert context.business_stream == "payments"
    assert context.service == "payment_service"
    assert context.component == "payment_api"

    assert context.environment == Environment.PRODUCTION
    assert context.risk == RiskLevel.MEDIUM

    assert context.scenario_state == OperationalState.INITIALISING
    assert context.simulation_time == start
    assert context.sequence_number == 0
    assert context.random_seed == 42


def test_runner_creates_context_without_change_for_non_change_scenario(
) -> None:
    start = datetime(
        2026,
        8,
        11,
        10,
        0,
        tzinfo=UTC,
    )

    runner = ScenarioRunner(
        ids=IdFactory(),
        clock=ManualSimulationClock(start),
    )

    scenario = build_scenario().model_copy(
        update={
            "correlation": ScenarioCorrelation(
                change_required=False,
            )
        }
    )

    context = runner.create_context(
        scenario=scenario,
        enterprise=build_enterprise(),
        random_seed=42,
    )

    assert context.run_id == "RUN0000001"
    assert context.chg_id is None


def test_runner_creates_unique_run_and_change_ids() -> None:
    start = datetime(
        2026,
        8,
        11,
        10,
        0,
        tzinfo=UTC,
    )

    runner = ScenarioRunner(
        ids=IdFactory(),
        clock=ManualSimulationClock(start),
    )

    scenario = build_scenario()
    enterprise = build_enterprise()

    first = runner.create_context(
        scenario=scenario,
        enterprise=enterprise,
        random_seed=42,
    )

    second = runner.create_context(
        scenario=scenario,
        enterprise=enterprise,
        random_seed=42,
    )

    assert first.run_id == "RUN0000001"
    assert second.run_id == "RUN0000002"

    assert first.chg_id == "CHG0000001"
    assert second.chg_id == "CHG0000002"


def test_runner_executes_bank_01_state_sequence() -> None:
    start = datetime(
        2026,
        8,
        11,
        10,
        0,
        tzinfo=UTC,
    )

    runner = ScenarioRunner(
        ids=IdFactory(),
        clock=ManualSimulationClock(start),
    )

    scenario = build_scenario()

    context = runner.create_context(
        scenario=scenario,
        enterprise=build_enterprise(),
        random_seed=42,
    )

    visited_states = runner.execute_state_sequence(
        scenario=scenario,
        context=context,
    )

    assert visited_states == [
        "initialising",
        "normal",
        "implementing",
        "observing",
        "completed",
    ]

    assert context.scenario_state == OperationalState.COMPLETED


def test_runner_rejects_wrong_enterprise() -> None:
    start = datetime(
        2026,
        8,
        11,
        10,
        0,
        tzinfo=UTC,
    )

    runner = ScenarioRunner(
        ids=IdFactory(),
        clock=ManualSimulationClock(start),
    )

    wrong_enterprise = build_enterprise().model_copy(
        update={
            "enterprise_id": "wrong_bank",
        }
    )

    with pytest.raises(
        ValueError,
        match="Scenario target enterprise",
    ):
        runner.create_context(
            scenario=build_scenario(),
            enterprise=wrong_enterprise,
            random_seed=42,
        )


@pytest.mark.asyncio
async def test_runner_notifies_progress_observer_at_state_boundaries(
) -> None:
    start = datetime(
        2026,
        8,
        11,
        10,
        0,
        tzinfo=UTC,
    )

    runner = ScenarioRunner(
        ids=IdFactory(),
        clock=ManualSimulationClock(start),
    )

    scenario = build_scenario()

    context = runner.create_context(
        scenario=scenario,
        enterprise=build_enterprise(),
        random_seed=42,
    )

    progress_updates: list[
        tuple[OperationalState, int]
    ] = []

    async def observe_progress(
        state: OperationalState,
        event_count: int,
    ) -> None:
        progress_updates.append(
            (
                state,
                event_count,
            )
        )

    visited_states = await runner.execute(
        scenario=scenario,
        context=context,
        generators=[],
        publisher=InMemoryPublisher(),
        event_interval_seconds=5.0,
        progress_observer=observe_progress,
    )

    assert visited_states == [
        "initialising",
        "normal",
        "implementing",
        "observing",
        "completed",
    ]

    assert progress_updates == [
        (
            OperationalState.NORMAL,
            0,
        ),
        (
            OperationalState.NORMAL,
            0,
        ),
        (
            OperationalState.IMPLEMENTING,
            0,
        ),
        (
            OperationalState.IMPLEMENTING,
            0,
        ),
        (
            OperationalState.OBSERVING,
            0,
        ),
        (
            OperationalState.OBSERVING,
            0,
        ),
        (
            OperationalState.COMPLETED,
            0,
        ),
        (
            OperationalState.COMPLETED,
            0,
        ),
    ]

    assert (
        context.scenario_state
        == OperationalState.COMPLETED
    )


@pytest.mark.asyncio
async def test_runner_can_stop_at_active_state_before_completed() -> None:
    scenario = build_scenario()
    enterprise = build_enterprise()

    start = datetime(
        2026,
        8,
        15,
        10,
        0,
        tzinfo=UTC,
    )

    runner = ScenarioRunner(
        ids=IdFactory(),
        clock=ManualSimulationClock(start),
    )

    context = runner.create_context(
        scenario=scenario,
        enterprise=enterprise,
        random_seed=42,
    )

    class NullPublisher:
        async def publish(
            self,
            event: object,
        ) -> None:
            del event

    visited_states = await runner.execute(
        scenario=scenario,
        context=context,
        generators=[],
        publisher=NullPublisher(),
        stop_at_state=OperationalState.OBSERVING,
    )

    assert visited_states == [
        OperationalState.INITIALISING.value,
        OperationalState.NORMAL.value,
        OperationalState.IMPLEMENTING.value,
        OperationalState.OBSERVING.value,
    ]

    assert context.scenario_state == OperationalState.OBSERVING

    assert (
        OperationalState.COMPLETED.value
        not in visited_states
    )


class ContextRecordingGenerator(SourceGenerator):
    source_system = "test"

    async def generate(
        self,
        context: ScenarioContext,
    ) -> AsyncIterator[GeneratedEvent]:
        sequence_number = context.next_sequence()
        yield GeneratedEvent(
            event_id=f"EVT-{sequence_number}",
            event_type="test.context",
            event_time=context.simulation_time,
            source_system=self.source_system,
            scenario_id=context.scenario_id,
            run_id=context.run_id,
            chg_id=context.chg_id,
            business_stream=context.business_stream,
            service=context.service,
            component=context.component,
            environment=context.environment,
            sequence_number=sequence_number,
        )


@pytest.mark.asyncio
async def test_execute_bindings_projects_target_context() -> None:
    scenario = build_scenario()
    enterprise = build_enterprise()
    clock = ManualSimulationClock(
        datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
    )
    runner = ScenarioRunner(
        ids=IdFactory(),
        clock=clock,
    )
    context = runner.create_context(
        scenario=scenario,
        enterprise=enterprise,
        random_seed=42,
    )
    target = ScenarioExecutionTarget(
        business_stream="core_banking",
        service="account_service",
        component="account_database",
        environment=Environment.PRODUCTION,
    )
    binding = SourceExecutionBinding(
        behaviour=scenario.behaviours[0],
        generator=ContextRecordingGenerator(),
        execution_target=target,
    )
    publisher = InMemoryPublisher()
    await runner.execute_bindings(
        scenario=scenario,
        context=context,
        bindings=[binding],
        publisher=publisher,
        stop_at_state=OperationalState.NORMAL,
    )
    assert len(publisher.events) > 0
    event = publisher.events[0]
    assert event.business_stream == "core_banking"
    assert event.service == "account_service"
    assert event.component == "account_database"
    assert context.service == "payment_service"


@pytest.mark.asyncio
async def test_execute_bindings_shares_run_state_and_sequence() -> None:
    scenario = build_scenario()
    enterprise = build_enterprise()
    clock = ManualSimulationClock(
        datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
    )
    runner = ScenarioRunner(
        ids=IdFactory(),
        clock=clock,
    )
    context = runner.create_context(
        scenario=scenario,
        enterprise=enterprise,
        random_seed=42,
    )
    target_b = ScenarioExecutionTarget(
        business_stream="core_banking",
        service="account_service",
        component="account_database",
        environment=Environment.PRODUCTION,
    )
    binding_a = SourceExecutionBinding(
        behaviour=scenario.behaviours[0],
        generator=ContextRecordingGenerator(),
        execution_target=None,
    )
    binding_b = SourceExecutionBinding(
        behaviour=scenario.behaviours[0],
        generator=ContextRecordingGenerator(),
        execution_target=target_b,
    )
    publisher = InMemoryPublisher()
    await runner.execute_bindings(
        scenario=scenario,
        context=context,
        bindings=[binding_a, binding_b],
        publisher=publisher,
        stop_at_state=OperationalState.NORMAL,
    )
    events = publisher.events
    assert len(events) == 2
    event_a, event_b = events[0], events[1]
    assert event_a.run_id == event_b.run_id
    assert event_a.scenario_id == event_b.scenario_id
    assert event_a.chg_id == event_b.chg_id
    assert event_a.sequence_number == 1
    assert event_b.sequence_number == 2
