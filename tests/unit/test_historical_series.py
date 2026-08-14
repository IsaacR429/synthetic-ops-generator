from datetime import UTC, datetime

import pytest

from synthetic_ops_generator.baselines.loader import (
    load_baseline_profile,
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
from synthetic_ops_generator.history.series import (
    HistoricalExpectationBundle,
    build_historical_expectations,
)
from synthetic_ops_generator.history.timeline import (
    build_baseline_timeline,
)


def build_bundle(
    *,
    profile_id: str,
    seed: int = 42,
) -> HistoricalExpectationBundle:
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

    return build_historical_expectations(
        timeline=timeline,
        baseline_profile=baseline,
        runtime_profile=runtime,
        random_source=SimulationRandom(
            seed=seed
        ),
    )


@pytest.mark.parametrize(
    "profile_id",
    [
        "critical_interactive_nominal",
        "business_workflow_nominal",
    ],
)
def test_builds_expectations_for_all_baseline_metrics(
    profile_id: str,
) -> None:
    bundle = build_bundle(
        profile_id=profile_id
    )

    assert set(
        bundle.metric_series
    ) == {
        "request_latency",
        "error_rate",
        "availability",
    }


@pytest.mark.parametrize(
    "profile_id",
    [
        "critical_interactive_nominal",
        "business_workflow_nominal",
    ],
)
def test_bundle_uses_baseline_timeline_sample_count(
    profile_id: str,
) -> None:
    bundle = build_bundle(
        profile_id=profile_id
    )

    assert len(
        bundle.activity_series.points
    ) == 6

    assert all(
        len(series.points) == 6
        for series
        in bundle.metric_series.values()
    )


def test_metric_series_share_activity_timestamps(
) -> None:
    bundle = build_bundle(
        profile_id=(
            "critical_interactive_nominal"
        )
    )

    activity_timestamps = tuple(
        point.timestamp
        for point
        in bundle.activity_series.points
    )

    for series in (
        bundle.metric_series.values()
    ):
        metric_timestamps = tuple(
            point.timestamp
            for point
            in series.points
        )

        assert (
            metric_timestamps
            == activity_timestamps
        )


def test_metric_series_share_same_activity_factors(
) -> None:
    bundle = build_bundle(
        profile_id=(
            "critical_interactive_nominal"
        )
    )

    activity_factors = tuple(
        point.activity_factor
        for point
        in bundle.activity_series.points
    )

    for series in (
        bundle.metric_series.values()
    ):
        metric_activity = tuple(
            point.activity_factor
            for point
            in series.points
        )

        assert (
            metric_activity
            == activity_factors
        )


def test_historical_expectation_bundle_is_reproducible(
) -> None:
    first = build_bundle(
        profile_id=(
            "critical_interactive_nominal"
        ),
        seed=42,
    )

    second = build_bundle(
        profile_id=(
            "critical_interactive_nominal"
        ),
        seed=42,
    )

    assert first == second


def test_historical_expectations_vary_with_seed(
) -> None:
    first = build_bundle(
        profile_id=(
            "critical_interactive_nominal"
        ),
        seed=42,
    )

    second = build_bundle(
        profile_id=(
            "critical_interactive_nominal"
        ),
        seed=43,
    )

    assert (
        first.activity_series
        != second.activity_series
    )

    assert (
        first.metric_series
        != second.metric_series
    )


def test_shared_activity_drives_expected_metric_directions(
) -> None:
    bundle = build_bundle(
        profile_id=(
            "critical_interactive_nominal"
        )
    )

    latency = bundle.metric_series[
        "request_latency"
    ].points

    errors = bundle.metric_series[
        "error_rate"
    ].points

    availability = bundle.metric_series[
        "availability"
    ].points

    for index in range(
        len(
            bundle.activity_series.points
        )
        - 1
    ):
        current_activity = (
            bundle.activity_series.points[
                index
            ].activity_factor
        )

        next_activity = (
            bundle.activity_series.points[
                index + 1
            ].activity_factor
        )

        if next_activity > current_activity:
            assert (
                latency[
                    index + 1
                ].expected_value
                >= latency[
                    index
                ].expected_value
            )

            assert (
                errors[
                    index + 1
                ].expected_value
                >= errors[
                    index
                ].expected_value
            )

            assert (
                availability[
                    index + 1
                ].expected_value
                <= availability[
                    index
                ].expected_value
            )

        elif next_activity < current_activity:
            assert (
                latency[
                    index + 1
                ].expected_value
                <= latency[
                    index
                ].expected_value
            )

            assert (
                errors[
                    index + 1
                ].expected_value
                <= errors[
                    index
                ].expected_value
            )

            assert (
                availability[
                    index + 1
                ].expected_value
                >= availability[
                    index
                ].expected_value
            )
