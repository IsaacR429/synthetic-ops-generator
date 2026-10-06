from abc import ABC, abstractmethod

from synthetic_ops_generator.control.models import (
    RunRecord,
    RunStatus,
)
from synthetic_ops_generator.domain.enums import (
    OperationalState,
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
    async def list_all(
        self,
    ) -> tuple[RunRecord, ...]:
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
    async def update_progress(
        self,
        *,
        run_id: str,
        current_state: OperationalState,
        event_count: int,
    ) -> bool:
        """
        Persist execution progress only while the Run is RUNNING.
        Returns True when progress was updated and False when
        the Run exists but is already terminal.
        """
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        raise NotImplementedError
