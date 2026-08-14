from dataclasses import dataclass
from typing import Any

from synthetic_ops_generator.baselines.models import (
    MetricBaseline,
)
from synthetic_ops_generator.benchmarks.models import (
    ResolvedBenchmark,
)
from synthetic_ops_generator.domain.enums import (
    OperationalState,
)
from synthetic_ops_generator.metrics.models import (
    MetricClassification,
    MetricDefinition,
)

METRIC_EVENT_TYPE = "metric.observed"
METRIC_SOURCE_SYSTEM = "synthetic_observability"


@dataclass(frozen=True)
class MetricHistoricalContext:
    counterfactual_value: float
    perturbation_strength: float
    perturbation_phase: str | None


def build_metric_event_data(
    *,
    definition: MetricDefinition,
    baseline: MetricBaseline,
    benchmark: ResolvedBenchmark,
    baseline_profile_id: str,
    benchmark_profile_id: str,
    behaviour_profile_id: str | None,
    scenario_state: OperationalState,
    observed_value: float,
    classification: MetricClassification,
    historical_context: (
        MetricHistoricalContext | None
    ) = None,
) -> dict[str, Any]:
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
        "classification": classification.value,
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

    return {
        "metric": metric,
    }
