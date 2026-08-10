from synthetic_ops_generator.benchmarks.models import (
    ResolvedBenchmark,
)
from synthetic_ops_generator.metrics.models import (
    MetricClassification,
    MetricDefinition,
    MetricDirection,
)


class MetricEvaluationError(ValueError):
    pass


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
