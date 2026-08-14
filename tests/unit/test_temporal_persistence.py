from datetime import UTC, datetime

import pytest

from synthetic_ops_generator.core.randomness import (
    SimulationRandom,
)
from synthetic_ops_generator.history.temporal import (
    TemporalActivityProfile,
    TemporalPersistenceProfile,
    build_activity_series,
)
from synthetic_ops_generator.history.timeline import (
    build_historical_timeline,
)


def build_activity_profile(
) -> TemporalActivityProfile:
    return TemporalActivityProfile(
        business_start_hour=8,
        business_end_hour=18,
        business_days=frozenset(
            {0, 1, 2, 3, 4}
        ),
        business_hours_factor=1.0,
        off_hours_factor=0.6,
        weekend_factor=0.4,
    )


def test_activity_series_smoothly_moves_toward_new_target(
) -> None:
    timeline = build_historical_timeline(
        end_time=datetime(
            2026,
            8,
            14,
            8,
            25,
            tzinfo=UTC,
        ),
        historical_window_minutes=40,
        sample_interval_seconds=300,
    )

    series = build_activity_series(
        timeline=timeline,
        activity_profile=(
            build_activity_profile()
        ),
        persistence_profile=(
            TemporalPersistenceProfile(
                persistence=0.5,
                innovation_stddev=0.0,
            )
        ),
        random_source=SimulationRandom(
            seed=42
        ),
    )

    activities = [
        point.activity_factor
        for point in series.points
    ]

    targets = [
        point.target_factor
        for point in series.points
    ]

    assert targets == [
        0.6,
        0.6,
        0.6,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
    ]

    assert activities == pytest.approx(
        [
            0.6,
            0.6,
            0.6,
            0.8,
            0.9,
            0.95,
            0.975,
            0.9875,
        ]
    )


def test_activity_series_is_reproducible_for_same_seed(
) -> None:
    timeline = build_historical_timeline(
        end_time=datetime(
            2026,
            8,
            14,
            12,
            0,
            tzinfo=UTC,
        ),
        historical_window_minutes=30,
        sample_interval_seconds=300,
    )

    persistence_profile = (
        TemporalPersistenceProfile(
            persistence=0.8,
            innovation_stddev=0.03,
        )
    )

    first = build_activity_series(
        timeline=timeline,
        activity_profile=(
            build_activity_profile()
        ),
        persistence_profile=(
            persistence_profile
        ),
        random_source=SimulationRandom(
            seed=42
        ),
    )

    second = build_activity_series(
        timeline=timeline,
        activity_profile=(
            build_activity_profile()
        ),
        persistence_profile=(
            persistence_profile
        ),
        random_source=SimulationRandom(
            seed=42
        ),
    )

    assert first == second


def test_activity_series_varies_for_different_seeds(
) -> None:
    timeline = build_historical_timeline(
        end_time=datetime(
            2026,
            8,
            14,
            12,
            0,
            tzinfo=UTC,
        ),
        historical_window_minutes=30,
        sample_interval_seconds=300,
    )

    persistence_profile = (
        TemporalPersistenceProfile(
            persistence=0.8,
            innovation_stddev=0.03,
        )
    )

    first = build_activity_series(
        timeline=timeline,
        activity_profile=(
            build_activity_profile()
        ),
        persistence_profile=(
            persistence_profile
        ),
        random_source=SimulationRandom(
            seed=42
        ),
    )

    second = build_activity_series(
        timeline=timeline,
        activity_profile=(
            build_activity_profile()
        ),
        persistence_profile=(
            persistence_profile
        ),
        random_source=SimulationRandom(
            seed=43
        ),
    )

    assert first != second


def test_activity_series_respects_bounds(
) -> None:
    timeline = build_historical_timeline(
        end_time=datetime(
            2026,
            8,
            14,
            12,
            0,
            tzinfo=UTC,
        ),
        historical_window_minutes=30,
        sample_interval_seconds=300,
    )

    series = build_activity_series(
        timeline=timeline,
        activity_profile=(
            build_activity_profile()
        ),
        persistence_profile=(
            TemporalPersistenceProfile(
                persistence=0.5,
                innovation_stddev=10.0,
                lower_bound=0.2,
                upper_bound=1.5,
            )
        ),
        random_source=SimulationRandom(
            seed=42
        ),
    )

    assert all(
        0.2
        <= point.activity_factor
        <= 1.5
        for point in series.points
    )


@pytest.mark.parametrize(
    (
        "persistence",
        "innovation_stddev",
    ),
    [
        (-0.1, 0.03),
        (1.0, 0.03),
        (1.1, 0.03),
        (0.8, -0.01),
    ],
)
def test_persistence_profile_rejects_invalid_configuration(
    persistence: float,
    innovation_stddev: float,
) -> None:
    with pytest.raises(ValueError):
        TemporalPersistenceProfile(
            persistence=persistence,
            innovation_stddev=(
                innovation_stddev
            ),
        )


def test_persistence_profile_rejects_invalid_bounds(
) -> None:
    with pytest.raises(
        ValueError,
        match="upper_bound",
    ):
        TemporalPersistenceProfile(
            persistence=0.8,
            innovation_stddev=0.03,
            lower_bound=1.0,
            upper_bound=0.5,
        )
