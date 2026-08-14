from dataclasses import dataclass
from datetime import datetime

from synthetic_ops_generator.baselines.models import (
    BaselineProfile,
)
from synthetic_ops_generator.core.randomness import (
    SimulationRandom,
)
from synthetic_ops_generator.history.series import (
    HistoricalExpectationBundle,
)
from synthetic_ops_generator.history.temporal import (
    HistoricalActivitySeries,
)


@dataclass(frozen=True)
class HistoricalMetricObservationPoint:
    timestamp: datetime
    activity_factor: float
    expected_value: float
    observed_value: float


@dataclass(frozen=True)
class HistoricalMetricObservationSeries:
    metric_definition_id: str
    points: tuple[
        HistoricalMetricObservationPoint,
        ...,
    ]


@dataclass(frozen=True)
class HistoricalObservationBundle:
    profile_id: str
    activity_series: HistoricalActivitySeries
    metric_series: dict[
        str,
        HistoricalMetricObservationSeries,
    ]


def build_historical_observations(
    *,
    expectation_bundle: HistoricalExpectationBundle,
    baseline_profile: BaselineProfile,
    random_source: SimulationRandom,
) -> HistoricalObservationBundle:
    if (
        expectation_bundle.profile_id
        != baseline_profile.profile_id
    ):
        raise ValueError(
            "Expectation bundle profile ID "
            "must match Baseline profile ID: "
            f"'{expectation_bundle.profile_id}' vs "
            f"'{baseline_profile.profile_id}'."
        )

    baseline_metric_ids = set(
        baseline_profile.metrics
    )
    expectation_metric_ids = set(
        expectation_bundle.metric_series
    )

    if baseline_metric_ids != expectation_metric_ids:
        raise ValueError(
            "Expectation bundle metrics must "
            "exactly match Baseline profile metrics."
        )

    metric_series: dict[
        str,
        HistoricalMetricObservationSeries,
    ] = {}

    for metric_id in sorted(
        baseline_profile.metrics
    ):
        baseline = baseline_profile.metrics[
            metric_id
        ]

        expectation_series = (
            expectation_bundle.metric_series[
                metric_id
            ]
        )

        if (
            expectation_series.metric_definition_id
            != metric_id
        ):
            raise ValueError(
                "Historical expectation series "
                "metric ID does not match its "
                f"mapping key: {metric_id}"
            )

        points: list[
            HistoricalMetricObservationPoint
        ] = []

        for expectation in (
            expectation_series.points
        ):
            if baseline.noise_stddev == 0:
                observed_value = (
                    expectation.expected_value
                )
            else:
                residual = random_source.normal(
                    0.0,
                    baseline.noise_stddev,
                )

                observed_value = (
                    expectation.expected_value
                    + residual
                )

            if baseline.lower_bound is not None:
                observed_value = max(
                    observed_value,
                    baseline.lower_bound,
                )

            if baseline.upper_bound is not None:
                observed_value = min(
                    observed_value,
                    baseline.upper_bound,
                )

            points.append(
                HistoricalMetricObservationPoint(
                    timestamp=(
                        expectation.timestamp
                    ),
                    activity_factor=(
                        expectation.activity_factor
                    ),
                    expected_value=(
                        expectation.expected_value
                    ),
                    observed_value=float(
                        observed_value
                    ),
                )
            )

        metric_series[
            metric_id
        ] = HistoricalMetricObservationSeries(
            metric_definition_id=metric_id,
            points=tuple(points),
        )

    return HistoricalObservationBundle(
        profile_id=baseline_profile.profile_id,
        activity_series=(
            expectation_bundle.activity_series
        ),
        metric_series=metric_series,
    )
