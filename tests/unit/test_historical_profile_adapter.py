import pytest

from synthetic_ops_generator.baselines.loader import (
    load_baseline_profile,
)
from synthetic_ops_generator.baselines.models import (
    BaselineProfile,
    MetricBaseline,
)
from synthetic_ops_generator.history.adapter import (
    build_historical_runtime_profile,
)
from synthetic_ops_generator.history.loader import (
    load_historical_behaviour_profile,
)
from synthetic_ops_generator.history.models import (
    HistoricalBehaviourProfile,
    HistoricalMetricResponse,
    TemporalActivityConfig,
    TemporalPersistenceConfig,
)


def build_baseline_profile(
) -> BaselineProfile:
    return BaselineProfile(
        profile_id="test_profile",
        name="Test Baseline",
        historical_window_minutes=30,
        sample_interval_seconds=300,
        metrics={
            "request_latency": MetricBaseline(
                metric_definition_id=(
                    "request_latency"
                ),
                center=180.0,
                noise_stddev=15.0,
            ),
            "error_rate": MetricBaseline(
                metric_definition_id=(
                    "error_rate"
                ),
                center=0.05,
                noise_stddev=0.02,
            ),
        },
    )


def build_historical_profile(
) -> HistoricalBehaviourProfile:
    return HistoricalBehaviourProfile(
        profile_id="test_profile",
        name="Test Historical Profile",
        temporal=TemporalActivityConfig(
            business_start_hour=8,
            business_end_hour=18,
            business_days=[
                0,
                1,
                2,
                3,
                4,
            ],
            business_hours_factor=1.0,
            off_hours_factor=0.65,
            weekend_factor=0.45,
        ),
        persistence=(
            TemporalPersistenceConfig(
                persistence=0.8,
                innovation_stddev=0.03,
                lower_bound=0.2,
                upper_bound=1.5,
            )
        ),
        metric_responses={
            "request_latency": (
                HistoricalMetricResponse(
                    metric_definition_id=(
                        "request_latency"
                    ),
                    slope_per_activity_unit=(
                        150.0
                    ),
                )
            ),
            "error_rate": (
                HistoricalMetricResponse(
                    metric_definition_id=(
                        "error_rate"
                    ),
                    slope_per_activity_unit=(
                        0.10
                    ),
                )
            ),
        },
    )


def test_builds_runtime_profile_from_configuration(
) -> None:
    runtime = (
        build_historical_runtime_profile(
            baseline_profile=(
                build_baseline_profile()
            ),
            historical_profile=(
                build_historical_profile()
            ),
        )
    )

    assert runtime.profile_id == "test_profile"

    assert (
        runtime.activity_profile.business_days
        == frozenset(
            {0, 1, 2, 3, 4}
        )
    )

    assert (
        runtime.activity_profile.off_hours_factor
        == 0.65
    )

    assert (
        runtime.persistence_profile.persistence
        == 0.8
    )

    assert (
        runtime.persistence_profile.upper_bound
        == 1.5
    )

    assert {
        *runtime.metric_responses,
    } == {
        "request_latency",
        "error_rate",
    }

    assert (
        runtime.metric_responses[
            "request_latency"
        ].slope_per_activity_unit
        == 150.0
    )


def test_rejects_mismatched_profile_ids(
) -> None:
    historical = (
        build_historical_profile()
    )

    baseline = BaselineProfile(
        profile_id="different_profile",
        name="Different Baseline",
        historical_window_minutes=30,
        sample_interval_seconds=300,
        metrics=(
            build_baseline_profile().metrics
        ),
    )

    with pytest.raises(
        ValueError,
        match="same profile ID",
    ):
        build_historical_runtime_profile(
            baseline_profile=baseline,
            historical_profile=historical,
        )


def test_rejects_missing_metric_response(
) -> None:
    historical = (
        build_historical_profile()
    )

    incomplete = (
        HistoricalBehaviourProfile(
            profile_id=(
                historical.profile_id
            ),
            name=historical.name,
            temporal=historical.temporal,
            persistence=(
                historical.persistence
            ),
            metric_responses={
                "request_latency": (
                    historical.metric_responses[
                        "request_latency"
                    ]
                )
            },
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "missing metric responses for: "
            "error_rate"
        ),
    ):
        build_historical_runtime_profile(
            baseline_profile=(
                build_baseline_profile()
            ),
            historical_profile=incomplete,
        )


def test_rejects_unknown_metric_response(
) -> None:
    historical = (
        build_historical_profile()
    )

    with_extra = (
        HistoricalBehaviourProfile(
            profile_id=(
                historical.profile_id
            ),
            name=historical.name,
            temporal=historical.temporal,
            persistence=(
                historical.persistence
            ),
            metric_responses={
                **historical.metric_responses,
                "availability": (
                    HistoricalMetricResponse(
                        metric_definition_id=(
                            "availability"
                        ),
                        slope_per_activity_unit=(
                            -0.02
                        ),
                    )
                ),
            },
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "not present in the Baseline "
            "profile: availability"
        ),
    ):
        build_historical_runtime_profile(
            baseline_profile=(
                build_baseline_profile()
            ),
            historical_profile=with_extra,
        )


@pytest.mark.parametrize(
    "profile_id",
    [
        "critical_interactive_nominal",
        "business_workflow_nominal",
    ],
)
def test_real_baseline_and_historical_profiles_are_compatible(
    profile_id: str,
) -> None:
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

    assert runtime.profile_id == profile_id

    assert set(
        runtime.metric_responses
    ) == set(
        baseline.metrics
    )
