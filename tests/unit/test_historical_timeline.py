from datetime import UTC, datetime

import pytest

from synthetic_ops_generator.baselines.models import (
    BaselineProfile,
    MetricBaseline,
)
from synthetic_ops_generator.history.timeline import (
    build_baseline_timeline,
    build_historical_timeline,
)


def test_build_historical_timeline_calculates_correct_bounds_and_timestamps(
) -> None:
    end_time = datetime(
        2026,
        8,
        14,
        10,
        0,
        tzinfo=UTC,
    )

    timeline = build_historical_timeline(
        end_time=end_time,
        historical_window_minutes=60,
        sample_interval_seconds=300,
    )

    assert timeline.start_time == datetime(
        2026,
        8,
        14,
        9,
        0,
        tzinfo=UTC,
    )
    assert timeline.end_time == end_time
    assert timeline.sample_interval_seconds == 300
    assert len(timeline.timestamps) == 12

    assert timeline.timestamps[0] == datetime(
        2026,
        8,
        14,
        9,
        0,
        tzinfo=UTC,
    )
    assert timeline.timestamps[-1] == datetime(
        2026,
        8,
        14,
        9,
        55,
        tzinfo=UTC,
    )


def test_historical_timeline_uses_consistent_interval(
) -> None:
    end_time = datetime(
        2026,
        8,
        14,
        10,
        0,
        tzinfo=UTC,
    )

    timeline = build_historical_timeline(
        end_time=end_time,
        historical_window_minutes=30,
        sample_interval_seconds=300,
    )

    intervals = [
        (
            current - previous
        ).total_seconds()
        for previous, current in zip(
            timeline.timestamps[:-1],
            timeline.timestamps[1:],
            strict=True,
        )
    ]

    assert intervals == [
        300.0,
        300.0,
        300.0,
        300.0,
        300.0,
    ]


def test_historical_timeline_rejects_naive_end_time(
) -> None:
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        build_historical_timeline(
            end_time=datetime(  # noqa: DTZ001
                2026,
                8,
                14,
                10,
                0,
            ),
            historical_window_minutes=60,
            sample_interval_seconds=300,
        )


@pytest.mark.parametrize(
    (
        "historical_window_minutes",
        "sample_interval_seconds",
    ),
    [
        (0, 300),
        (-1, 300),
        (60, 0),
        (60, -1),
    ],
)
def test_historical_timeline_rejects_invalid_configuration(
    historical_window_minutes: int,
    sample_interval_seconds: int,
) -> None:
    with pytest.raises(ValueError):
        build_historical_timeline(
            end_time=datetime(
                2026,
                8,
                14,
                10,
                0,
                tzinfo=UTC,
            ),
            historical_window_minutes=(
                historical_window_minutes
            ),
            sample_interval_seconds=(
                sample_interval_seconds
            ),
        )


def test_historical_timeline_rejects_too_large_sample_interval() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "exactly divisible by "
            "the sample interval"
        ),
    ):
        build_historical_timeline(
            end_time=datetime(
                2026,
                8,
                14,
                10,
                0,
                tzinfo=UTC,
            ),
            historical_window_minutes=1,
            sample_interval_seconds=3600,
        )


def test_historical_timeline_rejects_partial_sample_window(
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "exactly divisible by "
            "the sample interval"
        ),
    ):
        build_historical_timeline(
            end_time=datetime(
                2026,
                8,
                14,
                10,
                0,
                tzinfo=UTC,
            ),
            historical_window_minutes=60,
            sample_interval_seconds=420,
        )


def test_baseline_profile_builds_historical_timeline(
) -> None:
    profile = BaselineProfile(
        profile_id="payment_service_baseline",
        name="Payment Service Baseline",
        historical_window_minutes=60,
        sample_interval_seconds=300,
        metrics={
            "cpu_utilization": MetricBaseline(
                metric_definition_id=(
                    "cpu_utilization"
                ),
                center=40.0,
                noise_stddev=5.0,
                lower_bound=0.0,
                upper_bound=100.0,
            )
        },
    )

    end_time = datetime(
        2026,
        8,
        14,
        10,
        0,
        tzinfo=UTC,
    )

    timeline = build_baseline_timeline(
        end_time=end_time,
        baseline_profile=profile,
    )

    assert len(timeline.timestamps) == 12

    assert timeline.start_time == datetime(
        2026,
        8,
        14,
        9,
        0,
        tzinfo=UTC,
    )

    assert timeline.timestamps[-1] == datetime(
        2026,
        8,
        14,
        9,
        55,
        tzinfo=UTC,
    )

    assert timeline.end_time == end_time

    assert (
        timeline.sample_interval_seconds
        == 300
    )


def test_historical_timeline_excludes_end_boundary(
) -> None:
    end_time = datetime(
        2026,
        8,
        14,
        10,
        0,
        tzinfo=UTC,
    )

    timeline = build_historical_timeline(
        end_time=end_time,
        historical_window_minutes=15,
        sample_interval_seconds=300,
    )

    assert timeline.timestamps == (
        datetime(
            2026,
            8,
            14,
            9,
            45,
            tzinfo=UTC,
        ),
        datetime(
            2026,
            8,
            14,
            9,
            50,
            tzinfo=UTC,
        ),
        datetime(
            2026,
            8,
            14,
            9,
            55,
            tzinfo=UTC,
        ),
    )

    assert end_time not in timeline.timestamps
