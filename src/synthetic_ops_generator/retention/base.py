from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.retention.query import (
    EventActivityBucket,
    EventActivityQuery,
    EventQuery,
)


@dataclass(frozen=True)
class RunEventWindow:
    """
    One internally consistent retained-event snapshot for a Run.

    Events are returned in canonical Run sequence order even when
    the storage implementation selects the latest bounded window.
    """

    total_event_count: int
    events: tuple[GeneratedEvent, ...]


class EventStore(ABC):
    """
    Persistent storage port for canonical GeneratedEvents.

    Storage implementations preserve the canonical event contract
    and return events in Run sequence order.
    """

    @abstractmethod
    async def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def append(
        self,
        event: GeneratedEvent,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_run_events(
        self,
        run_id: str,
    ) -> Sequence[GeneratedEvent]:
        raise NotImplementedError

    @abstractmethod
    async def get_latest_run_event_window(
        self,
        run_id: str,
        *,
        limit: int,
    ) -> RunEventWindow:
        raise NotImplementedError

    @abstractmethod
    async def query_events(
        self,
        query: EventQuery,
    ) -> Sequence[GeneratedEvent]:
        raise NotImplementedError

    @abstractmethod
    async def count_events(
        self,
        query: EventQuery,
    ) -> int:
        raise NotImplementedError

    @abstractmethod
    async def aggregate_event_activity(
        self,
        query: EventActivityQuery,
    ) -> Sequence[EventActivityBucket]:
        raise NotImplementedError

    @abstractmethod
    async def delete_before(
        self,
        cutoff: datetime,
    ) -> int:
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        raise NotImplementedError
