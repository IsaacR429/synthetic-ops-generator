from dataclasses import dataclass
from datetime import datetime

from synthetic_ops_generator.domain.enums import SourceDomain


@dataclass(frozen=True)
class EventQuery:
    """
    Run-scoped filters for retained canonical events.

    None means that the corresponding projection field
    is not used as a filter.
    """

    run_id: str

    source_domain: SourceDomain | None = None
    source_system: str | None = None
    event_type: str | None = None
    service: str | None = None
    component: str | None = None

    after_sequence_number: int | None = None
    limit: int | None = None


@dataclass(frozen=True)
class EventActivityQuery:
    """
    Global retained-event activity aggregation window.

    EventStore implementations must validate the time
    window and bucket size before executing the query.
    """

    start_time: datetime
    end_time: datetime
    bucket_seconds: int


@dataclass(frozen=True)
class EventActivityBucket:
    """
    Aggregate retained-event count for one time bucket.
    """

    started_at: datetime
    event_count: int
