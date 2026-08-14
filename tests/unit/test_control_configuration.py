import pytest

from synthetic_ops_generator.control.configuration import (
    DEFAULT_HISTORICAL_EXECUTION_CONFIGURATION,
    HistoricalExecutionConfiguration,
)


def test_default_historical_execution_configuration() -> None:
    configuration = (
        DEFAULT_HISTORICAL_EXECUTION_CONFIGURATION
    )

    assert configuration.degradation_samples == 4
    assert configuration.plateau_samples == 2
    assert configuration.recovery_samples == 4


def test_historical_execution_configuration_builds_curve_spec() -> None:
    configuration = (
        HistoricalExecutionConfiguration(
            degradation_samples=6,
            plateau_samples=3,
            recovery_samples=5,
        )
    )

    curve_spec = configuration.to_curve_spec()

    assert curve_spec.degradation_samples == 6
    assert curve_spec.plateau_samples == 3
    assert curve_spec.recovery_samples == 5


@pytest.mark.parametrize(
    (
        "degradation_samples",
        "plateau_samples",
        "recovery_samples",
    ),
    [
        (0, 2, 4),
        (-1, 2, 4),
        (4, -1, 4),
        (4, 2, -1),
    ],
)
def test_historical_execution_configuration_reuses_curve_validation(
    degradation_samples: int,
    plateau_samples: int,
    recovery_samples: int,
) -> None:
    with pytest.raises(ValueError):
        HistoricalExecutionConfiguration(
            degradation_samples=(
                degradation_samples
            ),
            plateau_samples=(
                plateau_samples
            ),
            recovery_samples=(
                recovery_samples
            ),
        )
