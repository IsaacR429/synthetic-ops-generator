from dataclasses import dataclass

from synthetic_ops_generator.history.perturbation import (
    PerturbationCurveSpec,
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


DEFAULT_HISTORICAL_EXECUTION_CONFIGURATION = (
    HistoricalExecutionConfiguration()
)
