from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime

from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.retention.query import EventQuery


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
    async def query_events(
        self,
        query: EventQuery,
    ) -> Sequence[GeneratedEvent]:
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
