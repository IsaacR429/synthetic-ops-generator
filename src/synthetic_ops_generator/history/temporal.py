from dataclasses import dataclass
from datetime import datetime

from synthetic_ops_generator.core.randomness import (
    SimulationRandom,
)
from synthetic_ops_generator.history.timeline import (
    HistoricalTimeline,
)


@dataclass(frozen=True)
class TemporalActivityProfile:
    business_start_hour: int
    business_end_hour: int

    business_days: frozenset[int]

    business_hours_factor: float
    off_hours_factor: float
    weekend_factor: float

    def __post_init__(self) -> None:
        if not 0 <= self.business_start_hour <= 23:
            raise ValueError(
                "business_start_hour must be between 0 and 23."
            )

        if not 1 <= self.business_end_hour <= 24:
            raise ValueError(
                "business_end_hour must be between 1 and 24."
            )

        if (
            self.business_start_hour
            >= self.business_end_hour
        ):
            raise ValueError(
                "business_start_hour must be before "
                "business_end_hour."
            )

        if not self.business_days:
            raise ValueError(
                "business_days cannot be empty."
            )

        if any(
            day < 0 or day > 6
            for day in self.business_days
        ):
            raise ValueError(
                "Business days must use weekday "
                "values from 0 to 6."
            )

        for name, value in (
            (
                "business_hours_factor",
                self.business_hours_factor,
            ),
            (
                "off_hours_factor",
                self.off_hours_factor,
            ),
            (
                "weekend_factor",
                self.weekend_factor,
            ),
        ):
            if value <= 0:
                raise ValueError(
                    f"{name} must be greater than zero."
                )


@dataclass(frozen=True)
class TemporalPersistenceProfile:
    persistence: float
    innovation_stddev: float

    lower_bound: float = 0.0
    upper_bound: float | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.persistence < 1.0:
            raise ValueError(
                "persistence must be greater than or "
                "equal to zero and less than one."
            )

        if self.innovation_stddev < 0:
            raise ValueError(
                "innovation_stddev cannot be negative."
            )

        if self.lower_bound < 0:
            raise ValueError(
                "lower_bound cannot be negative."
            )

        if (
            self.upper_bound is not None
            and self.upper_bound
            < self.lower_bound
        ):
            raise ValueError(
                "upper_bound cannot be below lower_bound."
            )


@dataclass(frozen=True)
class HistoricalActivityPoint:
    timestamp: datetime
    target_factor: float
    activity_factor: float


@dataclass(frozen=True)
class HistoricalActivitySeries:
    points: tuple[
        HistoricalActivityPoint,
        ...,
    ]


def activity_factor_at(
    *,
    timestamp: datetime,
    profile: TemporalActivityProfile,
) -> float:
    if (
        timestamp.tzinfo is None
        or timestamp.utcoffset() is None
    ):
        raise ValueError(
            "Temporal activity timestamp must "
            "be timezone-aware."
        )

    if timestamp.weekday() not in profile.business_days:
        return profile.weekend_factor

    if (
        profile.business_start_hour
        <= timestamp.hour
        < profile.business_end_hour
    ):
        return profile.business_hours_factor

    return profile.off_hours_factor


def build_activity_series(
    *,
    timeline: HistoricalTimeline,
    activity_profile: TemporalActivityProfile,
    persistence_profile: TemporalPersistenceProfile,
    random_source: SimulationRandom,
) -> HistoricalActivitySeries:
    if not timeline.timestamps:
        raise ValueError(
            "Historical timeline must contain "
            "at least one timestamp."
        )

    points: list[
        HistoricalActivityPoint
    ] = []

    previous_activity: float | None = None

    for timestamp in timeline.timestamps:
        target_factor = activity_factor_at(
            timestamp=timestamp,
            profile=activity_profile,
        )

        innovation = random_source.normal(
            0.0,
            persistence_profile.innovation_stddev,
        )

        if previous_activity is None:
            activity_factor = (
                target_factor
                + innovation
            )
        else:
            activity_factor = (
                persistence_profile.persistence
                * previous_activity
                + (
                    1.0
                    - persistence_profile.persistence
                )
                * target_factor
                + innovation
            )

        activity_factor = max(
            activity_factor,
            persistence_profile.lower_bound,
        )

        if (
            persistence_profile.upper_bound
            is not None
        ):
            activity_factor = min(
                activity_factor,
                persistence_profile.upper_bound,
            )

        points.append(
            HistoricalActivityPoint(
                timestamp=timestamp,
                target_factor=target_factor,
                activity_factor=float(
                    activity_factor
                ),
            )
        )

        previous_activity = (
            activity_factor
        )

    return HistoricalActivitySeries(
        points=tuple(points)
    )