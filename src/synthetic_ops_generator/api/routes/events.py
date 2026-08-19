from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from synthetic_ops_generator.api.models import (
    EventActivityResponse,
    EventActivityWindow,
)
from synthetic_ops_generator.control.service import ControlService

router = APIRouter(
    prefix="/events",
    tags=["events"],
)


def get_control_service(
    request: Request,
) -> ControlService:
    return request.app.state.control_service


ControlServiceDependency = Annotated[
    ControlService,
    Depends(get_control_service),
]


ACTIVITY_WINDOW_CONFIGURATION: dict[
    EventActivityWindow,
    tuple[timedelta, int],
] = {
    "1h": (
        timedelta(hours=1),
        5 * 60,
    ),
    "6h": (
        timedelta(hours=6),
        30 * 60,
    ),
    "24h": (
        timedelta(hours=24),
        60 * 60,
    ),
    "7d": (
        timedelta(days=7),
        6 * 60 * 60,
    ),
}


def floor_to_bucket_boundary(
    value: datetime,
    bucket_seconds: int,
) -> datetime:
    timestamp = int(
        value.astimezone(UTC).timestamp()
    )

    aligned_timestamp = (
        timestamp
        - timestamp % bucket_seconds
    )

    return datetime.fromtimestamp(
        aligned_timestamp,
        tz=UTC,
    )


def ceil_to_bucket_boundary(
    value: datetime,
    bucket_seconds: int,
) -> datetime:
    value_utc = value.astimezone(UTC)

    floor = floor_to_bucket_boundary(
        value_utc,
        bucket_seconds,
    )

    if value_utc == floor:
        return floor

    return floor + timedelta(
        seconds=bucket_seconds
    )


@router.get(
    "/activity",
    response_model=EventActivityResponse,
)
async def get_event_activity(
    service: ControlServiceDependency,
    window: Annotated[
        EventActivityWindow,
        Query(),
    ] = "24h",
) -> EventActivityResponse:
    duration, bucket_seconds = (
        ACTIVITY_WINDOW_CONFIGURATION[window]
    )

    end_time = ceil_to_bucket_boundary(
        datetime.now(UTC),
        bucket_seconds,
    )

    start_time = end_time - duration

    buckets = await service.get_event_activity(
        start_time=start_time,
        end_time=end_time,
        bucket_seconds=bucket_seconds,
    )

    return EventActivityResponse.from_activity(
        window=window,
        start_time=start_time,
        end_time=end_time,
        bucket_seconds=bucket_seconds,
        buckets=buckets,
    )
