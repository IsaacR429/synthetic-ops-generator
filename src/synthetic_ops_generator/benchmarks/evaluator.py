from dataclasses import dataclass

from synthetic_ops_generator.benchmarks.models import (
    ResolvedBenchmark,
)
from synthetic_ops_generator.metrics.models import (
    MetricClassification,
    MetricDefinition,
    MetricDirection,
    MetricEvaluationStatus,
)


class MetricEvaluationError(ValueError):
    pass


@dataclass(frozen=True)
class MetricEvaluationResult:
    status: MetricEvaluationStatus
    classification: MetricClassification | None


def classify_metric(
    definition: MetricDefinition,
    benchmark: ResolvedBenchmark,
    observed_value: float,
) -> MetricClassification:
    if definition.direction == MetricDirection.LOWER_IS_BETTER:
        if observed_value >= benchmark.blocking_threshold:
            return MetricClassification.BLOCKING

        if observed_value >= benchmark.warning_threshold:
            return MetricClassification.WARNING

        return MetricClassification.NORMAL

    if definition.direction == MetricDirection.HIGHER_IS_BETTER:
        if observed_value <= benchmark.blocking_threshold:
            return MetricClassification.BLOCKING

        if observed_value <= benchmark.warning_threshold:
            return MetricClassification.WARNING

        return MetricClassification.NORMAL

    raise MetricEvaluationError(
        f"Metric {definition.metric_definition_id} "
        "requires context-specific evaluation."
    )


def evaluate_metric(
    *,
    definition: MetricDefinition,
    benchmark: ResolvedBenchmark | None,
    observed_value: float,
) -> MetricEvaluationResult:
    if (
        definition.direction
        == MetricDirection.CONTEXT_DEPENDENT
    ):
        return MetricEvaluationResult(
            status=(
                MetricEvaluationStatus.CONTEXT_REQUIRED
            ),
            classification=None,
        )

    if benchmark is None:
        raise MetricEvaluationError(
            f"Metric {definition.metric_definition_id} "
            "requires a resolved Benchmark for evaluation."
        )

    return MetricEvaluationResult(
        status=MetricEvaluationStatus.EVALUATED,
        classification=classify_metric(
            definition,
            benchmark,
            observed_value,
        ),
    )
