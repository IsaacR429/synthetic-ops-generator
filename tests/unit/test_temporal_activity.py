from datetime import UTC, datetime

import pytest

from synthetic_ops_generator.history.temporal import (
    TemporalActivityProfile,
    activity_factor_at,
)


def build_profile() -> TemporalActivityProfile:
    return TemporalActivityProfile(
        business_start_hour=8,
        business_end_hour=18,
        business_days=frozenset(
            {0, 1, 2, 3, 4}
        ),
        business_hours_factor=1.0,
        off_hours_factor=0.65,
        weekend_factor=0.45,
    )


def test_business_hour_uses_business_factor(
) -> None:
    timestamp = datetime(
        2026,
        8,
        14,
        10,
        0,
        tzinfo=UTC,
    )

    assert activity_factor_at(
        timestamp=timestamp,
        profile=build_profile(),
    ) == 1.0


def test_weekday_off_hours_uses_off_hours_factor(
) -> None:
    timestamp = datetime(
        2026,
        8,
        14,
        3,
        0,
        tzinfo=UTC,
    )

    assert activity_factor_at(
        timestamp=timestamp,
        profile=build_profile(),
    ) == 0.65


def test_weekend_uses_weekend_factor(
) -> None:
    timestamp = datetime(
        2026,
        8,
        15,
        10,
        0,
        tzinfo=UTC,
    )

    assert activity_factor_at(
        timestamp=timestamp,
        profile=build_profile(),
    ) == 0.45


def test_business_end_hour_is_exclusive(
) -> None:
    timestamp = datetime(
        2026,
        8,
        14,
        18,
        0,
        tzinfo=UTC,
    )

    assert activity_factor_at(
        timestamp=timestamp,
        profile=build_profile(),
    ) == 0.65


def test_temporal_activity_rejects_naive_timestamp(
) -> None:
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        activity_factor_at(
            timestamp=datetime(  # noqa: DTZ001
                2026,
                8,
                14,
                10,
                0,
            ),
            profile=build_profile(),
        )


@pytest.mark.parametrize(
    (
        "start_hour",
        "end_hour",
    ),
    [
        (-1, 18),
        (24, 18),
        (8, 25),
        (18, 8),
        (8, 8),
    ],
)
def test_temporal_profile_rejects_invalid_hours(
    start_hour: int,
    end_hour: int,
) -> None:
    with pytest.raises(ValueError):
        TemporalActivityProfile(
            business_start_hour=start_hour,
            business_end_hour=end_hour,
            business_days=frozenset(
                {0, 1, 2, 3, 4}
            ),
            business_hours_factor=1.0,
            off_hours_factor=0.65,
            weekend_factor=0.45,
        )