from dataclasses import dataclass
from datetime import datetime, timedelta

from synthetic_ops_generator.baselines.models import (
    BaselineProfile,
)


@dataclass(frozen=True)
class HistoricalTimeline:
    start_time: datetime
    end_time: datetime
    sample_interval_seconds: int
    timestamps: tuple[datetime, ...]


def build_historical_timeline(
    *,
    end_time: datetime,
    historical_window_minutes: int,
    sample_interval_seconds: int,
) -> HistoricalTimeline:
    if end_time.tzinfo is None or end_time.utcoffset() is None:
        raise ValueError(
            "Historical timeline end_time must be timezone-aware."
        )

    if historical_window_minutes <= 0:
        raise ValueError(
            "Historical window must be greater than zero."
        )

    if sample_interval_seconds <= 0:
        raise ValueError(
            "Sample interval must be greater than zero."
        )

    window_seconds = (
        historical_window_minutes * 60
    )

    if (
        window_seconds
        % sample_interval_seconds
        != 0
    ):
        raise ValueError(
            "Historical window must be exactly "
            "divisible by the sample interval."
        )

    sample_count = (
        window_seconds
        // sample_interval_seconds
    )

    if sample_count == 0:
        raise ValueError(
            "Historical window must contain at least "
            "one sample interval."
        )

    start_time = end_time - timedelta(
        seconds=window_seconds
    )

    timestamps = tuple(
        start_time
        + timedelta(
            seconds=(
                index
                * sample_interval_seconds
            )
        )
        for index in range(sample_count)
    )

    return HistoricalTimeline(
        start_time=start_time,
        end_time=end_time,
        sample_interval_seconds=(
            sample_interval_seconds
        ),
        timestamps=timestamps,
    )


def build_baseline_timeline(
    *,
    end_time: datetime,
    baseline_profile: BaselineProfile,
) -> HistoricalTimeline:
    return build_historical_timeline(
        end_time=end_time,
        historical_window_minutes=(
            baseline_profile.historical_window_minutes
        ),
        sample_interval_seconds=(
            baseline_profile.sample_interval_seconds
        ),
    )
