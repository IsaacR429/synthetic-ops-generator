from datetime import UTC, datetime, timedelta

import pytest

from synthetic_ops_generator.baselines.models import (
    MetricBaseline,
)
from synthetic_ops_generator.history.correlation import (
    MetricActivityResponse,
    build_metric_expectation_series,
    expected_metric_value,
)
from synthetic_ops_generator.history.temporal import (
    HistoricalActivityPoint,
    HistoricalActivitySeries,
)


def build_activity_series(
) -> HistoricalActivitySeries:
    start = datetime(
        2026,
        8,
        14,
        9,
        0,
        tzinfo=UTC,
    )

    activity_factors = (
        0.6,
        0.8,
        1.0,
        1.2,
        1.4,
    )

    return HistoricalActivitySeries(
        points=tuple(
            HistoricalActivityPoint(
                timestamp=(
                    start
                    + timedelta(
                        minutes=index * 5
                    )
                ),
                target_factor=activity,
                activity_factor=activity,
            )
            for index, activity
            in enumerate(
                activity_factors
            )
        )
    )


def test_latency_increases_with_activity(
) -> None:
    baseline = MetricBaseline(
        metric_definition_id=(
            "request_latency"
        ),
        center=180.0,
        noise_stddev=15.0,
        lower_bound=100.0,
        upper_bound=260.0,
    )

    response = MetricActivityResponse(
        metric_definition_id=(
            "request_latency"
        ),
        slope_per_activity_unit=150.0,
    )

    series = (
        build_metric_expectation_series(
            activity_series=(
                build_activity_series()
            ),
            baseline=baseline,
            response=response,
        )
    )

    values = [
        point.expected_value
        for point in series.points
    ]

    assert values == pytest.approx(
        [
            120.0,
            150.0,
            180.0,
            210.0,
            240.0,
        ]
    )


def test_availability_decreases_with_activity(
) -> None:
    baseline = MetricBaseline(
        metric_definition_id=(
            "availability"
        ),
        center=99.95,
        noise_stddev=0.01,
        lower_bound=99.90,
        upper_bound=100.0,
    )

    response = MetricActivityResponse(
        metric_definition_id=(
            "availability"
        ),
        slope_per_activity_unit=-0.05,
    )

    series = (
        build_metric_expectation_series(
            activity_series=(
                build_activity_series()
            ),
            baseline=baseline,
            response=response,
        )
    )

    values = [
        point.expected_value
        for point in series.points
    ]

    assert values == pytest.approx(
        [
            99.97,
            99.96,
            99.95,
            99.94,
            99.93,
        ]
    )


def test_shared_activity_creates_correlated_metric_direction(
) -> None:
    activity_series = (
        build_activity_series()
    )

    latency = build_metric_expectation_series(
        activity_series=activity_series,
        baseline=MetricBaseline(
            metric_definition_id=(
                "request_latency"
            ),
            center=180.0,
            noise_stddev=0.0,
        ),
        response=MetricActivityResponse(
            metric_definition_id=(
                "request_latency"
            ),
            slope_per_activity_unit=100.0,
        ),
    )

    errors = build_metric_expectation_series(
        activity_series=activity_series,
        baseline=MetricBaseline(
            metric_definition_id=(
                "error_rate"
            ),
            center=0.05,
            noise_stddev=0.0,
        ),
        response=MetricActivityResponse(
            metric_definition_id=(
                "error_rate"
            ),
            slope_per_activity_unit=0.10,
        ),
    )

    availability = (
        build_metric_expectation_series(
            activity_series=activity_series,
            baseline=MetricBaseline(
                metric_definition_id=(
                    "availability"
                ),
                center=99.95,
                noise_stddev=0.0,
            ),
            response=(
                MetricActivityResponse(
                    metric_definition_id=(
                        "availability"
                    ),
                    slope_per_activity_unit=(
                        -0.05
                    ),
                )
            ),
        )
    )

    latency_values = [
        point.expected_value
        for point in latency.points
    ]

    error_values = [
        point.expected_value
        for point in errors.points
    ]

    availability_values = [
        point.expected_value
        for point in availability.points
    ]

    assert latency_values == sorted(
        latency_values
    )

    assert error_values == sorted(
        error_values
    )

    assert availability_values == sorted(
        availability_values,
        reverse=True,
    )


def test_expected_metric_value_respects_baseline_bounds(
) -> None:
    baseline = MetricBaseline(
        metric_definition_id=(
            "request_latency"
        ),
        center=180.0,
        noise_stddev=0.0,
        lower_bound=100.0,
        upper_bound=260.0,
    )

    response = MetricActivityResponse(
        metric_definition_id=(
            "request_latency"
        ),
        slope_per_activity_unit=500.0,
    )

    high = expected_metric_value(
        baseline=baseline,
        response=response,
        activity_factor=2.0,
    )

    low = expected_metric_value(
        baseline=baseline,
        response=response,
        activity_factor=0.0,
    )

    assert high == 260.0
    assert low == 100.0


def test_metric_response_rejects_mismatched_baseline(
) -> None:
    baseline = MetricBaseline(
        metric_definition_id=(
            "request_latency"
        ),
        center=180.0,
    )

    response = MetricActivityResponse(
        metric_definition_id=(
            "error_rate"
        ),
        slope_per_activity_unit=0.1,
    )

    with pytest.raises(
        ValueError,
        match="same Metric Definition",
    ):
        expected_metric_value(
            baseline=baseline,
            response=response,
            activity_factor=1.0,
        )


def test_metric_response_rejects_negative_activity(
) -> None:
    baseline = MetricBaseline(
        metric_definition_id=(
            "request_latency"
        ),
        center=180.0,
    )

    response = MetricActivityResponse(
        metric_definition_id=(
            "request_latency"
        ),
        slope_per_activity_unit=100.0,
    )

    with pytest.raises(
        ValueError,
        match="cannot be negative",
    ):
        expected_metric_value(
            baseline=baseline,
            response=response,
            activity_factor=-0.1,
        )
