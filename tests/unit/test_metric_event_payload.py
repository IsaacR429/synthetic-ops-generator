import pytest

from synthetic_ops_generator.baselines.models import (
    MetricBaseline,
)
from synthetic_ops_generator.benchmarks.models import (
    BenchmarkSource,
    BenchmarkSourceType,
    ResolvedBenchmark,
)
from synthetic_ops_generator.capacity.models import (
    CapacityClassification,
    CapacityDirection,
)
from synthetic_ops_generator.domain.enums import (
    OperationalState,
)
from synthetic_ops_generator.metrics.event_payload import (
    MetricCapacityContext,
    build_metric_event_data,
)
from synthetic_ops_generator.metrics.models import (
    MetricClassification,
    MetricDefinition,
    MetricDirection,
    MetricEvaluationStatus,
)


def test_metric_event_exposes_evaluation_status() -> None:
    definition = MetricDefinition(
        metric_definition_id="request_latency",
        name="Request Latency",
        unit="ms",
        evaluation_statistic="p95",
        direction=MetricDirection.LOWER_IS_BETTER,
    )
    baseline = MetricBaseline(
        metric_definition_id="request_latency",
        center=180.0,
        noise_stddev=0.0,
    )
    benchmark = ResolvedBenchmark(
        metric_definition_id="request_latency",
        reference_target=300.0,
        warning_threshold=500.0,
        blocking_threshold=1000.0,
        provenance=BenchmarkSource(
            source_id="test",
            source_type=(
                BenchmarkSourceType.SYNTHETIC_REFERENCE
            ),
            source_name="Test",
            version="1.0",
            rationale="Test.",
        ),
    )
    data = build_metric_event_data(
        definition=definition,
        baseline=baseline,
        benchmark=benchmark,
        baseline_profile_id="baseline_test",
        benchmark_profile_id="benchmark_test",
        behaviour_profile_id="operational_warning",
        scenario_state=OperationalState.WARNING,
        observed_value=650.0,
        classification=MetricClassification.WARNING,
        evaluation_status=MetricEvaluationStatus.EVALUATED,
    )
    assert (
        data["metric"]["evaluation_status"]
        == "evaluated"
    )
    assert (
        data["metric"]["classification"]
        == "warning"
    )


def test_context_metric_event_does_not_require_health_classification() -> None:
    definition = MetricDefinition(
        metric_definition_id="throughput",
        name="Throughput",
        unit="requests_per_second",
        evaluation_statistic="rate",
        direction=MetricDirection.CONTEXT_DEPENDENT,
    )
    baseline = MetricBaseline(
        metric_definition_id="throughput",
        center=800.0,
        noise_stddev=25.0,
        lower_bound=0.0,
    )
    data = build_metric_event_data(
        definition=definition,
        baseline=baseline,
        benchmark=None,
        baseline_profile_id="capacity_baseline",
        benchmark_profile_id=None,
        behaviour_profile_id="capacity_pressure",
        scenario_state=OperationalState.WARNING,
        observed_value=900.0,
        classification=None,
        evaluation_status=(
            MetricEvaluationStatus.CONTEXT_REQUIRED
        ),
    )
    metric = data["metric"]
    assert metric["classification"] is None
    assert (
        metric["evaluation_status"]
        == "context_required"
    )
    assert metric["effective_benchmark"] is None
    assert metric["benchmark_profile_id"] is None


def test_evaluated_metric_requires_classification() -> None:
    definition = MetricDefinition(
        metric_definition_id="request_latency",
        name="Request Latency",
        unit="ms",
        evaluation_statistic="p95",
        direction=MetricDirection.LOWER_IS_BETTER,
    )
    baseline = MetricBaseline(
        metric_definition_id="request_latency",
        center=180.0,
        noise_stddev=0.0,
    )
    benchmark = ResolvedBenchmark(
        metric_definition_id="request_latency",
        reference_target=300.0,
        warning_threshold=500.0,
        blocking_threshold=1000.0,
        provenance=BenchmarkSource(
            source_id="test",
            source_type=(
                BenchmarkSourceType.SYNTHETIC_REFERENCE
            ),
            source_name="Test",
            version="1.0",
            rationale="Test.",
        ),
    )
    with pytest.raises(
        ValueError,
        match="Evaluated Metric event requires classification",
    ):
        build_metric_event_data(
            definition=definition,
            baseline=baseline,
            benchmark=benchmark,
            baseline_profile_id="baseline_test",
            benchmark_profile_id="benchmark_test",
            behaviour_profile_id="operational_warning",
            scenario_state=OperationalState.WARNING,
            observed_value=650.0,
            classification=None,
            evaluation_status=(
                MetricEvaluationStatus.EVALUATED
            ),
        )


def test_context_required_metric_rejects_health_classification() -> None:
    definition = MetricDefinition(
        metric_definition_id="throughput",
        name="Throughput",
        unit="requests_per_second",
        evaluation_statistic="rate",
        direction=MetricDirection.CONTEXT_DEPENDENT,
    )
    baseline = MetricBaseline(
        metric_definition_id="throughput",
        center=800.0,
        noise_stddev=25.0,
        lower_bound=0.0,
    )
    with pytest.raises(
        ValueError,
        match=(
            "Context-required Metric event "
            "cannot have classification"
        ),
    ):
        build_metric_event_data(
            definition=definition,
            baseline=baseline,
            benchmark=None,
            baseline_profile_id="capacity_baseline",
            benchmark_profile_id=None,
            behaviour_profile_id="capacity_pressure",
            scenario_state=OperationalState.WARNING,
            observed_value=900.0,
            classification=MetricClassification.WARNING,
            evaluation_status=(
                MetricEvaluationStatus.CONTEXT_REQUIRED
            ),
        )


def test_context_required_metric_rejects_resolved_benchmark() -> None:
    definition = MetricDefinition(
        metric_definition_id="throughput",
        name="Throughput",
        unit="requests_per_second",
        evaluation_statistic="rate",
        direction=MetricDirection.CONTEXT_DEPENDENT,
    )
    baseline = MetricBaseline(
        metric_definition_id="throughput",
        center=800.0,
        noise_stddev=25.0,
        lower_bound=0.0,
    )
    benchmark = ResolvedBenchmark(
        metric_definition_id="throughput",
        reference_target=800.0,
        warning_threshold=900.0,
        blocking_threshold=1000.0,
        provenance=BenchmarkSource(
            source_id="test",
            source_type=(
                BenchmarkSourceType.SYNTHETIC_REFERENCE
            ),
            source_name="Test",
            version="1.0",
            rationale="Test.",
        ),
    )
    with pytest.raises(
        ValueError,
        match=(
            "Context-required Metric event "
            "cannot have resolved benchmark"
        ),
    ):
        build_metric_event_data(
            definition=definition,
            baseline=baseline,
            benchmark=benchmark,
            baseline_profile_id="capacity_baseline",
            benchmark_profile_id="benchmark_test",
            behaviour_profile_id="capacity_pressure",
            scenario_state=OperationalState.WARNING,
            observed_value=900.0,
            classification=None,
            evaluation_status=(
                MetricEvaluationStatus.CONTEXT_REQUIRED
            ),
        )


def test_evaluated_metric_requires_resolved_benchmark() -> None:
    definition = MetricDefinition(
        metric_definition_id="request_latency",
        name="Request Latency",
        unit="ms",
        evaluation_statistic="p95",
        direction=MetricDirection.LOWER_IS_BETTER,
    )
    baseline = MetricBaseline(
        metric_definition_id="request_latency",
        center=180.0,
        noise_stddev=0.0,
    )
    with pytest.raises(
        ValueError,
        match=(
            "Evaluated Metric event "
            "requires resolved benchmark"
        ),
    ):
        build_metric_event_data(
            definition=definition,
            baseline=baseline,
            benchmark=None,
            baseline_profile_id="baseline_test",
            benchmark_profile_id=None,
            behaviour_profile_id="operational_warning",
            scenario_state=OperationalState.WARNING,
            observed_value=650.0,
            classification=MetricClassification.WARNING,
            evaluation_status=(
                MetricEvaluationStatus.EVALUATED
            ),
        )


def test_context_metric_event_can_expose_capacity_evidence() -> None:
    definition = MetricDefinition(
        metric_definition_id="throughput",
        name="Throughput",
        unit="requests_per_second",
        evaluation_statistic="rate",
        direction=MetricDirection.CONTEXT_DEPENDENT,
    )
    baseline = MetricBaseline(
        metric_definition_id="throughput",
        center=700.0,
        noise_stddev=0.0,
        lower_bound=500.0,
        upper_bound=850.0,
    )
    data = build_metric_event_data(
        definition=definition,
        baseline=baseline,
        benchmark=None,
        baseline_profile_id="payment_processing_nominal",
        benchmark_profile_id=None,
        behaviour_profile_id="capacity_pressure",
        scenario_state=OperationalState.WARNING,
        observed_value=900.0,
        classification=None,
        evaluation_status=(
            MetricEvaluationStatus.CONTEXT_REQUIRED
        ),
        capacity_context=MetricCapacityContext(
            capacity_profile_id="critical_payment_capacity",
            classification=CapacityClassification.PRESSURE,
            direction=CapacityDirection.HIGHER_IS_PRESSURE,
            pressure_threshold=900.0,
            saturation_threshold=1000.0,
        ),
    )
    metric = data["metric"]
    assert metric["classification"] is None
    assert (
        metric["evaluation_status"]
        == "context_required"
    )
    assert metric["capacity"] == {
        "capacity_profile_id": "critical_payment_capacity",
        "classification": "pressure",
        "direction": "higher_is_pressure",
        "pressure_threshold": 900.0,
        "saturation_threshold": 1000.0,
    }


def test_capacity_evidence_requires_context_required_metric() -> None:
    definition = MetricDefinition(
        metric_definition_id="request_latency",
        name="Request Latency",
        unit="ms",
        evaluation_statistic="p95",
        direction=MetricDirection.LOWER_IS_BETTER,
    )
    baseline = MetricBaseline(
        metric_definition_id="request_latency",
        center=180.0,
        noise_stddev=0.0,
    )
    benchmark = ResolvedBenchmark(
        metric_definition_id="request_latency",
        reference_target=300.0,
        warning_threshold=500.0,
        blocking_threshold=1000.0,
        provenance=BenchmarkSource(
            source_id="test",
            source_type=(
                BenchmarkSourceType.SYNTHETIC_REFERENCE
            ),
            source_name="Test",
            version="1.0",
            rationale="Test.",
        ),
    )
    with pytest.raises(
        ValueError,
        match=(
            "Capacity evidence requires "
            "context-required Metric event"
        ),
    ):
        build_metric_event_data(
            definition=definition,
            baseline=baseline,
            benchmark=benchmark,
            baseline_profile_id="baseline_test",
            benchmark_profile_id="benchmark_test",
            behaviour_profile_id="healthy_baseline",
            scenario_state=OperationalState.NORMAL,
            observed_value=180.0,
            classification=MetricClassification.NORMAL,
            evaluation_status=(
                MetricEvaluationStatus.EVALUATED
            ),
            capacity_context=MetricCapacityContext(
                capacity_profile_id=(
                    "critical_payment_capacity"
                ),
                classification=(
                    CapacityClassification.NORMAL
                ),
                direction=(
                    CapacityDirection.HIGHER_IS_PRESSURE
                ),
                pressure_threshold=900.0,
                saturation_threshold=1000.0,
            ),
        )
