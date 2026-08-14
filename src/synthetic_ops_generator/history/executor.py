import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.core.randomness import SimulationRandom
from synthetic_ops_generator.domain.enterprise import Enterprise
from synthetic_ops_generator.domain.enums import OperationalState
from synthetic_ops_generator.history.event_adapter import (
    iter_historical_metric_events,
)
from synthetic_ops_generator.history.incident_dataset import (
    build_historical_incident_dataset,
)
from synthetic_ops_generator.history.perturbation import (
    PerturbationCurveSpec,
)
from synthetic_ops_generator.history.scenario_runtime import (
    build_historical_scenario_runtime,
)
from synthetic_ops_generator.publishers.base import EventPublisher
from synthetic_ops_generator.scenarios.context import ScenarioContext
from synthetic_ops_generator.scenarios.models import ScenarioDefinition

ProgressObserver = Callable[
    [OperationalState, int],
    Awaitable[None] | None,
]


@dataclass(frozen=True)
class HistoricalRunExecutionResult:
    event_count: int
    final_state: OperationalState
    change_boundary_time: datetime
    rollback_boundary_time: datetime


class HistoricalRunExecutor:
    def __init__(
        self,
        *,
        config_root: str | Path,
    ) -> None:
        self._config_root = Path(
            config_root
        )

    async def execute(
        self,
        *,
        scenario: ScenarioDefinition,
        enterprise: Enterprise,
        context: ScenarioContext,
        ids: IdFactory,
        publisher: EventPublisher,
        anchor_time: datetime,
        curve_spec: PerturbationCurveSpec,
        progress_observer: ProgressObserver | None = None,
    ) -> HistoricalRunExecutionResult:
        runtime = build_historical_scenario_runtime(
            scenario=scenario,
            enterprise=enterprise,
            config_root=self._config_root,
        )

        dataset = build_historical_incident_dataset(
            runtime=runtime,
            anchor_time=anchor_time,
            curve_spec=curve_spec,
            random_source=SimulationRandom(
                seed=context.random_seed
            ),
        )

        event_count = 0
        current_sample_state: OperationalState | None = None
        metrics_per_sample = len(dataset.metric_series)

        for event in iter_historical_metric_events(
            dataset=dataset,
            runtime=runtime,
            context=context,
            ids=ids,
        ):
            await publisher.publish(event)
            event_count += 1

            state_str = event.data["metric"]["scenario_state"]
            current_sample_state = OperationalState(state_str)

            if (
                event_count % metrics_per_sample == 0
                and progress_observer is not None
            ):
                res = progress_observer(
                    current_sample_state,
                    event_count,
                )
                if inspect.isawaitable(res):
                    await res

        if (
            progress_observer is not None
            and event_count > 0
        ):
            res = progress_observer(
                OperationalState.COMPLETED,
                event_count,
            )
            if inspect.isawaitable(res):
                await res

        return HistoricalRunExecutionResult(
            event_count=event_count,
            final_state=OperationalState.COMPLETED,
            change_boundary_time=dataset.change_boundary_time,
            rollback_boundary_time=dataset.rollback_boundary_time,
        )
