from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest

from synthetic_ops_generator.config.runtime import (
    IntervalFrequencyConfiguration,
    LogFrequencyConfiguration,
    RuntimeMode,
    RuntimeTimingConfiguration,
    SourceFrequencyConfiguration,
)
from synthetic_ops_generator.core.clock import ManualSimulationClock
from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.domain.enums import (
    Environment,
    OperationalState,
    RiskLevel,
)
from synthetic_ops_generator.domain.operational_log import LogSeverity
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.generators.log import (
    LogDefinition,
    LogGenerator,
)
from synthetic_ops_generator.publishers.base import EventPublisher
from synthetic_ops_generator.scenarios.context import ScenarioContext
from synthetic_ops_generator.scenarios.continuous import (
    ContinuousSourceBinding,
    ContinuousSourceScheduler,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    SourceDomain,
)

START_TIME = datetime(
    2026,
    8,
    16,
    10,
    0,
    tzinfo=UTC,
)


def make_context(
    clock: ManualSimulationClock,
    *,
    state: OperationalState = OperationalState.OBSERVING,
) -> ScenarioContext:
    return ScenarioContext(
        scenario_id="SCEN0000001",
        run_id="RUN0000001",
        chg_id="CHG0000001",
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        risk=RiskLevel.MEDIUM,
        scenario_state=state,
        simulation_time=clock.now(),
        random_seed=42,
    )


def make_frequency() -> SourceFrequencyConfiguration:
    return SourceFrequencyConfiguration(
        metrics=IntervalFrequencyConfiguration(
            interval_seconds=5.0
        ),
        logs=LogFrequencyConfiguration(
            normal_per_second=2.0,
            warning_per_second=8.0,
            failure_per_second=25.0,
        ),
        infrastructure_tests=(
            IntervalFrequencyConfiguration(
                interval_seconds=60.0
            )
        ),
    )


class SleepRecorder:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(
        self,
        seconds: float,
    ) -> None:
        self.calls.append(seconds)


class StopAfterPublisher(EventPublisher):
    def __init__(
        self,
        stop_after: int,
    ) -> None:
        self.stop_after = stop_after
        self.events: list[GeneratedEvent] = []

    async def publish(
        self,
        event: GeneratedEvent,
    ) -> None:
        self.events.append(event)

        if len(self.events) >= self.stop_after:
            raise StopAsyncIteration


class FiniteMetricCycleGenerator:
    """
    Represents the production SourceGenerator contract:

    one generate() invocation produces one finite source cycle.
    The scheduler, not the generator, owns repetition.
    """

    def __init__(self) -> None:
        self.invocation_count = 0

    async def generate(
        self,
        context: ScenarioContext,
    ) -> AsyncGenerator[GeneratedEvent, None]:
        self.invocation_count += 1

        for metric_name in (
            "request_latency",
            "error_rate",
        ):
            sequence_number = context.next_sequence()

            yield GeneratedEvent(
                event_id=(
                    f"EVT-{sequence_number}"
                ),
                sequence_number=sequence_number,
                event_type="metric.observed",
                event_time=context.simulation_time,
                source_system="synthetic_observability",
                business_stream=context.business_stream,
                service=context.service,
                component=context.component,
                environment=context.environment,
                scenario_id=context.scenario_id,
                run_id=context.run_id,
                chg_id=context.chg_id,
                data={
                    "metric": {
                        "metric_id": metric_name,
                    },
                    "scenario_state": (
                        context.scenario_state.value
                    ),
                },
            )


class FiniteInfrastructureCycleGenerator:
    def __init__(self) -> None:
        self.invocation_count = 0

    async def generate(
        self,
        context: ScenarioContext,
    ) -> AsyncGenerator[GeneratedEvent, None]:
        self.invocation_count += 1

        for check_name in (
            "connectivity",
            "service_health",
        ):
            sequence_number = context.next_sequence()

            yield GeneratedEvent(
                event_id=f"EVT-{sequence_number}",
                sequence_number=sequence_number,
                event_type="infrastructure_test.passed",
                event_time=context.simulation_time,
                source_system="synthetic_infrastructure_test",
                business_stream=context.business_stream,
                service=context.service,
                component=context.component,
                environment=context.environment,
                scenario_id=context.scenario_id,
                run_id=context.run_id,
                chg_id=context.chg_id,
                data={
                    "check": check_name,
                },
            )


class CountingLogGenerator:
    def __init__(
        self,
        generator: LogGenerator,
    ) -> None:
        self._generator = generator
        self.invocation_count = 0

    async def generate(
        self,
        context: ScenarioContext,
    ) -> AsyncGenerator[GeneratedEvent, None]:
        self.invocation_count += 1

        async for event in self._generator.generate(
            context
        ):
            yield event


@pytest.mark.asyncio
async def test_finite_metric_cycle_is_repeated_by_scheduler(
) -> None:
    clock = ManualSimulationClock(
        START_TIME
    )
    sleep = SleepRecorder()

    behaviour = ScenarioBehaviour(
        source=SourceDomain.METRIC,
        during_state=OperationalState.OBSERVING,
        profile_id="healthy_post_change",
        continuous=True,
    )

    generator = FiniteMetricCycleGenerator()

    scheduler = ContinuousSourceScheduler(
        clock=clock,
        runtime=RuntimeTimingConfiguration(
            mode=RuntimeMode.ACCELERATED,
            speed_multiplier=10.0,
        ),
        frequency=make_frequency(),
        sleep_fn=sleep,
    )

    publisher = StopAfterPublisher(
        stop_after=5
    )

    await scheduler.run(
        context=make_context(clock),
        bindings=[
            ContinuousSourceBinding(
                behaviour=behaviour,
                generator=generator,
            )
        ],
        publisher=publisher,
    )

    assert generator.invocation_count == 3

    offsets = [
        (
            event.event_time
            - START_TIME
        ).total_seconds()
        for event in publisher.events
    ]

    assert offsets == pytest.approx(
        [
            0.0,
            0.0,
            5.0,
            5.0,
            10.0,
        ]
    )

    assert sleep.calls == pytest.approx(
        [
            0.5,
            0.5,
        ]
    )


@pytest.mark.asyncio
async def test_metric_interval_applies_between_cycles_not_events(
) -> None:
    clock = ManualSimulationClock(
        START_TIME
    )
    sleep = SleepRecorder()

    behaviour = ScenarioBehaviour(
        source=SourceDomain.METRIC,
        during_state=OperationalState.OBSERVING,
        profile_id="healthy_post_change",
        continuous=True,
    )

    publisher = StopAfterPublisher(
        stop_after=4
    )

    await ContinuousSourceScheduler(
        clock=clock,
        runtime=RuntimeTimingConfiguration(
            mode=RuntimeMode.REAL_TIME,
            speed_multiplier=1.0,
        ),
        frequency=make_frequency(),
        sleep_fn=sleep,
    ).run(
        context=make_context(clock),
        bindings=[
            ContinuousSourceBinding(
                behaviour=behaviour,
                generator=(
                    FiniteMetricCycleGenerator()
                ),
            )
        ],
        publisher=publisher,
    )

    assert (
        publisher.events[0].event_time
        == publisher.events[1].event_time
    )

    assert (
        publisher.events[2].event_time
        == publisher.events[3].event_time
    )

    assert (
        publisher.events[2].event_time
        - publisher.events[0].event_time
    ).total_seconds() == pytest.approx(
        5.0
    )


@pytest.mark.asyncio
async def test_scheduler_only_runs_continuous_behaviour_for_active_state(
) -> None:
    clock = ManualSimulationClock(
        START_TIME
    )

    recovery_behaviour = ScenarioBehaviour(
        source=SourceDomain.METRIC,
        during_state=OperationalState.RECOVERY,
        profile_id="recovered_post_rollback",
        continuous=True,
    )

    scheduler = ContinuousSourceScheduler(
        clock=clock,
        runtime=RuntimeTimingConfiguration(
            mode=RuntimeMode.ACCELERATED,
            speed_multiplier=10.0,
        ),
        frequency=make_frequency(),
        sleep_fn=SleepRecorder(),
    )

    with pytest.raises(
        ValueError,
        match="continuous",
    ):
        await scheduler.run(
            context=make_context(
                clock,
                state=OperationalState.OBSERVING,
            ),
            bindings=[
                ContinuousSourceBinding(
                    behaviour=recovery_behaviour,
                    generator=(
                        FiniteMetricCycleGenerator()
                    ),
                )
            ],
            publisher=StopAfterPublisher(
                stop_after=1
            ),
        )


@pytest.mark.asyncio
async def test_finite_infrastructure_cycle_is_repeated_as_batch(
) -> None:
    clock = ManualSimulationClock(
        START_TIME
    )
    sleep = SleepRecorder()

    behaviour = ScenarioBehaviour(
        source=SourceDomain.INFRASTRUCTURE_TEST,
        during_state=OperationalState.OBSERVING,
        profile_id="all_required_checks_pass",
        continuous=True,
    )

    generator = (
        FiniteInfrastructureCycleGenerator()
    )

    publisher = StopAfterPublisher(
        stop_after=5
    )

    scheduler = ContinuousSourceScheduler(
        clock=clock,
        runtime=RuntimeTimingConfiguration(
            mode=RuntimeMode.ACCELERATED,
            speed_multiplier=10.0,
        ),
        frequency=make_frequency(),
        sleep_fn=sleep,
    )

    await scheduler.run(
        context=make_context(clock),
        bindings=[
            ContinuousSourceBinding(
                behaviour=behaviour,
                generator=generator,
            )
        ],
        publisher=publisher,
    )

    assert generator.invocation_count == 3

    offsets = [
        (
            event.event_time
            - START_TIME
        ).total_seconds()
        for event in publisher.events
    ]

    assert offsets == pytest.approx(
        [
            0.0,
            0.0,
            60.0,
            60.0,
            120.0,
        ]
    )

    assert sleep.calls == pytest.approx(
        [
            6.0,
            6.0,
        ]
    )


@pytest.mark.asyncio
async def test_finite_log_profile_is_restarted_after_exhaustion(
) -> None:
    clock = ManualSimulationClock(
        START_TIME
    )
    sleep = SleepRecorder()

    behaviour = ScenarioBehaviour(
        source=SourceDomain.LOG,
        during_state=OperationalState.OBSERVING,
        profile_id="normal_operational_logs",
        continuous=True,
    )

    generator = CountingLogGenerator(
        LogGenerator(
            ids=IdFactory(),
            behaviour=behaviour,
            logs=(
                LogDefinition(
                    log_type="warning",
                    severity=LogSeverity.WARNING,
                    message="Synthetic warning.",
                ),
                LogDefinition(
                    log_type="failure",
                    severity=LogSeverity.ERROR,
                    message="Synthetic failure.",
                ),
            ),
        )
    )

    publisher = StopAfterPublisher(
        stop_after=5
    )

    scheduler = ContinuousSourceScheduler(
        clock=clock,
        runtime=RuntimeTimingConfiguration(
            mode=RuntimeMode.REAL_TIME,
            speed_multiplier=1.0,
        ),
        frequency=make_frequency(),
        sleep_fn=sleep,
    )

    await scheduler.run(
        context=make_context(clock),
        bindings=[
            ContinuousSourceBinding(
                behaviour=behaviour,
                generator=generator,
            )
        ],
        publisher=publisher,
    )

    assert generator.invocation_count == 3

    offsets = [
        (
            event.event_time
            - START_TIME
        ).total_seconds()
        for event in publisher.events
    ]

    assert offsets == pytest.approx(
        [
            0.0,
            0.125,
            0.165,
            0.290,
            0.330,
        ]
    )

    assert sleep.calls == pytest.approx(
        [
            0.125,
            0.04,
            0.125,
            0.04,
        ]
    )