import pytest

from synthetic_ops_generator.benchmarks.models import (
    BenchmarkOverride,
    BenchmarkScope,
    BenchmarkSource,
    BenchmarkSourceType,
    MetricPolicy,
)
from synthetic_ops_generator.benchmarks.resolver import (
    BenchmarkResolutionError,
    resolve_benchmark,
)
from synthetic_ops_generator.metrics.models import (
    MetricDefinition,
    MetricDirection,
)


def make_source() -> BenchmarkSource:
    return BenchmarkSource(
        source_id="test_source",
        source_type=BenchmarkSourceType.SYNTHETIC_REFERENCE,
        source_name="Test Source",
        version="1.0",
        rationale="Test benchmark source.",
    )


def make_latency_definition() -> MetricDefinition:
    return MetricDefinition(
        metric_definition_id="request_latency",
        name="Request Latency",
        unit="ms",
        evaluation_statistic="p95",
        direction=MetricDirection.LOWER_IS_BETTER,
    )


def test_service_override_wins() -> None:
    definition = make_latency_definition()

    base_policy = MetricPolicy(
        metric_definition_id="request_latency",
        reference_target=500,
        warning_threshold=800,
        blocking_threshold=1500,
        provenance=make_source(),
    )

    overrides = [
        BenchmarkOverride(
            scope=BenchmarkScope.ENTERPRISE,
            scope_id="bank_alpha",
            metric_definition_id="request_latency",
            reference_target=350,
            warning_threshold=600,
            blocking_threshold=1000,
        ),
        BenchmarkOverride(
            scope=BenchmarkScope.SERVICE,
            scope_id="payment_service",
            metric_definition_id="request_latency",
            reference_target=250,
            warning_threshold=400,
            blocking_threshold=700,
        ),
    ]

    resolved = resolve_benchmark(
        definition,
        base_policy,
        overrides,
    )

    assert resolved.reference_target == 250
    assert resolved.warning_threshold == 400
    assert resolved.blocking_threshold == 700


def test_invalid_threshold_order_is_rejected() -> None:
    definition = make_latency_definition()

    policy = MetricPolicy(
        metric_definition_id="request_latency",
        reference_target=500,
        warning_threshold=400,
        blocking_threshold=700,
        provenance=make_source(),
    )

    with pytest.raises(BenchmarkResolutionError):
        resolve_benchmark(
            definition,
            policy,
        )