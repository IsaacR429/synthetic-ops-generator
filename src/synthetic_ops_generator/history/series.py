from dataclasses import dataclass

from synthetic_ops_generator.baselines.models import (
    BaselineProfile,
)
from synthetic_ops_generator.core.randomness import (
    SimulationRandom,
)
from synthetic_ops_generator.history.adapter import (
    HistoricalRuntimeProfile,
)
from synthetic_ops_generator.history.correlation import (
    HistoricalMetricExpectationSeries,
    build_metric_expectation_series,
)
from synthetic_ops_generator.history.temporal import (
    HistoricalActivitySeries,
    build_activity_series,
)
from synthetic_ops_generator.history.timeline import (
    HistoricalTimeline,
)


@dataclass(frozen=True)
class HistoricalExpectationBundle:
    profile_id: str

    activity_series: HistoricalActivitySeries

    metric_series: dict[
        str,
        HistoricalMetricExpectationSeries,
    ]


def build_historical_expectations(
    *,
    timeline: HistoricalTimeline,
    baseline_profile: BaselineProfile,
    runtime_profile: HistoricalRuntimeProfile,
    random_source: SimulationRandom,
) -> HistoricalExpectationBundle:
    if (
        baseline_profile.profile_id
        != runtime_profile.profile_id
    ):
        raise ValueError(
            "Baseline profile and historical "
            "runtime profile must have the "
            "same profile ID."
        )

    baseline_metric_ids = set(
        baseline_profile.metrics
    )

    response_metric_ids = set(
        runtime_profile.metric_responses
    )

    if baseline_metric_ids != response_metric_ids:
        raise ValueError(
            "Historical runtime metric responses "
            "must exactly match Baseline metrics."
        )

    activity_series = build_activity_series(
        timeline=timeline,
        activity_profile=(
            runtime_profile.activity_profile
        ),
        persistence_profile=(
            runtime_profile.persistence_profile
        ),
        random_source=random_source,
    )

    metric_series = {
        metric_id: build_metric_expectation_series(
            activity_series=activity_series,
            baseline=baseline_profile.metrics[
                metric_id
            ],
            response=(
                runtime_profile.metric_responses[
                    metric_id
                ]
            ),
        )
        for metric_id in sorted(
            baseline_profile.metrics
        )
    }

    return HistoricalExpectationBundle(
        profile_id=baseline_profile.profile_id,
        activity_series=activity_series,
        metric_series=metric_series,
    )
