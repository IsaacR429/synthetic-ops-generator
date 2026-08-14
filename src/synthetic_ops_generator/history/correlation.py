from dataclasses import dataclass
from datetime import datetime

from synthetic_ops_generator.baselines.models import (
    MetricBaseline,
)
from synthetic_ops_generator.history.temporal import (
    HistoricalActivitySeries,
)


@dataclass(frozen=True)
class MetricActivityResponse:
    metric_definition_id: str
    slope_per_activity_unit: float

    def __post_init__(self) -> None:
        if not self.metric_definition_id.strip():
            raise ValueError(
                "metric_definition_id cannot be empty."
            )


@dataclass(frozen=True)
class HistoricalMetricExpectationPoint:
    timestamp: datetime
    activity_factor: float
    expected_value: float


@dataclass(frozen=True)
class HistoricalMetricExpectationSeries:
    metric_definition_id: str
    points: tuple[
        HistoricalMetricExpectationPoint,
        ...,
    ]


def expected_metric_value(
    *,
    baseline: MetricBaseline,
    response: MetricActivityResponse,
    activity_factor: float,
) -> float:
    if baseline.metric_definition_id != response.metric_definition_id:
        raise ValueError(
            "Baseline and response must target the "
            "same Metric Definition."
        )

    if activity_factor < 0:
        raise ValueError(
            "Activity factor cannot be negative."
        )

    expected = baseline.center + (activity_factor - 1.0) * response.slope_per_activity_unit

    if baseline.lower_bound is not None:
        expected = max(expected, baseline.lower_bound)

    if baseline.upper_bound is not None:
        expected = min(expected, baseline.upper_bound)

    return float(expected)


def build_metric_expectation_series(
    *,
    activity_series: HistoricalActivitySeries,
    baseline: MetricBaseline,
    response: MetricActivityResponse,
) -> HistoricalMetricExpectationSeries:
    points = tuple(
        HistoricalMetricExpectationPoint(
            timestamp=point.timestamp,
            activity_factor=(
                point.activity_factor
            ),
            expected_value=expected_metric_value(
                baseline=baseline,
                response=response,
                activity_factor=(
                    point.activity_factor
                ),
            ),
        )
        for point in activity_series.points
    )

    return HistoricalMetricExpectationSeries(
        metric_definition_id=(
            baseline.metric_definition_id
        ),
        points=points,
    )
