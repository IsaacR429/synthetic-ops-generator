from dataclasses import dataclass
from datetime import datetime, timedelta

from synthetic_ops_generator.benchmarks.evaluator import (
    classify_metric,
)
from synthetic_ops_generator.core.randomness import (
    SimulationRandom,
)
from synthetic_ops_generator.domain.enums import (
    OperationalState,
)
from synthetic_ops_generator.history.observations import (
    build_historical_observations,
)
from synthetic_ops_generator.history.scenario_runtime import (
    HistoricalScenarioRuntime,
)
from synthetic_ops_generator.history.series import (
    build_historical_expectations,
)
from synthetic_ops_generator.history.timeline import (
    HistoricalTimeline,
    build_baseline_timeline,
)
from synthetic_ops_generator.metrics.models import (
    MetricClassification,
)


@dataclass(frozen=True)
class HistoricalHealthyChangeMetricPoint:
    timestamp: datetime

    operational_state: OperationalState

    counterfactual_value: float
    observed_value: float

    classification: MetricClassification


@dataclass(frozen=True)
class HistoricalHealthyChangeMetricSeries:
    metric_definition_id: str

    points: tuple[
        HistoricalHealthyChangeMetricPoint,
        ...,
    ]


@dataclass(frozen=True)
class HistoricalHealthyChangeDataset:
    """
    Historical Metric dataset for a successful Change.

    The dataset contains:
    - a healthy pre-change baseline;
    - a Change boundary;
    - healthy post-change observations.

    It intentionally contains no degradation,
    rollback or recovery semantics.
    """

    scenario_id: str
    enterprise_id: str
    service_id: str

    baseline_profile_id: str
    benchmark_profile_id: str

    change_boundary_time: datetime

    sample_interval_seconds: int

    metric_series: dict[
        str,
        HistoricalHealthyChangeMetricSeries,
    ]


def build_historical_healthy_change_dataset(
    *,
    runtime: HistoricalScenarioRuntime,
    anchor_time: datetime,
    post_change_samples: int = 6,
    random_source: SimulationRandom | None = None,
) -> HistoricalHealthyChangeDataset:
    if post_change_samples <= 0:
        raise ValueError(
            "Healthy post-change sample count "
            "must be greater than zero."
        )

    if (
        anchor_time.tzinfo is None
        or anchor_time.utcoffset() is None
    ):
        raise ValueError(
            "Historical healthy change anchor time "
            "must be timezone-aware."
        )

    baseline_profile = (
        runtime.metric_runtime.baseline_profile
    )
    metric_runtime = runtime.metric_runtime

    baseline_timeline = build_baseline_timeline(
        end_time=anchor_time,
        baseline_profile=baseline_profile,
    )

    interval = timedelta(
        seconds=baseline_profile.sample_interval_seconds
    )
    post_change_timestamps = tuple(
        anchor_time + (interval * index)
        for index in range(1, post_change_samples + 1)
    )

    timeline = HistoricalTimeline(
        start_time=baseline_timeline.start_time,
        end_time=post_change_timestamps[-1],
        sample_interval_seconds=(
            baseline_profile.sample_interval_seconds
        ),
        timestamps=baseline_timeline.timestamps
        + (anchor_time,)
        + post_change_timestamps,
    )

    random = (
        random_source
        if random_source is not None
        else SimulationRandom()
    )

    expectations = build_historical_expectations(
        timeline=timeline,
        baseline_profile=baseline_profile,
        runtime_profile=(
            runtime.historical_runtime_profile
        ),
        random_source=random,
    )

    observations = build_historical_observations(
        expectation_bundle=expectations,
        baseline_profile=baseline_profile,
        random_source=random,
    )

    metric_series: dict[
        str,
        HistoricalHealthyChangeMetricSeries,
    ] = {}

    for metric_id in sorted(
        baseline_profile.metrics
    ):
        definition = (
            metric_runtime.definitions[metric_id]
        )
        benchmark = (
            metric_runtime.resolved_benchmarks[
                metric_id
            ]
        )
        observation_series = (
            observations.metric_series[
                metric_id
            ]
        )

        points: list[
            HistoricalHealthyChangeMetricPoint
        ] = []

        for observation in (
            observation_series.points
        ):
            # The boundary exists internally so
            # persistence continues naturally,
            # but it is not an emitted Metric point.
            if (
                observation.timestamp
                == anchor_time
            ):
                continue

            if (
                observation.timestamp
                < anchor_time
            ):
                operational_state = (
                    OperationalState.NORMAL
                )
            else:
                operational_state = (
                    OperationalState.OBSERVING
                )

            classification = classify_metric(
                definition,
                benchmark,
                observation.observed_value,
            )

            points.append(
                HistoricalHealthyChangeMetricPoint(
                    timestamp=(
                        observation.timestamp
                    ),
                    operational_state=(
                        operational_state
                    ),
                    counterfactual_value=(
                        observation.expected_value
                    ),
                    observed_value=(
                        observation.observed_value
                    ),
                    classification=(
                        classification
                    ),
                )
            )

        metric_series[
            metric_id
        ] = (
            HistoricalHealthyChangeMetricSeries(
                metric_definition_id=metric_id,
                points=tuple(points),
            )
        )

    return HistoricalHealthyChangeDataset(
        scenario_id=(
            runtime.scenario.scenario_id
        ),
        enterprise_id=(
            runtime.enterprise.enterprise_id
        ),
        service_id=(
            runtime.service.service_id
        ),
        baseline_profile_id=(
            baseline_profile.profile_id
        ),
        benchmark_profile_id=(
            metric_runtime
            .benchmark_profile_id
        ),
        change_boundary_time=anchor_time,
        sample_interval_seconds=(
            baseline_profile
            .sample_interval_seconds
        ),
        metric_series=metric_series,
    )
