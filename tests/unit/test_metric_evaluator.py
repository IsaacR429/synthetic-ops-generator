from synthetic_ops_generator.benchmarks.evaluator import (
    classify_metric,
)
from synthetic_ops_generator.benchmarks.models import (
    BenchmarkSource,
    BenchmarkSourceType,
    ResolvedBenchmark,
)
from synthetic_ops_generator.metrics.models import (
    MetricClassification,
    MetricDefinition,
    MetricDirection,
)


def make_source() -> BenchmarkSource:
    return BenchmarkSource(
        source_id="test",
        source_type=BenchmarkSourceType.SYNTHETIC_REFERENCE,
        source_name="Test",
        version="1.0",
        rationale="Test.",
    )


def test_latency_warning_classification() -> None:
    definition = MetricDefinition(
        metric_definition_id="request_latency",
        name="Request Latency",
        unit="ms",
        evaluation_statistic="p95",
        direction=MetricDirection.LOWER_IS_BETTER,
    )

    benchmark = ResolvedBenchmark(
        metric_definition_id="request_latency",
        reference_target=300,
        warning_threshold=500,
        blocking_threshold=1000,
        provenance=make_source(),
    )

    result = classify_metric(
        definition,
        benchmark,
        observed_value=650,
    )

    assert result == MetricClassification.WARNING


def test_availability_blocking_classification() -> None:
    definition = MetricDefinition(
        metric_definition_id="availability",
        name="Availability",
        unit="percent",
        evaluation_statistic="rate",
        direction=MetricDirection.HIGHER_IS_BETTER,
    )

    benchmark = ResolvedBenchmark(
        metric_definition_id="availability",
        reference_target=99.99,
        warning_threshold=99.90,
        blocking_threshold=99.00,
        provenance=make_source(),
    )

    result = classify_metric(
        definition,
        benchmark,
        observed_value=98.7,
    )

    assert result == MetricClassification.BLOCKING