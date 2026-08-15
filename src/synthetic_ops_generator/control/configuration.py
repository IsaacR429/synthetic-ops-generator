from dataclasses import dataclass
from enum import StrEnum

from synthetic_ops_generator.history.perturbation import (
    PerturbationCurveSpec,
)


class GenerationLifecycle(StrEnum):
    BOUNDED = "bounded"
    CONTINUOUS = "continuous"


class ContinuousStopMode(StrEnum):
    MANUAL = "manual"
    DURATION = "duration"


@dataclass(frozen=True)
class ContinuousExecutionConfiguration:
    stop_mode: ContinuousStopMode = ContinuousStopMode.MANUAL
    duration_seconds: int | None = None

    def __post_init__(self) -> None:
        if self.stop_mode == ContinuousStopMode.MANUAL:
            if self.duration_seconds is not None:
                raise ValueError(
                    "Manual continuous execution cannot "
                    "define a duration."
                )

            return

        if self.stop_mode == ContinuousStopMode.DURATION:
            if self.duration_seconds is None:
                raise ValueError(
                    "Duration-based continuous execution "
                    "requires duration_seconds."
                )

            if self.duration_seconds <= 0:
                raise ValueError(
                    "Continuous execution duration must "
                    "be greater than zero."
                )

            return

        raise ValueError(
            f"Unsupported continuous stop mode: {self.stop_mode}"
        )


@dataclass(frozen=True)
class HistoricalExecutionConfiguration:
    degradation_samples: int = 4
    plateau_samples: int = 2
    recovery_samples: int = 4

    def __post_init__(self) -> None:
        self.to_curve_spec()

    def to_curve_spec(
        self,
    ) -> PerturbationCurveSpec:
        return PerturbationCurveSpec(
            degradation_samples=(
                self.degradation_samples
            ),
            plateau_samples=(
                self.plateau_samples
            ),
            recovery_samples=(
                self.recovery_samples
            ),
        )


DEFAULT_CONTINUOUS_EXECUTION_CONFIGURATION = (
    ContinuousExecutionConfiguration()
)


DEFAULT_HISTORICAL_EXECUTION_CONFIGURATION = (
    HistoricalExecutionConfiguration()
)
