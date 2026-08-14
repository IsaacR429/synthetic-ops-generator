import pytest

from synthetic_ops_generator.benchmarks.evaluator import (
    MetricEvaluationError,
)
from synthetic_ops_generator.benchmarks.models import (
    BenchmarkSource,
    BenchmarkSourceType,
    ResolvedBenchmark,
)
from synthetic_ops_generator.history.perturbation import (
    PerturbationCurveSpec,
    build_metric_perturbation_series,
    build_perturbation_curve,
    perturb_metric_value,
)
from synthetic_ops_generator.metrics.models import (
    MetricClassification,
    MetricDefinition,
    MetricDirection,
)


def build_source() -> BenchmarkSource:
    return BenchmarkSource(
        source_id="synthetic_test",
        source_type=(
            BenchmarkSourceType.SYNTHETIC_REFERENCE
        ),
        source_name="Synthetic Test",
        version="1.0",
        rationale=(
            "Unit-test benchmark provenance."
        ),
    )


def test_lower_is_better_metric_moves_toward_blocking_threshold(
) -> None:
    definition = MetricDefinition(
        metric_definition_id=(
            "request_latency"
        ),
        name="Request Latency",
        unit="ms",
        evaluation_statistic="p95",
        direction=(
            MetricDirection.LOWER_IS_BETTER
        ),
    )

    benchmark = ResolvedBenchmark(
        metric_definition_id=(
            "request_latency"
        ),
        reference_target=180.0,
        warning_threshold=240.0,
        blocking_threshold=300.0,
        provenance=build_source(),
    )

    curve = build_perturbation_curve(
        spec=PerturbationCurveSpec(
            degradation_samples=4,
        )
    )

    series = build_metric_perturbation_series(
        definition=definition,
        benchmark=benchmark,
        healthy_value=180.0,
        curve=curve,
    )

    assert tuple(
        point.perturbed_value
        for point in series.points
    ) == pytest.approx(
        (
            210.0,
            240.0,
            270.0,
            300.0,
        )
    )

    assert tuple(
        point.classification
        for point in series.points
    ) == (
        MetricClassification.NORMAL,
        MetricClassification.WARNING,
        MetricClassification.WARNING,
        MetricClassification.BLOCKING,
    )


def test_higher_is_better_metric_moves_down_to_blocking_threshold(
) -> None:
    definition = MetricDefinition(
        metric_definition_id="availability",
        name="Availability",
        unit="percent",
        evaluation_statistic="rate",
        direction=(
            MetricDirection.HIGHER_IS_BETTER
        ),
    )

    benchmark = ResolvedBenchmark(
        metric_definition_id="availability",
        reference_target=99.995,
        warning_threshold=99.95,
        blocking_threshold=99.90,
        provenance=build_source(),
    )

    curve = build_perturbation_curve(
        spec=PerturbationCurveSpec(
            degradation_samples=4,
        )
    )

    series = build_metric_perturbation_series(
        definition=definition,
        benchmark=benchmark,
        healthy_value=99.995,
        curve=curve,
    )

    values = tuple(
        point.perturbed_value
        for point in series.points
    )

    assert values == pytest.approx(
        (
            99.97125,
            99.9475,
            99.92375,
            99.90,
        )
    )

    assert (
        series.points[-1].classification
        == MetricClassification.BLOCKING
    )


def test_recovery_curve_returns_metric_to_healthy_value(
) -> None:
    definition = MetricDefinition(
        metric_definition_id=(
            "request_latency"
        ),
        name="Request Latency",
        unit="ms",
        evaluation_statistic="p95",
        direction=(
            MetricDirection.LOWER_IS_BETTER
        ),
    )

    benchmark = ResolvedBenchmark(
        metric_definition_id=(
            "request_latency"
        ),
        reference_target=180.0,
        warning_threshold=240.0,
        blocking_threshold=300.0,
        provenance=build_source(),
    )

    curve = build_perturbation_curve(
        spec=PerturbationCurveSpec(
            degradation_samples=2,
            plateau_samples=1,
            recovery_samples=2,
        )
    )

    series = build_metric_perturbation_series(
        definition=definition,
        benchmark=benchmark,
        healthy_value=180.0,
        curve=curve,
    )

    assert tuple(
        point.perturbed_value
        for point in series.points
    ) == pytest.approx(
        (
            240.0,
            300.0,
            300.0,
            240.0,
            180.0,
        )
    )

    assert (
        series.points[-1].classification
        == MetricClassification.NORMAL
    )


@pytest.mark.parametrize(
    (
        "healthy",
        "target",
        "strength",
        "expected",
    ),
    [
        (100.0, 200.0, 0.0, 100.0),
        (100.0, 200.0, 0.25, 125.0),
        (100.0, 200.0, 0.50, 150.0),
        (100.0, 200.0, 1.0, 200.0),
        (100.0, 50.0, 0.50, 75.0),
    ],
)
def test_metric_interpolation(
    healthy: float,
    target: float,
    strength: float,
    expected: float,
) -> None:
    assert perturb_metric_value(
        healthy_value=healthy,
        incident_target=target,
        strength=strength,
    ) == pytest.approx(expected)


@pytest.mark.parametrize(
    "strength",
    [
        -0.01,
        1.01,
    ],
)
def test_metric_interpolation_rejects_invalid_strength(
    strength: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="between zero and one",
    ):
        perturb_metric_value(
            healthy_value=100.0,
            incident_target=200.0,
            strength=strength,
        )


def test_metric_perturbation_rejects_non_normal_start(
) -> None:
    definition = MetricDefinition(
        metric_definition_id=(
            "request_latency"
        ),
        name="Request Latency",
        unit="ms",
        evaluation_statistic="p95",
        direction=(
            MetricDirection.LOWER_IS_BETTER
        ),
    )

    benchmark = ResolvedBenchmark(
        metric_definition_id=(
            "request_latency"
        ),
        reference_target=180.0,
        warning_threshold=240.0,
        blocking_threshold=300.0,
        provenance=build_source(),
    )

    curve = build_perturbation_curve(
        spec=PerturbationCurveSpec(
            degradation_samples=2,
        )
    )

    with pytest.raises(
        ValueError,
        match="normal healthy value",
    ):
        build_metric_perturbation_series(
            definition=definition,
            benchmark=benchmark,
            healthy_value=250.0,
            curve=curve,
        )


def test_metric_perturbation_rejects_context_dependent_metric(
) -> None:
    definition = MetricDefinition(
        metric_definition_id="throughput",
        name="Throughput",
        unit="requests_per_second",
        evaluation_statistic="rate",
        direction=(
            MetricDirection.CONTEXT_DEPENDENT
        ),
    )

    benchmark = ResolvedBenchmark(
        metric_definition_id="throughput",
        reference_target=1000.0,
        warning_threshold=800.0,
        blocking_threshold=500.0,
        provenance=build_source(),
    )

    curve = build_perturbation_curve(
        spec=PerturbationCurveSpec(
            degradation_samples=2,
        )
    )

    with pytest.raises(
        MetricEvaluationError,
        match="Context-dependent",
    ):
        build_metric_perturbation_series(
            definition=definition,
            benchmark=benchmark,
            healthy_value=1000.0,
            curve=curve,
        )


def test_metric_perturbation_rejects_mismatched_metric_ids(
) -> None:
    definition = MetricDefinition(
        metric_definition_id=(
            "request_latency"
        ),
        name="Request Latency",
        unit="ms",
        evaluation_statistic="p95",
        direction=(
            MetricDirection.LOWER_IS_BETTER
        ),
    )

    benchmark = ResolvedBenchmark(
        metric_definition_id="error_rate",
        reference_target=0.05,
        warning_threshold=0.10,
        blocking_threshold=0.20,
        provenance=build_source(),
    )

    curve = build_perturbation_curve(
        spec=PerturbationCurveSpec(
            degradation_samples=2,
        )
    )

    with pytest.raises(
        ValueError,
        match="same metric",
    ):
        build_metric_perturbation_series(
            definition=definition,
            benchmark=benchmark,
            healthy_value=180.0,
            curve=curve,
        )
