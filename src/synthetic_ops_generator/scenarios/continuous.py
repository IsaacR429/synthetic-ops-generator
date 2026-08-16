import heapq
import inspect
from collections.abc import AsyncGenerator, Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

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

    def _cycle_interval(
        self,
        source: SourceDomain,
    ) -> float:
        if source == SourceDomain.METRIC:
            return self._frequency.metrics.interval_seconds

        if source == SourceDomain.INFRASTRUCTURE_TEST:
            return self._frequency.infrastructure_tests.interval_seconds

        raise ValueError(
            "Continuous cycle interval is not "
            f"configured for source: {source.value}"
        )

    def _new_iterator(
        self,
        *,
        binding: ContinuousSourceBinding,
        context: ScenarioContext,
    ) -> Any:
        if hasattr(binding.generator, "generate"):
            gen = binding.generator.generate(context)
        else:
            gen = binding.generator

        return gen.__aiter__() if hasattr(gen, "__aiter__") else gen

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

            if binding.behaviour.during_state != context.scenario_state:
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
            raise ValueError(
                "No continuous source behaviours configured for active state"
            )

        heap: list[tuple[float, int, ContinuousSourceBinding, Any]] = []

        for idx, binding in enumerate(active_bindings):
            iterator = self._new_iterator(
                binding=binding,
                context=context,
            )
            heapq.heappush(
                heap,
                (0.0, idx, binding, iterator),
            )

        current_sim_offset = 0.0

        while heap:
            (
                sched_time,
                priority_idx,
                binding,
                iterator,
            ) = heapq.heappop(heap)

            if sched_time > current_sim_offset:
                delta_sim = sched_time - current_sim_offset

                wall_seconds = self._runtime.wall_clock_seconds(delta_sim)

                if self._sleep_fn is not None:
                    result = self._sleep_fn(wall_seconds)

                    if inspect.isawaitable(result):
                        await result

                self._clock.advance(delta_sim)

                current_sim_offset = sched_time

                context.simulation_time = self._clock.now()

            source = binding.behaviour.source

            if source in (
                SourceDomain.METRIC,
                SourceDomain.INFRASTRUCTURE_TEST,
            ):
                while True:
                    try:
                        event = await iterator.__anext__()

                    except StopAsyncIteration:
                        break

                    try:
                        await publisher.publish(event)

                    except StopAsyncIteration:
                        return

                if not hasattr(binding.generator, "generate"):
                    continue

                next_iterator = self._new_iterator(
                    binding=binding,
                    context=context,
                )

                next_sched_time = (
                    current_sim_offset + self._cycle_interval(source)
                )

                heapq.heappush(
                    heap,
                    (
                        next_sched_time,
                        priority_idx,
                        binding,
                        next_iterator,
                    ),
                )

                continue

            try:
                event = await iterator.__anext__()

            except StopAsyncIteration:
                if not hasattr(binding.generator, "generate"):
                    continue

                iterator = self._new_iterator(
                    binding=binding,
                    context=context,
                )

                try:
                    event = await iterator.__anext__()

                except StopAsyncIteration as exc:
                    raise ValueError(
                        "Continuous source generator "
                        "produced an empty cycle"
                    ) from exc

            try:
                await publisher.publish(event)

            except StopAsyncIteration:
                return

            next_sched_time = (
                current_sim_offset + self._log_simulated_interval(event)
            )

            heapq.heappush(
                heap,
                (
                    next_sched_time,
                    priority_idx,
                    binding,
                    iterator,
                ),
            )
