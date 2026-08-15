import inspect
from collections.abc import AsyncGenerator, Awaitable, Callable, Sequence
from dataclasses import dataclass

from synthetic_ops_generator.config.runtime import (
    RuntimeTimingConfiguration,
    SourceFrequencyConfiguration,
)
from synthetic_ops_generator.core.clock import SimulationClock
from synthetic_ops_generator.domain.operational_log import OperationalLog
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.generators.base import SourceGenerator
from synthetic_ops_generator.publishers.base import EventPublisher
from synthetic_ops_generator.scenarios.context import ScenarioContext
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    SourceDomain,
)


@dataclass(frozen=True)
class ContinuousSourceBinding:
    behaviour: ScenarioBehaviour
    generator: SourceGenerator | AsyncGenerator[GeneratedEvent, None]


class ContinuousSourceScheduler:
    def __init__(
        self,
        *,
        clock: SimulationClock,
        runtime: RuntimeTimingConfiguration,
        frequency: SourceFrequencyConfiguration,
        sleep_fn: (
            Callable[[float], Awaitable[None]]
            | Callable[[float], None]
            | None
        ) = None,
    ) -> None:
        self._clock = clock
        self._runtime = runtime
        self._frequency = frequency
        self._sleep_fn = sleep_fn

    def _simulated_interval(
        self,
        source: SourceDomain,
        event: GeneratedEvent,
    ) -> float:
        if source == SourceDomain.METRIC:
            return self._frequency.metrics.interval_seconds

        if source == SourceDomain.LOG:
            return self._log_simulated_interval(event)

        if source == SourceDomain.INFRASTRUCTURE_TEST:
            return self._frequency.infrastructure_tests.interval_seconds

        raise ValueError(
            "Continuous interval is not "
            f"configured for source: {source.value}"
        )

    def _log_simulated_interval(
        self,
        event: GeneratedEvent,
    ) -> float:
        log_payload = event.data.get("log")

        if not isinstance(log_payload, dict):
            raise ValueError(  # noqa: TRY004
                "Continuous Log event is missing "
                "a valid log payload."
            )

        operational_log = OperationalLog.model_validate(log_payload)

        severity = operational_log.severity.value

        if severity == "info":
            rate = self._frequency.logs.normal_per_second

        elif severity == "warning":
            rate = self._frequency.logs.warning_per_second

        elif severity == "error":
            rate = self._frequency.logs.failure_per_second

        else:
            raise ValueError(
                "Continuous Log scheduling does "
                "not define a rate for severity: "
                f"{severity}"
            )

        return 1.0 / rate

    async def run(
        self,
        *,
        context: ScenarioContext,
        bindings: Sequence[ContinuousSourceBinding],
        publisher: EventPublisher,
    ) -> None:
        active_bindings: list[ContinuousSourceBinding] = []

        for binding in bindings:
            if not binding.behaviour.continuous:
                continue

            source = binding.behaviour.source
            if source not in (
                SourceDomain.METRIC,
                SourceDomain.INFRASTRUCTURE_TEST,
                SourceDomain.LOG,
            ):
                raise ValueError(
                    "Continuous scheduling is not "
                    f"configured for source: {source.value}"
                )

            active_bindings.append(binding)

        if not active_bindings:
            raise ValueError("No continuous source behaviours")

        iterators = []
        for binding in active_bindings:
            if hasattr(binding.generator, "generate"):
                gen = binding.generator.generate(context)
            else:
                gen = binding.generator
            iterators.append((binding, gen))

        for binding, gen in iterators:
            try:
                async for event in gen:
                    try:
                        await publisher.publish(event)
                    except StopAsyncIteration:
                        return

                    simulated_interval = self._simulated_interval(
                        binding.behaviour.source, event
                    )
                    wall_seconds = self._runtime.wall_clock_seconds(
                        simulated_interval
                    )

                    if self._sleep_fn is not None:
                        res = self._sleep_fn(wall_seconds)
                        if inspect.isawaitable(res):
                            await res

                    self._clock.advance(simulated_interval)
                    context.simulation_time = self._clock.now()
            except StopAsyncIteration:
                return
