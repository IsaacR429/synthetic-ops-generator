from dataclasses import dataclass
from typing import Any

from synthetic_ops_generator.baselines.models import (
    MetricBaseline,
)
from synthetic_ops_generator.benchmarks.models import (
    ResolvedBenchmark,
)
from synthetic_ops_generator.capacity.models import (
    CapacityClassification,
    CapacityDirection,
)
from synthetic_ops_generator.domain.enums import (
    OperationalState,
)
from synthetic_ops_generator.metrics.models import (
    MetricClassification,
    MetricDefinition,
    MetricEvaluationStatus,
)

METRIC_EVENT_TYPE = "metric.observed"
METRIC_SOURCE_SYSTEM = "synthetic_observability"


@dataclass(frozen=True)
class MetricHistoricalContext:
    counterfactual_value: float
    perturbation_strength: float
    perturbation_phase: str | None


@dataclass(frozen=True)
class MetricCapacityContext:
    capacity_profile_id: str
    classification: CapacityClassification
    direction: CapacityDirection
    pressure_threshold: float
    saturation_threshold: float


def build_metric_event_data(
    *,
    definition: MetricDefinition,
    baseline: MetricBaseline,
    benchmark: ResolvedBenchmark | None,
    baseline_profile_id: str,
    benchmark_profile_id: str | None,
    behaviour_profile_id: str | None,
    scenario_state: OperationalState,
    observed_value: float,
    classification: MetricClassification | None,
    evaluation_status: (
        MetricEvaluationStatus
    ) = MetricEvaluationStatus.EVALUATED,
    historical_context: (
        MetricHistoricalContext | None
    ) = None,
    capacity_context: (
        MetricCapacityContext | None
    ) = None,
) -> dict[str, Any]:
    if (
        evaluation_status
        == MetricEvaluationStatus.EVALUATED
        and classification is None
    ):
        raise ValueError(
            "Evaluated Metric event requires classification."
        )

    if (
        evaluation_status
        == MetricEvaluationStatus.EVALUATED
        and benchmark is None
    ):
        raise ValueError(
            "Evaluated Metric event "
            "requires resolved benchmark."
        )


    if (
        evaluation_status
        == MetricEvaluationStatus.CONTEXT_REQUIRED
        and classification is not None
    ):
        raise ValueError(
            "Context-required Metric event "
            "cannot have classification."
        )

    if (
        evaluation_status
        == MetricEvaluationStatus.CONTEXT_REQUIRED
        and benchmark is not None
    ):
        raise ValueError(
            "Context-required Metric event "
            "cannot have resolved benchmark."
        )

    if (
        capacity_context is not None
        and evaluation_status
        != MetricEvaluationStatus.CONTEXT_REQUIRED
    ):
        raise ValueError(
            "Capacity evidence requires "
            "context-required Metric event."
        )

    metric: dict[str, Any] = {



        "metric_definition_id": (
            definition.metric_definition_id
        ),
        "name": definition.name,
        "observed_value": observed_value,
        "unit": definition.unit,
        "evaluation_statistic": (
            definition.evaluation_statistic
        ),
        "direction": definition.direction.value,
        "classification": (
            classification.value
            if classification is not None
            else None
        ),
        "evaluation_status": evaluation_status.value,
        "baseline_profile_id": (
            baseline_profile_id
        ),

        "baseline": baseline.model_dump(
            mode="json"
        ),
        "benchmark_profile_id": (
            benchmark_profile_id
        ),
        "effective_benchmark": (
            benchmark.model_dump(
                mode="json"
            )
            if benchmark is not None
            else None
        ),
        "behaviour_profile_id": (
            behaviour_profile_id
        ),
        "scenario_state": (
            scenario_state.value
        ),
    }


    if historical_context is not None:
        metric["historical"] = {
            "counterfactual_value": (
                historical_context.counterfactual_value
            ),
            "perturbation_strength": (
                historical_context.perturbation_strength
            ),
            "perturbation_phase": (
                historical_context.perturbation_phase
            ),
        }

    if capacity_context is not None:
        metric["capacity"] = {
            "capacity_profile_id": (
                capacity_context.capacity_profile_id
            ),
            "classification": (
                capacity_context.classification.value
            ),
            "direction": (
                capacity_context.direction.value
            ),
            "pressure_threshold": (
                capacity_context.pressure_threshold
            ),
            "saturation_threshold": (
                capacity_context.saturation_threshold
            ),
        }

    return {
        "metric": metric,
    }
