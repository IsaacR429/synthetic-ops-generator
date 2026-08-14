from datetime import UTC, datetime

import pytest

from synthetic_ops_generator.baselines.loader import (
    load_baseline_profile,
)
from synthetic_ops_generator.baselines.models import (
    BaselineProfile,
    MetricBaseline,
)
from synthetic_ops_generator.core.randomness import (
    SimulationRandom,
)
from synthetic_ops_generator.history.adapter import (
    build_historical_runtime_profile,
)
from synthetic_ops_generator.history.loader import (
    load_historical_behaviour_profile,
)
from synthetic_ops_generator.history.observations import (
    build_historical_observations,
)
from synthetic_ops_generator.history.series import (
    HistoricalExpectationBundle,
    build_historical_expectations,
)
from synthetic_ops_generator.history.timeline import (
    build_baseline_timeline,
)


def build_expectations(
    *,
    profile_id: str,
    seed: int = 42,
) -> tuple[
    BaselineProfile,
    HistoricalExpectationBundle,
]:
    baseline = load_baseline_profile(
        profile_id
    )

    historical = (
        load_historical_behaviour_profile(
            profile_id
        )
    )

    runtime = (
        build_historical_runtime_profile(
            baseline_profile=baseline,
            historical_profile=historical,
        )
    )

    timeline = build_baseline_timeline(
        end_time=datetime(
            2026,
            8,
            14,
            10,
            0,
            tzinfo=UTC,
        ),
        baseline_profile=baseline,
    )

    expectations = (
        build_historical_expectations(
            timeline=timeline,
            baseline_profile=baseline,
            runtime_profile=runtime,
            random_source=SimulationRandom(
                seed=seed
            ),
        )
    )

    return baseline, expectations


@pytest.mark.parametrize(
    "profile_id",
    [
        "critical_interactive_nominal",
        "business_workflow_nominal",
    ],
)
def test_builds_observations_for_all_metrics(
    profile_id: str,
) -> None:
    baseline, expectations = (
        build_expectations(
            profile_id=profile_id
        )
    )

    observations = (
        build_historical_observations(
            expectation_bundle=expectations,
            baseline_profile=baseline,
            random_source=SimulationRandom(
                seed=100
            ),
        )
    )

    assert set(
        observations.metric_series
    ) == set(
        baseline.metrics
    )

    assert all(
        len(series.points) == 6
        for series
        in observations.metric_series.values()
    )


def test_observations_preserve_expectation_coordinates(
) -> None:
    baseline, expectations = (
        build_expectations(
            profile_id=(
                "critical_interactive_nominal"
            )
        )
    )

    observations = (
        build_historical_observations(
            expectation_bundle=expectations,
            baseline_profile=baseline,
            random_source=SimulationRandom(
                seed=100
            ),
        )
    )

    for metric_id in baseline.metrics:
        expected_points = (
            expectations.metric_series[
                metric_id
            ].points
        )

        observed_points = (
            observations.metric_series[
                metric_id
            ].points
        )

        assert tuple(
            point.timestamp
            for point in observed_points
        ) == tuple(
            point.timestamp
            for point in expected_points
        )

        assert tuple(
            point.activity_factor
            for point in observed_points
        ) == tuple(
            point.activity_factor
            for point in expected_points
        )


def test_nonzero_baseline_noise_changes_observations(
) -> None:
    baseline, expectations = (
        build_expectations(
            profile_id=(
                "critical_interactive_nominal"
            )
        )
    )

    observations = (
        build_historical_observations(
            expectation_bundle=expectations,
            baseline_profile=baseline,
            random_source=SimulationRandom(
                seed=100
            ),
        )
    )

    assert any(
        observed.observed_value
        != expected.expected_value
        for metric_id in baseline.metrics
        for observed, expected in zip(
            observations.metric_series[
                metric_id
            ].points,
            expectations.metric_series[
                metric_id
            ].points,
            strict=True,
        )
    )


def test_historical_observations_are_reproducible(
) -> None:
    baseline, expectations = (
        build_expectations(
            profile_id=(
                "critical_interactive_nominal"
            )
        )
    )

    first = build_historical_observations(
        expectation_bundle=expectations,
        baseline_profile=baseline,
        random_source=SimulationRandom(
            seed=100
        ),
    )

    second = build_historical_observations(
        expectation_bundle=expectations,
        baseline_profile=baseline,
        random_source=SimulationRandom(
            seed=100
        ),
    )

    assert first == second


def test_historical_observations_vary_with_seed(
) -> None:
    baseline, expectations = (
        build_expectations(
            profile_id=(
                "critical_interactive_nominal"
            )
        )
    )

    first = build_historical_observations(
        expectation_bundle=expectations,
        baseline_profile=baseline,
        random_source=SimulationRandom(
            seed=100
        ),
    )

    second = build_historical_observations(
        expectation_bundle=expectations,
        baseline_profile=baseline,
        random_source=SimulationRandom(
            seed=101
        ),
    )

    assert (
        first.metric_series
        != second.metric_series
    )


@pytest.mark.parametrize(
    "profile_id",
    [
        "critical_interactive_nominal",
        "business_workflow_nominal",
    ],
)
def test_observations_respect_baseline_bounds(
    profile_id: str,
) -> None:
    baseline, expectations = (
        build_expectations(
            profile_id=profile_id
        )
    )

    observations = (
        build_historical_observations(
            expectation_bundle=expectations,
            baseline_profile=baseline,
            random_source=SimulationRandom(
                seed=100
            ),
        )
    )

    for metric_id, series in (
        observations.metric_series.items()
    ):
        metric_baseline = (
            baseline.metrics[
                metric_id
            ]
        )

        for point in series.points:
            if (
                metric_baseline.lower_bound
                is not None
            ):
                assert (
                    point.observed_value
                    >= metric_baseline.lower_bound
                )

            if (
                metric_baseline.upper_bound
                is not None
            ):
                assert (
                    point.observed_value
                    <= metric_baseline.upper_bound
                )


def test_zero_noise_preserves_expected_values(
) -> None:
    baseline, expectations = (
        build_expectations(
            profile_id=(
                "critical_interactive_nominal"
            )
        )
    )

    zero_noise_baseline = BaselineProfile(
        profile_id=baseline.profile_id,
        name=baseline.name,
        historical_window_minutes=(
            baseline.historical_window_minutes
        ),
        sample_interval_seconds=(
            baseline.sample_interval_seconds
        ),
        metrics={
            metric_id: MetricBaseline(
                metric_definition_id=(
                    metric.metric_definition_id
                ),
                center=metric.center,
                noise_stddev=0.0,
                lower_bound=metric.lower_bound,
                upper_bound=metric.upper_bound,
            )
            for metric_id, metric
            in baseline.metrics.items()
        },
    )

    observations = (
        build_historical_observations(
            expectation_bundle=expectations,
            baseline_profile=(
                zero_noise_baseline
            ),
            random_source=SimulationRandom(
                seed=999
            ),
        )
    )

    for metric_id in baseline.metrics:
        assert tuple(
            point.observed_value
            for point
            in observations.metric_series[
                metric_id
            ].points
        ) == tuple(
            point.expected_value
            for point
            in expectations.metric_series[
                metric_id
            ].points
        )


def test_rejects_mismatched_baseline_profile(
) -> None:
    baseline, expectations = (
        build_expectations(
            profile_id=(
                "critical_interactive_nominal"
            )
        )
    )

    mismatched = BaselineProfile(
        profile_id="different_profile",
        name=baseline.name,
        historical_window_minutes=(
            baseline.historical_window_minutes
        ),
        sample_interval_seconds=(
            baseline.sample_interval_seconds
        ),
        metrics=baseline.metrics,
    )

    with pytest.raises(
        ValueError,
        match="Expectation bundle profile ID",
    ):
        build_historical_observations(
            expectation_bundle=expectations,
            baseline_profile=mismatched,
            random_source=SimulationRandom(
                seed=100
            ),
        )
