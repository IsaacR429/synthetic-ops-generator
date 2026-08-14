from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from synthetic_ops_generator.control.configuration import (
    HistoricalExecutionConfiguration,
)
from synthetic_ops_generator.domain.enums import (
    OperationalState,
)


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class RunExecutionMode(StrEnum):
    STANDARD = "standard"
    HISTORICAL = "historical"


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    scenario_id: str
    change_id: str

    status: RunStatus

    started_at: datetime
    completed_at: datetime | None

    current_state: OperationalState

    event_count: int
    validation_passed: bool | None

    random_seed: int
    event_interval_seconds: float

    error_message: str | None = None

    execution_mode: RunExecutionMode = (
        RunExecutionMode.STANDARD
    )

    historical_configuration: (
        HistoricalExecutionConfiguration | None
    ) = None


@dataclass(frozen=True)
class RunStartResult:
    scenario_id: str
    run_id: str
    change_id: str
    status: RunStatus

    execution_mode: RunExecutionMode = (
        RunExecutionMode.STANDARD
    )

    historical_configuration: (
        HistoricalExecutionConfiguration | None
    ) = None


@dataclass(frozen=True)
class StopRunResult:
    run_id: str
    scenario_id: str
    status: RunStatus
    event_count: int


@dataclass(frozen=True)
class RunExecutionResult:
    scenario_id: str
    run_id: str
    change_id: str

    visited_states: tuple[str, ...]

    event_count: int
    validation_passed: bool


@dataclass(frozen=True)
class ReplayExecutionResult:
    run_id: str
    scenario_id: str
    replayed_event_count: int