from abc import ABC, abstractmethod

from synthetic_ops_generator.control.models import (
    RunRecord,
    RunStatus,
)


class RunStore(ABC):
    """
    Persistent storage port for Scenario Run metadata.

    Run metadata is stored separately from canonical generated
    events retained by EventStore.
    """

    @abstractmethod
    async def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def create(
        self,
        record: RunRecord,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get(
        self,
        run_id: str,
    ) -> RunRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_status(
        self,
        status: RunStatus,
    ) -> tuple[RunRecord, ...]:
        raise NotImplementedError

    @abstractmethod
    async def update(
        self,
        record: RunRecord,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        raise NotImplementedError
