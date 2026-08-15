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
from synthetic_ops_generator.domain.enums import (
    Environment,
    OperationalState,
    RiskLevel,
)
from synthetic_ops_generator.domain.operational_log import (
    LogSeverity,
    OperationalLog,
)
from synthetic_ops_generator.events.envelope import GeneratedEvent
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


def make_context(clock: ManualSimulationClock) -> ScenarioContext:
    return ScenarioContext(
        scenario_id="SCEN0000001",
        run_id="RUN0000001",
        chg_id="CHG0000001",
        business_stream="retail",
        service="payment-gateway",
        component="api",
        environment=Environment.PRODUCTION,
        risk=RiskLevel.MEDIUM,
        scenario_state=OperationalState.OBSERVING,
        simulation_time=clock.now(),
        random_seed=42,
    )


def make_frequency() -> SourceFrequencyConfiguration:
    return SourceFrequencyConfiguration(
        metrics=IntervalFrequencyConfiguration(interval_seconds=6.0),
        logs=LogFrequencyConfiguration(
            normal_per_second=2.0,
            warning_per_second=8.0,
            failure_per_second=25.0,
        ),
        infrastructure_tests=IntervalFrequencyConfiguration(
            interval_seconds=60.0
        ),
    )


class SleepRecorder:
    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


class RecordingPublisher(EventPublisher):
    def __init__(self, stop_after: int = 4) -> None:
        self.events: list[GeneratedEvent] = []
        self.stop_after = stop_after

    async def publish(self, event: GeneratedEvent) -> None:
        self.events.append(event)
        if len(self.events) >= self.stop_after:
            raise StopAsyncIteration


class MetricEventGenerator:
    async def generate(
        self, context: ScenarioContext
    ) -> AsyncGenerator[GeneratedEvent, None]:
        while True:
            sequence_number = context.next_sequence()
            yield GeneratedEvent(
                event_id=f"EVT-{sequence_number}",
                sequence_number=sequence_number,
                event_type="metric.sample",
                event_time=context.simulation_time,
                source_system="synthetic_observability",
                business_stream=context.business_stream,
                service=context.service,
                component=context.component,
                environment=Environment.PRODUCTION,
                scenario_id=context.scenario_id,
                run_id=context.run_id,
                chg_id=context.chg_id,
                data={"metric": {"name": "cpu_utilization", "value": 45.0}},
            )


class LogEventGenerator:
    async def generate(
        self, context: ScenarioContext
    ) -> AsyncGenerator[GeneratedEvent, None]:
        # Event 1: Warning log
        log_warn = OperationalLog(
            log_id="LOG001",
            chg_id=context.chg_id,
            log_type="log.warning",
            service=context.service,
            component=context.component,
            severity=LogSeverity.WARNING,
            message="High memory usage",
            timestamp=context.simulation_time,
            environment=Environment.PRODUCTION,
        )
        sequence_number = context.next_sequence()
        yield GeneratedEvent(
            event_id=f"EVT-{sequence_number}",
            sequence_number=sequence_number,
            event_type="log.entry",
            event_time=context.simulation_time,
            source_system="synthetic_observability",
            business_stream=context.business_stream,
            service=context.service,
            component=context.component,
            environment=Environment.PRODUCTION,
            scenario_id=context.scenario_id,
            run_id=context.run_id,
            chg_id=context.chg_id,
            data={"log": log_warn.model_dump(mode="json")},
        )

        # Event 2: Error log
        log_err = OperationalLog(
            log_id="LOG002",
            chg_id=context.chg_id,
            log_type="log.error",
            service=context.service,
            component=context.component,
            severity=LogSeverity.ERROR,
            message="Service connection failed",
            timestamp=context.simulation_time,
            environment=Environment.PRODUCTION,
        )
        sequence_number = context.next_sequence()
        yield GeneratedEvent(
            event_id=f"EVT-{sequence_number}",
            sequence_number=sequence_number,
            event_type="log.entry",
            event_time=context.simulation_time,
            source_system="synthetic_observability",
            business_stream=context.business_stream,
            service=context.service,
            component=context.component,
            environment=Environment.PRODUCTION,
            scenario_id=context.scenario_id,
            run_id=context.run_id,
            chg_id=context.chg_id,
            data={"log": log_err.model_dump(mode="json")},
        )


class SingleEventGenerator:
    def __init__(self, event_type: str = "deployment.triggered") -> None:
        self.event_type = event_type

    async def generate(
        self, context: ScenarioContext
    ) -> AsyncGenerator[GeneratedEvent, None]:
        sequence_number = context.next_sequence()
        yield GeneratedEvent(
            event_id=f"EVT-{sequence_number}",
            sequence_number=sequence_number,
            event_type=self.event_type,
            event_time=context.simulation_time,
            source_system="synthetic_observability",
            business_stream=context.business_stream,
            service=context.service,
            component=context.component,
            environment=Environment.PRODUCTION,
            scenario_id=context.scenario_id,
            run_id=context.run_id,
            chg_id=context.chg_id,
            data={},
        )


@pytest.mark.asyncio
async def test_continuous_source_scheduler_schedules_metric_events_on_shared_timeline() -> None:
    start = datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
    clock = ManualSimulationClock(start)
    sleep = SleepRecorder()

    behaviour = ScenarioBehaviour(
        source=SourceDomain.METRIC,
        during_state=OperationalState.OBSERVING,
        profile_id="metric",
        continuous=True,
    )

    scheduler = ContinuousSourceScheduler(
        clock=clock,
        runtime=RuntimeTimingConfiguration(
            mode=RuntimeMode.ACCELERATED,
            speed_multiplier=12.0,
        ),
        frequency=make_frequency(),
        sleep_fn=sleep,
    )

    publisher = RecordingPublisher(stop_after=3)

    await scheduler.run(
        context=make_context(clock=clock),
        bindings=[
            ContinuousSourceBinding(
                behaviour=behaviour,
                generator=MetricEventGenerator(),
            )
        ],
        publisher=publisher,
    )

    event_times = [event.event_time for event in publisher.events]

    assert (
        event_times[1] - event_times[0]
    ).total_seconds() == pytest.approx(6.0)

    assert (
        event_times[2] - event_times[1]
    ).total_seconds() == pytest.approx(6.0)

    assert sleep.calls == pytest.approx([0.5, 0.5])


@pytest.mark.asyncio
async def test_continuous_source_scheduler_schedules_log_events_by_severity() -> None:
    start = datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
    clock = ManualSimulationClock(start)
    sleep = SleepRecorder()

    behaviour = ScenarioBehaviour(
        source=SourceDomain.LOG,
        during_state=OperationalState.OBSERVING,
        profile_id="log",
        continuous=True,
    )

    scheduler = ContinuousSourceScheduler(
        clock=clock,
        runtime=RuntimeTimingConfiguration(
            mode=RuntimeMode.ACCELERATED,
            speed_multiplier=12.0,
        ),
        frequency=make_frequency(),
        sleep_fn=sleep,
    )

    publisher = RecordingPublisher(stop_after=2)

    await scheduler.run(
        context=make_context(clock=clock),
        bindings=[
            ContinuousSourceBinding(
                behaviour=behaviour,
                generator=LogEventGenerator(),
            )
        ],
        publisher=publisher,
    )

    event_times = [event.event_time for event in publisher.events]

    assert (
        event_times[1] - event_times[0]
    ).total_seconds() == pytest.approx(0.125)

    assert sleep.calls == pytest.approx([0.125 / 12.0])


@pytest.mark.asyncio
async def test_scheduler_rejects_non_continuous_behaviour() -> None:
    start = datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
    clock = ManualSimulationClock(start)

    behaviour = ScenarioBehaviour(
        source=SourceDomain.METRIC,
        during_state=OperationalState.OBSERVING,
        profile_id="metric",
        continuous=False,
    )

    scheduler = ContinuousSourceScheduler(
        clock=clock,
        runtime=RuntimeTimingConfiguration(
            mode=RuntimeMode.ACCELERATED,
            speed_multiplier=12.0,
        ),
        frequency=make_frequency(),
        sleep_fn=SleepRecorder(),
    )

    with pytest.raises(
        ValueError,
        match="No continuous source behaviours",
    ):
        await scheduler.run(
            context=make_context(clock),
            bindings=[
                ContinuousSourceBinding(
                    behaviour=behaviour,
                    generator=SingleEventGenerator("metric.sample"),
                )
            ],
            publisher=RecordingPublisher(stop_after=1),
        )


@pytest.mark.asyncio
async def test_scheduler_rejects_unsupported_continuous_source() -> None:
    start = datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
    clock = ManualSimulationClock(start)

    behaviour = ScenarioBehaviour(
        source=SourceDomain.DEPLOYMENT,
        during_state=OperationalState.OBSERVING,
        profile_id="deployment",
        continuous=True,
    )

    scheduler = ContinuousSourceScheduler(
        clock=clock,
        runtime=RuntimeTimingConfiguration(
            mode=RuntimeMode.ACCELERATED,
            speed_multiplier=12.0,
        ),
        frequency=make_frequency(),
        sleep_fn=SleepRecorder(),
    )

    with pytest.raises(
        ValueError,
        match=(
            "Continuous scheduling is not "
            "configured for source: deployment"
        ),
    ):
        await scheduler.run(
            context=make_context(clock),
            bindings=[
                ContinuousSourceBinding(
                    behaviour=behaviour,
                    generator=SingleEventGenerator("deployment.triggered"),
                )
            ],
            publisher=RecordingPublisher(stop_after=1),
        )
