from datetime import UTC, datetime, timedelta
from typing import Protocol


class SimulationClock(Protocol):
    def now(self) -> datetime:
        ...

    def advance(self, seconds: float) -> None:
        ...


class ManualSimulationClock:
    """
    Deterministic clock for scenarios and tests.
    """

    def __init__(self, start_at: datetime) -> None:
        if start_at.tzinfo is None:
            raise ValueError("Simulation clock requires a timezone-aware datetime.")

        self._current = start_at

    def now(self) -> datetime:
        return self._current

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("Simulation time cannot move backwards.")

        self._current += timedelta(seconds=seconds)


class RealTimeClock:
    """
    Runtime clock for future real-time execution.
    """

    def now(self) -> datetime:
        return datetime.now(UTC)

    def advance(self, seconds: float) -> None:
        raise RuntimeError("RealTimeClock cannot be advanced manually.")