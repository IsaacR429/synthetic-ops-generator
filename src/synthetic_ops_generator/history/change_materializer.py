from dataclasses import dataclass
from pathlib import Path

from synthetic_ops_generator.core.identifiers import (
    IdFactory,
)
from synthetic_ops_generator.core.randomness import (
    SimulationRandom,
)
from synthetic_ops_generator.domain.enterprise import (
    Enterprise,
)
from synthetic_ops_generator.events.envelope import (
    GeneratedEvent,
)
from synthetic_ops_generator.history.change_context import (
    build_historical_change_context,
)
from synthetic_ops_generator.history.change_history import (
    HistoricalChangeCase,
    HistoricalChangeOutcome,
)
from synthetic_ops_generator.history.event_adapter import (
    build_historical_healthy_metric_events,
    build_historical_metric_events,
)
from synthetic_ops_generator.history.healthy_change_dataset import (
    build_historical_healthy_change_dataset,
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
from synthetic_ops_generator.scenarios.context import (
    ScenarioContext,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioDefinition,
)


@dataclass(frozen=True)
class HistoricalMaterializedChange:
    change: HistoricalChangeCase
    context: ScenarioContext
    events: tuple[GeneratedEvent, ...]


def materialize_historical_change(
    *,
    change: HistoricalChangeCase,
    scenario: ScenarioDefinition,
    enterprise: Enterprise,
    config_root: str | Path,
    ids: IdFactory,
    random_seed: int,
    incident_curve_spec: (
        PerturbationCurveSpec | None
    ) = None,
    post_change_samples: int = 6,
) -> HistoricalMaterializedChange:
    """
    Materialize one pre-identified historical
    Change into canonical Metric events.

    This function never allocates a new Run ID
    or CHG ID.
    """
    runtime = (
        build_historical_scenario_runtime(
            scenario=scenario,
            enterprise=enterprise,
            config_root=config_root,
        )
    )

    context = build_historical_change_context(
        change=change,
        scenario=scenario,
        enterprise=enterprise,
        random_seed=random_seed,
    )

    random_source = SimulationRandom(
        seed=random_seed
    )

    if (
        change.outcome
        == HistoricalChangeOutcome.SUCCESSFUL
    ):
        dataset = (
            build_historical_healthy_change_dataset(
                runtime=runtime,
                anchor_time=change.change_time,
                post_change_samples=(
                    post_change_samples
                ),
                random_source=random_source,
            )
        )

        events = (
            build_historical_healthy_metric_events(
                dataset=dataset,
                runtime=runtime,
                context=context,
                ids=ids,
            )
        )

    elif (
        change.outcome
        == HistoricalChangeOutcome.ROLLED_BACK
    ):
        if incident_curve_spec is None:
            raise ValueError(
                "Rolled-back historical Change "
                "requires an incident curve."
            )

        dataset = (
            build_historical_incident_dataset(
                runtime=runtime,
                anchor_time=change.change_time,
                curve_spec=(
                    incident_curve_spec
                ),
                random_source=random_source,
            )
        )

        events = (
            build_historical_metric_events(
                dataset=dataset,
                runtime=runtime,
                context=context,
                ids=ids,
            )
        )

    else:
        raise ValueError(
            "Unsupported historical Change "
            f"outcome: {change.outcome}"
        )

    return HistoricalMaterializedChange(
        change=change,
        context=context,
        events=events,
    )
